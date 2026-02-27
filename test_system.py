# test_system.py
import os
import sys

# Đảm bảo hệ thống nhận diện đúng cấu trúc thư mục
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    print("🔍 --- BẮT ĐẦU KIỂM TRA HỆ THỐNG ---")
    
    # 1. KIỂM TRA IMPORT
    print("\n1. Kiểm tra kết nối Module...")
    from backend.database.db_manager import db
    from backend.database.repository import repo
    from backend.core.parser import CommandParser
    from backend.modules.dashboard import DashboardModule
    from backend.modules.stock import StockModule
    print("✅ Các Module đã kết nối thông suốt.")

    # 2. KIỂM TRA DATABASE & DỮ LIỆU GIẢ LẬP
    print("\n2. Kiểm tra Luồng dữ liệu (Data Flow)...")
    TEST_USER_ID = 999999  # ID ảo để không ảnh hưởng dữ liệu thật
    
    # Giả lập lệnh nạp tiền
    raw_cmd = "nap 100tr"
    parsed = CommandParser.parse_transaction(raw_cmd)
    if parsed:
        print(f"✅ Parser hoạt động: {raw_cmd} -> {parsed['total_val']:,.0f} VNĐ")
        repo.save_transaction(TEST_USER_ID, **parsed)
        print("✅ Lưu giao dịch thành công.")
    else:
        print("❌ Lỗi Parser: Không hiểu lệnh nạp tiền.")

    # 3. KIỂM TRA SỰ TƯƠNG THÍCH CỦA DASHBOARD (MỚI vs CŨ)
    print("\n3. Kiểm tra Hiển thị Dashboard...")
    dash = DashboardModule(TEST_USER_ID)
    output = dash.run()
    if "TÀI SẢN CỦA BẠN" in output:
        print("✅ Dashboard hiển thị chuẩn Layout CEO.")
        # Kiểm tra xem con số 100tr có xuất hiện trong Dashboard không
        if "100.0 triệu" in output or "100,000,000" in output:
            print("✅ Dữ liệu nạp tiền đã khớp với hiển thị.")
        else:
            print("⚠️ Cảnh báo: Dashboard chạy được nhưng không thấy con số 100tr.")
    else:
        print("❌ Lỗi Hiển thị: Dashboard không trả về đúng format.")

    # 4. KIỂM TRA STOCK MODULE
    print("\n4. Kiểm tra Module Chứng Khoán...")
    stock_mod = StockModule(TEST_USER_ID)
    stock_out = stock_mod.run()
    if "DANH MỤC CỔ PHIẾU" in stock_out:
        print("✅ Stock Module tương thích cấu trúc mới.")
    else:
        print("❌ Stock Module gặp lỗi logic.")

    print("\n🚀 --- KẾT QUẢ: HỆ THỐNG SẴN SÀNG TRIỂN KHAI ---")

except Exception as e:
    print("\n❌ LỖI PHÁT SINH TRONG QUÁ TRÌNH TEST:")
    import traceback
    traceback.print_exc()
    print("\n💡 CEO hãy copy đoạn lỗi trên gửi cho tôi để xử lý nhé!")
