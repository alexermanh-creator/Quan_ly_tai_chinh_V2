# main.py
import os
import sys
import logging
from dotenv import load_dotenv

# 1. KHAI BÁO ĐƯỜNG DẪN GỐC (Phải chạy đầu tiên)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# 2. TẢI CẤU HÌNH BIẾN MÔI TRƯỜNG
load_dotenv()

# 3. CHỈ IMPORT BOT SAU KHI ĐÃ SET PATH
# Điều này giúp bot_client tìm thấy thư mục backend/
try:
    from Telegram.bot_client import bot_app
except ImportError as e:
    print(f"❌ Lỗi cấu trúc thư mục: {e}")
    # In ra path hiện tại để debug trên Railway nếu cần
    print(f"Dòng dẫn hiện tại: {sys.path}")
    raise

# Cấu hình logging chuyên nghiệp
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_ID = os.getenv("ADMIN_USER_ID")

    if not TOKEN:
        print("❌ LỖI: Thiếu TELEGRAM_BOT_TOKEN trên Railway/Env.")
        return

    print(f"🚀 Hệ điều hành Tài chính v2.0")
    print(f"📡 Kết nối Admin ID: {ADMIN_ID}")
    
    # Khởi chạy bot
    bot_app.run()

if __name__ == '__main__':
    main()
