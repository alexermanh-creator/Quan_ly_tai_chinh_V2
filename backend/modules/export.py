# backend/modules/export.py
import pandas as pd
import io
from datetime import datetime
import xlsxwriter
from backend.database.repository import Repository

def generate_excel_report(user_id):
    """Cỗ máy xuất Excel Pro tích hợp Dashboard và Phân tích danh mục"""
    raw_data = Repository.get_all_transactions_for_report(user_id)
    current_prices = Repository.get_current_prices()
    
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book

    # --- ĐỊNH DẠNG (FORMATTING) ---
    title_fmt = workbook.add_format({'bold': True, 'font_size': 16, 'color': '#1F4E78', 'align': 'center'})
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1, 'align': 'center'})
    money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})
    pct_fmt = workbook.add_format({'num_format': '0.00%', 'border': 1})
    border_fmt = workbook.add_format({'border': 1})

    # --- XỬ LÝ DỮ LIỆU ---
    df_tx = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
    
    # Tính toán Portfolio thực tế
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

    portfolio_list = []
    for t, v in portfolio.items():
        if v['qty'] > 0:
            curr_p = current_prices.get(t, v['cost'])
            market_val = v['qty'] * curr_p
            cost_val = v['qty'] * v['cost']
            pnl = market_val - cost_val
            portfolio_list.append({
                'Mã': t, 'Loại': v['type'], 'Số lượng': v['qty'], 
                'Giá vốn': v['cost'], 'Giá hiện tại': curr_p,
                'Tổng vốn đầu tư': cost_val, 'Giá trị thị trường': market_val,
                'Lãi/Lỗ tạm tính': pnl, '% Lãi/Lỗ': pnl/cost_val if cost_val > 0 else 0
            })
    df_port = pd.DataFrame(portfolio_list)

    # --- SHEET 1: DASHBOARD ---
    ws_dash = workbook.add_worksheet('📊 Dashboard')
    ws_dash.hide_gridlines(2)
    ws_dash.merge_range('A1:H1', 'BÁO CÁO TÀI CHÍNH QUẢN TRỊ', title_fmt)
    
    # Bảng Summary nhanh
    ws_dash.write('B3', 'TỔNG TÀI SẢN (AUM)', header_fmt)
    ws_dash.write('C3', 'VỐN RÒNG THỰC NẠP', header_fmt)
    ws_dash.write('D3', 'P&L TỔNG HỢP', header_fmt)
    
    aum = df_port['Giá trị thị trường'].sum() if not df_port.empty else 0
    net_invested = total_in - total_out
    ws_dash.write('B4', aum, money_fmt)
    ws_dash.write('C4', net_invested, money_fmt)
    ws_dash.write('D4', aum - net_invested if net_invested > 0 else 0, money_fmt)

    # Vẽ Biểu đồ phân bổ
    if not df_port.empty:
        summary_cat = df_port.groupby('Loại')['Giá trị thị trường'].sum().reset_index()
        for i, row in summary_cat.iterrows():
            ws_dash.write(i+20, 10, row['Loại'])
            ws_dash.write(i+20, 11, row['Giá trị thị trường'])
        
        pie_chart = workbook.add_chart({'type': 'pie'})
        pie_chart.add_series({
            'name': 'Cơ cấu Tài sản',
            'categories': ['📊 Dashboard', 20, 10, 20 + len(summary_cat)-1, 10],
            'values':     ['📊 Dashboard', 20, 11, 20 + len(summary_cat)-1, 11],
            'data_labels': {'percentage': True, 'position': 'outside_end'},
        })
        pie_chart.set_title({'name': 'Tỷ trọng Danh mục'})
        ws_dash.insert_chart('B6', pie_chart)

    # --- SHEET 2: CHI TIẾT DANH MỤC ---
    if not df_port.empty:
        df_port.to_excel(writer, sheet_name='💼 Danh Mục', index=False)
        ws_p = writer.sheets['💼 Danh Mục']
        ws_p.set_column('A:E', 12, border_fmt)
        ws_p.set_column('F:H', 20, money_fmt)
        ws_p.set_column('I:I', 15, pct_fmt)

    # --- SHEET 3: NHẬT KÝ GIAO DỊCH ---
    df_tx.to_excel(writer, sheet_name='📝 Nhật Ký', index=False)
    ws_tx = writer.sheets['📝 Nhật Ký']
    ws_tx.set_column('B:B', 20)
    ws_tx.set_column('H:I', 15, money_fmt)

    writer.close()
    output.seek(0)
    return output
