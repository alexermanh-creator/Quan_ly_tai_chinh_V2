# backend/modules/export.py
import pandas as pd
import io
from datetime import datetime
import xlsxwriter
from backend.database.repository import Repository

def generate_excel_report(user_id):
    raw_data = Repository.get_all_transactions_for_report(user_id)
    current_prices = Repository.get_current_prices()
    
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book

    # --- HỆ THỐNG ĐỊNH DẠNG ---
    title_fmt = workbook.add_format({'bold': True, 'font_size': 20, 'font_color': '#1F4E78', 'align': 'center', 'valign': 'vcenter'})
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#2F75B5', 'font_color': 'white', 'border': 1, 'align': 'center'})
    money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})
    pct_fmt = workbook.add_format({'num_format': '0.0%', 'border': 1})
    green_fmt = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'border': 1, 'num_format': '#,##0'})
    red_fmt = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'border': 1, 'num_format': '#,##0'})

    # --- 1. LOGIC XỬ LÝ NÂNG CAO ---
    df_raw = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
    portfolio = {}
    cash_flow = {} # Cho tính năng 1: Phân tích dòng tiền tháng

    for trx in raw_data:
        t = trx['ticker']
        val = trx.get('total_value', 0)
        date_obj = datetime.strptime(trx['date'], '%Y-%m-%d %H:%M:%S')
        month_key = date_obj.strftime('%Y-%m')

        # Xử lý dòng tiền tháng
        if month_key not in cash_flow: cash_flow[month_key] = {'In': 0, 'Out': 0}
        if trx['type'] in ['IN', 'DEPOSIT']: cash_flow[month_key]['In'] += val
        elif trx['type'] in ['OUT', 'WITHDRAW']: cash_flow[month_key]['Out'] += val

        # Xử lý Portfolio
        if t not in portfolio: portfolio[t] = {'qty': 0, 'cost': 0, 'type': trx.get('asset_type', 'OTHER')}
        p = portfolio[t]
        if trx['type'] == 'BUY':
            new_qty = p['qty'] + trx['qty']
            if new_qty > 0: p['cost'] = (p['qty'] * p['cost'] + val) / new_qty
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
            portfolio_list.append({'Mã': t, 'Loại': v['type'], 'SL': v['qty'], 'Vốn': cv, 'Giá trị TT': mv, 'Lãi/Lỗ': pnl, 'ROI': pnl/cv if cv > 0 else 0})
    
    df_port = pd.DataFrame(portfolio_list)
    aum = df_port['Giá trị TT'].sum() if not df_port.empty else 0

    # --- SHEET 1: 📊 DASHBOARD ---
    ws_dash = workbook.add_worksheet('📊 Dashboard')
    ws_dash.hide_gridlines(2)
    ws_dash.merge_range('A1:I2', 'HỆ THỐNG QUẢN TRỊ TÀI CHÍNH CHI TIẾT', title_fmt)

    # Thẻ tóm tắt nhanh
    summary = [('TÀI SẢN (AUM)', aum), ('LÃI LỖ TỔNG', aum - sum(c['In']-c['Out'] for c in cash_flow.values()))]
    for i, (l, v) in enumerate(summary):
        ws_dash.write(3, i*2 + 1, l, header_fmt)
        ws_dash.write(4, i*2 + 1, v, money_fmt)

    # BIỂU ĐỒ 1: CƠ CẤU TÀI SẢN
    if not df_port.empty:
        summary_cat = df_port.groupby('Loại')['Giá trị TT'].sum().reset_index()
        for i, row in summary_cat.iterrows():
            ws_dash.write(40+i, 20, row['Loại']); ws_dash.write(40+i, 21, row['Giá trị TT'])
        chart1 = workbook.add_chart({'type': 'pie'})
        chart1.add_series({'categories': ['📊 Dashboard', 40, 20, 40+len(summary_cat)-1, 20], 'values': ['📊 Dashboard', 40, 21, 40+len(summary_cat)-1, 21]})
        ws_dash.insert_chart('B7', chart1)

    # --- SHEET 2: 💼 DANH MỤC & RỦI RO ---
    if not df_port.empty:
        df_port.to_excel(writer, sheet_name='💼 Danh Mục', index=False)
        ws_p = writer.sheets['💼 Danh Mục']
        ws_p.autofilter(0, 0, len(df_port), len(df_port.columns)-1)
        
        # Tính năng 3: Data Bars cho Giá trị thị trường
        ws_p.conditional_format(1, 4, len(df_port), 4, {'type': 'data_bar', 'bar_color': '#63C384'})
        
        # Tính năng 2: Quản trị rủi ro (Tô đỏ mã chiếm > 30% danh mục)
        for i in range(len(df_port)):
            weight = df_port.iloc[i]['Giá trị TT'] / aum if aum > 0 else 0
            if weight > 0.3:
                ws_p.write(i+1, 0, df_port.iloc[i]['Mã'], workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'bold': True}))

        ws_p.set_column('A:C', 12); ws_p.set_column('D:F', 18, money_fmt); ws_p.set_column('G:G', 12, pct_fmt)

    # --- SHEET 3: 📈 DÒNG TIỀN THÁNG (Tính năng 1) ---
    df_cf = pd.DataFrame([{'Tháng': k, 'Nạp': v['In'], 'Rút': v['Out'], 'Ròng': v['In']-v['Out']} for k, v in sorted(cash_flow.items())])
    df_cf.to_excel(writer, sheet_name='📈 Dòng Tiền', index=False)
    ws_cf = writer.sheets['📈 Dòng Tiền']
    ws_cf.set_column('A:D', 18, money_fmt)
    
    # Vẽ biểu đồ dòng tiền tháng
    cf_chart = workbook.add_chart({'type': 'column'})
    cf_chart.add_series({'name': 'Nạp', 'values': ['📈 Dòng Tiền', 1, 1, len(df_cf), 1]})
    cf_chart.add_series({'name': 'Rút', 'values': ['📈 Dòng Tiền', 1, 2, len(df_cf), 2]})
    ws_cf.insert_chart('F2', cf_chart)

    # --- SHEET 4: 📝 NHẬT KÝ ---
    df_raw.to_excel(writer, sheet_name='📝 Nhật Ký', index=False)
    writer.sheets['📝 Nhật Ký'].autofilter(0, 0, len(df_raw), len(df_raw.columns)-1)

    writer.close()
    output.seek(0)
    return output
