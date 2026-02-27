# main.py
import os
import sys
import logging
from dotenv import load_dotenv

# Đảm bảo Python tìm thấy các module trong thư mục dự án
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Telegram.bot_client import bot_app

# 1. Tải cấu hình
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_USER_ID")

# Cấu hình logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    """
    Điểm khởi đầu của hệ thống.
    Kết nối Bot với các Module nghiệp vụ.
    """
    if not TOKEN:
        print("❌ LỖI: Thiếu TELEGRAM_BOT_TOKEN trong cấu hình Railway/Environment.")
        return

    print(f"🚀 Bot Finance v2.0 - Khởi động cho Admin: {ADMIN_ID}")
    
    # Khởi chạy bot (bot_app đã chứa các handler được hợp nhất từ bản cũ)
    bot_app.run()

if __name__ == '__main__':
    main()
