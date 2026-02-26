# backend/modules/export.py
import pandas as pd
import io
from datetime import datetime
import xlsxwriter
from backend.database.repository import Repository # Hợp nhất: Import Class chính xác

def generate_excel_report(user_id):
    # 1. Gọi hàm thông qua Class (Static Method)
    raw_data = Repository.get_all_transactions_for_report(user_id)
    
    # 2. Tạo Buffer để lưu file trên RAM
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book

    # 3. Tạo các định dạng (Formatting)
    money_fmt = workbook.add_format({'num_format': '#,##0', 'align': 'right'})
    title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'color': '#203764'})

    # --- SHEET: NHẬT KÝ GIAO DỊCH (RAW DATA) ---
    # Chuyển dữ liệu sang DataFrame
    df_tx = pd.DataFrame(raw_data) if raw_data else pd.DataFrame(columns=['id', 'date', 'type', 'ticker', 'total_value'])
    
    # Ghi dữ liệu thực tế vào Sheet
    df_tx.to_excel(writer, sheet_name='Raw_Transactions', index=False)
    ws_raw = writer.sheets['Raw_Transactions']
    ws_raw.freeze_panes(1, 0)
    ws_raw.set_column('A:J', 15)

    # --- SHEET: DASHBOARD ---
    ws_dash = workbook.add_worksheet('📊 Dashboard')
    ws_dash.hide_gridlines(2)
    ws_dash.write('A1', 'BÁO CÁO TÀI CHÍNH THÀNH AN', title_fmt)
    ws_dash.write('A2', f'Trích xuất: {datetime.now().strftime("%d/%m/%Y %H:%M")}')
    
    # 4. Vẽ biểu đồ từ dữ liệu thật
    if not df_tx.empty and 'asset_type' in df_tx.columns:
        # Group by để lấy tỷ trọng
        summary = df_tx.groupby('asset_type')['total_value'].sum().reset_index()
        
        # Ghi dữ liệu summary vào vùng tạm (Cột K, L)
        start_row = 10
        for i, row in summary.iterrows():
            ws_dash.write(start_row + i, 10, row['asset_type'])
            ws_dash.write(start_row + i, 11, row['total_value'])

        # Tạo Biểu đồ Tròn
        chart = workbook.add_chart({'type': 'pie'})
        chart.add_series({
            'name': 'Cơ cấu Tài sản',
            'categories': ['📊 Dashboard', start_row, 10, start_row + len(summary) - 1, 10],
            'values':     ['📊 Dashboard', start_row, 11, start_row + len(summary) - 1, 11],
            'data_labels': {'percentage': True, 'leader_lines': True},
        })
        chart.set_title({'name': 'Tỷ trọng Phân bổ Tài sản'})
        ws_dash.insert_chart('B5', chart)

    writer.close()
    output.seek(0)
    return output
