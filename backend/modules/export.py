# backend/modules/export.py
import pandas as pd
import io
from datetime import datetime
import xlsxwriter
from backend.database.repository import Repository

def generate_excel_report(user_id):
    """
    Hệ thống xuất Báo cáo Tài chính Pro: 
    Dashboard Biểu đồ + Danh mục chi tiết + Nhật ký giao dịch
    """
    # 1. Lấy dữ liệu từ Repository (Dùng Static Methods)
    raw_data = Repository.get_all_transactions_for_report(user_id)
    current_prices = Repository.get_current_prices()
    
    # 2. Tạo Buffer để xử lý file trên RAM
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book

    # --- HỆ THỐNG ĐỊNH DẠNG (FORMATTING) ---
    title_fmt = workbook.add_format({'bold': True, 'font_size': 18, 'font_color': '#1F4E78', 'align': 'center', 'valign': 'vcenter'})
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#BDD7EE', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
    money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1, 'align': 'right'})
    pct_fmt = workbook.add_format({'num_format': '0.00%', 'border': 1, 'align': 'right'})
    border_fmt = workbook.add_format({'border': 1})
    
    # Định dạng màu sắc Lãi/Lỗ
    green_money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1, 'font_color': '#006100', 'bg_color': '#C6EFCE'})
    red_money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1, 'font_color': '#9C0006', 'bg_color': '#FFC7CE'})

    # --- 3. XỬ LÝ DỮ LIỆU DANH MỤC (PORTFOLIO) ---
    portfolio = {}
    total_in = 0
    total_out = 0
    
    for trx in raw_data:
        t = trx['ticker']
        if trx['type'] in ['IN', 'DEPOSIT']: total_in += trx['total_value']
        elif trx['type'] in ['OUT', 'WITHDRAW']: total_out += trx['total_value']
        
        if t not in portfolio:
            portfolio[t] = {'qty': 0, 'cost': 0, 'type': trx['asset_type']}
        
        p = portfolio[t]
        if trx['type'] == 'BUY':
            new_qty = p['qty'] + trx['qty']
            if new_qty > 0:
                p['cost'] = (p['qty'] * p['cost'] + trx['total_value']) / new_qty
            p['qty'] = new_qty
        elif trx['type'] == 'SELL':
            p['qty'] -= trx['qty']
            if p['qty'] <= 0: p['qty'] = 0; p['cost'] = 0

    portfolio_data = []
    for t, v in portfolio.items():
        if v['qty'] > 0:
            curr_p = current_prices.get(t, v['cost'])
            market_val = v['qty'] * curr_p
            cost_val = v['qty'] * v['cost']
            pnl = market_val - cost_val
            roi = pnl/cost_val if cost_val > 0 else 0
            portfolio_data.append({
                'Mã TS': t, 'Phân khúc': v['type'], 'Số lượng': v['qty'], 
                'Giá vốn TB': v['cost'], 'Giá thị trường': curr_p,
                'Tổng vốn': cost_val, 'Giá trị hiện tại': market_val,
                'Lãi/Lỗ tạm tính': pnl, 'ROI (%)': roi
            })
    df_port = pd.DataFrame(portfolio_data)

    # --- SHEET 1: 📊 DASHBOARD ---
    ws_dash = workbook.add_worksheet('📊 Dashboard')
    ws_dash.hide_gridlines(2)
    
    # Header & Tổng quan
    ws_dash.merge_range('A1:H2', 'BÁO CÁO QUẢN TRỊ TÀI CHÍNH CHI TIẾT', title_fmt)
    ws_dash.write('A4', f'Ngày báo cáo: {datetime.now().strftime("%d/%m/%Y %H:%M")}')

    # Thẻ Summary
    summary_headers = ['TỔNG TÀI SẢN (AUM)', 'VỐN ĐẦU TƯ RÒNG', 'LÃI/LỖ TỔNG HỢP', 'TỶ SUẤT ROI (%)']
    aum = df_port['Giá trị hiện tại'].sum() if not df_port.empty else 0
    net_invested = total_in - total_out
    total_pnl = aum - net_invested if net_invested > 0 else 0
    total_roi = total_pnl / net_invested if net_invested > 0 else 0
    
    summary_vals = [aum, net_invested, total_pnl, total_roi]
    
    for col, (header, val) in enumerate(zip(summary_headers, summary_vals)):
        ws_dash.write(4, col + 1, header, header_fmt)
        fmt = money_fmt if col < 3 else pct_fmt
        ws_dash.write(5, col + 1, val, fmt)

    # VẼ BIỂU ĐỒ TRÒN (PHÂN BỔ TÀI SẢN)
    if not df_port.empty:
        summary_cat = df_port.groupby('Phân khúc')['Giá trị hiện tại'].sum().reset_index()
        # Ghi data ẩn làm gốc cho Chart
        for i, row in summary_cat.iterrows():
            ws_dash.write(25 + i, 10, row['Phân khúc'])
            ws_dash.write(25 + i, 11, row['Giá trị hiện tại'])
            
        chart = workbook.add_chart({'type': 'pie'})
        chart.add_series({
            'name': 'Cơ cấu Danh mục',
            'categories': ['📊 Dashboard', 25, 10, 25 + len(summary_cat)-1, 10],
            'values':     ['📊 Dashboard', 25, 11, 25 + len(summary_cat)-1, 11],
            'data_labels': {'percentage': True, 'position': 'outside_end'},
        })
        chart.set_title({'name': 'Tỷ trọng Phân bổ Tài sản'})
        chart.set_style(10)
        ws_dash.insert_chart('B8', chart, {'x_scale': 1.2, 'y_scale': 1.2})

    # --- SHEET 2: 💼 DANH MỤC CHI TIẾT ---
    if not df_port.empty:
        df_port.to_excel(writer, sheet_name='💼 Danh Mục', index=False)
        ws_p = writer.sheets['💼 Danh Mục']
        
        # Format bảng và Autofit
        for col_num, value in enumerate(df_port.columns.values):
            ws_p.write(0, col_num, value, header_fmt)
            # Autofit logic đơn giản
            ws_p.set_column(col_num, col_num, 18)

        # Áp dụng format tiền và màu sắc lãi lỗ
        num_rows = len(df_port)
        ws_p.set_column('D:G', 18, money_fmt)
        ws_p.set_column('I:I', 15, pct_fmt)
        
        # Conditional Formatting cho cột Lãi/Lỗ (Cột H - index 7)
        ws_p.conditional_format(1, 7, num_rows, 7, {'type': 'cell', 'criteria': '>=', 'value': 0, 'format': green_money_fmt})
        ws_p.conditional_format(1, 7, num_rows, 7, {'type': 'cell', 'criteria': '<', 'value': 0, 'format': red_money_fmt})

    # --- SHEET 3: 📝 NHẬT KÝ GIAO DỊCH ---
    df_tx = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
    if not df_tx.empty:
        df_tx.to_excel(writer, sheet_name='📝 Nhật Ký', index=False)
        ws_tx = writer.sheets['📝 Nhật Ký']
        ws_tx.freeze_panes(1, 0)
        for col_num, value in enumerate(df_tx.columns.values):
            ws_tx.write(0, col_num, value, header_fmt)
            ws_tx.set_column(col_num, col_num, 15)
        ws_tx.set_column('H:I', 18, money_fmt)

    writer.close()
    output.seek(0)
    return output
