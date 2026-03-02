import os
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_PATH = "data/finance_v2.db"

# Tỷ giá bọc thép
RATE_CRYPTO = 25000  # 1 USD = 25.000 VNĐ
RATE_STOCK = 1000    # Nhân 1000 cho giá cổ phiếu (vd: 80 -> 80,000)
