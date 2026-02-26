# backend/modules/export.py
import pandas as pd
import io
from datetime import datetime
import xlsxwriter
from backend.database.repository import Repository

def generate_excel_report(user_id):
    """
    Hệ thống Báo cáo Tài chính v4.0: 
    - Fix lỗi ZeroDivisionError
    - Dashboard Đa biểu đồ (Tròn + Cột)
    - Auto-Filter (Bộ lọc) cho toàn bộ bảng dữ liệu
    - Kẻ bảng (Borders) & Định dạng màu sắc chuyên nghiệp
    """
    # 1. Lấy dữ liệu thực tế từ DB
    raw_data = Repository.get_all_transactions_for_report(user_id)
    current_prices = Repository.get_current_prices()
    
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book

    # --- HỆ THỐNG ĐỊNH DẠNG ---
    title_fmt = workbook.add_format({'bold': True, 'font_size': 20, 'font_color': '#1F4E78', 'align': 'center', 'valign': 'vcenter'})
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#2F75B5', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
    money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})
    roi_fmt = workbook.add_format({'num_format': '0.00%', 'border': 1})
    border_fmt = workbook.add_format({'border': 1})
    
    # Định dạng màu sắc Lãi/Lỗ
    green_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1, 'font_color': '#006100', 'bg_color': '#C6EFCE'})
    red_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1, 'font_color': '#9C0006', 'bg_color': '#FFC7CE'})

    # --- 2. XỬ LÝ LOGIC DANH MỤC ---
    portfolio = {}
    total_in = 0
    total_out = 0
    for trx in raw_data:
        t = trx['ticker']
        val = trx.get('total_value', 0)
        if trx['type'] in ['IN', 'DEPOSIT']: total_in += val
        elif trx['type'] in ['OUT', 'WITHDRAW']: total_out += val
        
        if t not in portfolio:
            portfolio[t] = {'qty': 0, 'cost': 0, 'type': trx.get('asset_type', 'OTHER')}
        
        p = portfolio[t]
        if trx['type'] == 'BUY':
            new_qty = p['qty'] + trx['qty']
            if new_qty > 0:
                p['cost'] = (p['qty'] * p['cost'] + val) / new_qty
            p['qty'] = new_qty
        elif trx['type'] == 'SELL':
            p['qty'] -= trx['qty']
            if p['qty'] <= 0: p['qty'] = 0; p['cost'] = 0

    portfolio_list = []
    for t, v in portfolio.items():
        if v['qty'] > 0:
            curr_p = current_prices.get(t, v['cost'])
            mv = v['qty'] * curr_p
            cv = v['qty'] * v['cost']
            pnl = mv - cv
            portfolio_list.append({
                'Mã TS': t, 'Loại': v['type'], 'Số lượng': v['qty'], 
                'Giá vốn': v['cost'], 'Giá TT': curr_p,
                'Vốn đầu tư': cv, 'Giá trị TT': mv, 'P&L': pnl,
                'ROI %': (pnl / cv) if cv > 0 else 0
            })
    
    df_port = pd.DataFrame(portfolio_list)
    aum = df_port['Giá trị TT'].sum() if not df_port.empty else 0
    net_inv = total_in - total_out

    # --- SHEET 1: 📊 DASHBOARD ---
    ws_dash = workbook.add_worksheet('📊 Dashboard')
    ws_dash.hide_gridlines(2)
    ws_dash.merge_range('A1:I2', 'HỆ THỐNG PHÂN TÍCH TÀI CHÍNH QUẢN TRỊ', title_fmt)
    
    # Bảng chỉ số tóm tắt (Kẻ bảng đầy đủ)
    summary_headers = ['GIÁ TRỊ TÀI SẢN (AUM)', 'VỐN THỰC NẠP', 'LỢI NHUẬN TẠM TÍNH', 'ROI TỔNG HỆ THỐNG']
    total_pnl = aum - net_inv
    total_roi = (total_pnl / net_inv) if net_inv > 0 else 0
    summary_vals = [aum, net_inv, total_pnl, total_roi]

    for col, (header, val) in enumerate(zip(summary_headers, summary_vals)):
        ws_dash.write(3, col*2 + 1, header, header_fmt)
        fmt = money_fmt if col < 3 else roi_fmt
        ws_dash.write(4, col*2 + 1, val, fmt)

    # VẼ BIỂU ĐỒ
    if not df_port.empty:
        # Dữ liệu ẩn cho biểu đồ tròn
        summary_cat = df_port.groupby('Loại')['Giá trị TT'].sum().reset_index()
        for i, row in summary_cat.iterrows():
            ws_dash.write(30+i, 15, row['Loại'])
            ws_dash.write(30+i, 16, row['Giá trị TT'])

        # BIỂU ĐỒ 1: PIE CHART (CƠ CẤU)
        pie = workbook.add_chart({'type': 'pie'})
        pie.add_series({
            'name': 'Cơ cấu Tài sản',
            'categories': ['📊 Dashboard', 30, 15, 30+len(summary_cat)-1, 15],
            'values':     ['📊 Dashboard', 30, 16, 30+len(summary_cat)-1, 16],
            'data_labels': {'percentage': True, 'position': 'outside_end'}
        })
        pie.set_title({'name': 'Tỷ trọng Phân bổ Tài sản'})
        ws_dash.insert_chart('B7', pie, {'x_scale': 1.1, 'y_scale': 1.1})

        # BIỂU ĐỒ 2: COLUMN CHART (SO SÁNH VỐN GỐC & GIÁ TRỊ THỰC)
        col_chart = workbook.add_chart({'type': 'column'})
        col_chart.add_series({
            'name': 'Vốn gốc đầu tư',
            'values': ['📊 Dashboard', 4, 3], # Lấy từ ô Vốn thực nạp
            'fill': {'color': '#ADB9CA'}
        })
        col_chart.add_series({
            'name': 'Giá trị hiện tại',
            'values': ['📊 Dashboard', 4, 1], # Lấy từ ô AUM
            'fill': {'color': '#4472C4'}
        })
        col_chart.set_title({'name': 'Hiệu quả sử dụng vốn'})
        ws_dash.insert_chart('F7', col_chart, {'x_scale': 1.1, 'y_scale': 1.1})

    # --- SHEET 2: 💼 DANH MỤC (KẺ BẢNG + BỘ LỌC) ---
    if not df_port.empty:
        df_port.to_excel(writer, sheet_name='💼 Danh Mục', index=False)
        ws_p = writer.sheets['💼 Danh Mục']
        
        # Thêm Auto-Filter
        ws_p.autofilter(0, 0, len(df_port), len(df_port.columns) - 1)
        
        # Kẻ bảng & Định dạng cột
        ws_p.set_column('A:C', 15, border_fmt)
        ws_p.set_column('D:G', 18, money_fmt)
        ws_p.set_column('H:H', 18, money_fmt)
        ws_p.set_column('I:I', 12, roi_fmt)
        
        # Format tiêu đề bảng
        for col_num, value in enumerate(df_port.columns.values):
            ws_p.write(0, col_num, value, header_fmt)

        # Conditional Formatting cho P&L (Cột H - index 7)
        ws_p.conditional_format(1, 7, len(df_port), 7, {'type': 'cell', 'criteria': '>=', 'value': 0, 'format': green_fmt})
        ws_p.conditional_format(1, 7, len(df_port), 7, {'type': 'cell', 'criteria': '<', 'value': 0, 'format': red_fmt})

    # --- SHEET 3: 📝 NHẬT KÝ (KẺ BẢNG + BỘ LỌC) ---
    df_tx = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
    if not df_tx.empty:
        df_tx.to_excel(writer, sheet_name='📝 Nhật Ký', index=False)
        ws_tx = writer.sheets['📝 Nhật Ký']
        ws_tx.autofilter(0, 0, len(df_tx), len(df_tx.columns) - 1)
        ws_tx.freeze_panes(1, 0)
        # Format tiêu đề & Kẻ bảng
        for col_num, value in enumerate(df_tx.columns.values):
            ws_tx.write(0, col_num, value, header_fmt)
        ws_tx.set_column('A:J', 18, border_fmt)

    writer.close()
    output.seek(0)
    return output
