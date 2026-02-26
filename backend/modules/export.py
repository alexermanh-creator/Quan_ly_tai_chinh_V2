import pandas as pd
import io
from datetime import datetime
import xlsxwriter
from backend.database import repository

def generate_excel_report(user_id):
    # 1. Lấy dữ liệu từ DB (Dùng hàm bọc thép lấy toàn bộ để tính giá vốn)
    raw_data = repository.get_all_transactions_for_report(user_id)
    
    # 2. Tạo Buffer để lưu file trên RAM
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book

    # 3. Tạo các định dạng (Formatting)
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
    money_fmt = workbook.add_format({'num_format': '#,##0', 'align': 'right'})
    title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'color': '#203764'})

    # --- SHEET 3: NHẬT KÝ GIAO DỊCH (RAW DATA) ---
    df_tx = pd.DataFrame(raw_data) if raw_data else pd.DataFrame(columns=['ID', 'Ngày', 'Loại', 'Mã', 'Tiền'])
    df_tx.to_excel(writer, sheet_name='Raw_Transactions', index=False)
    ws_raw = writer.sheets['Raw_Transactions']
    ws_raw.freeze_panes(1, 0) # Đóng băng dòng đầu

    # --- SHEET 1: DASHBOARD ---
    ws_dash = workbook.add_worksheet('📊 Dashboard')
    ws_dash.hide_gridlines(2)
    ws_dash.write('A1', 'BÁO CÁO TÀI CHÍNH THÀNH AN', title_fmt)
    
    # Giả định data tóm tắt để vẽ biểu đồ (Sếp có thể dùng groupby từ df_tx)
    summary_data = [['Phân khúc', 'Giá trị'], ['Stock', 60], ['Crypto', 20], ['Khác', 20]]
    for r, row in enumerate(summary_data):
        ws_dash.write_row(r + 10, 10, row) # Ghi vào vùng tạm để vẽ chart

    # Vẽ Biểu đồ Tròn (Pie Chart)
    chart = workbook.add_chart({'type': 'pie'})
    chart.add_series({
        'name': 'Cơ cấu Tài sản',
        'categories': "='📊 Dashboard'!$K$12:$K$14",
        'values':     "='📊 Dashboard'!$L$12:$L$14",
        'data_labels': {'percentage': True},
    })
    ws_dash.insert_chart('A4', chart)

    writer.close()
    output.seek(0)
    return output
