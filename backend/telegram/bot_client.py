import telebot
import sys
import os

# Đảm bảo có thể import từ config ở thư mục gốc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config import TOKEN

if not TOKEN:
    print("❌ LỖI: Chưa tìm thấy TELEGRAM_BOT_TOKEN trong file .env")
    sys.exit(1)

# Khởi tạo thực thể bot duy nhất (Singleton)
bot = telebot.TeleBot(TOKEN)
