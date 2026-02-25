import sqlite3
import os
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self, db_path='data/finance_manager.db'):
        self.db_path = db_path
        # Đảm bảo thư mục data luôn tồn tại
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Cung cấp connection dưới dạng context manager để tự đóng sau khi dùng"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Cho phép truy cập dữ liệu theo tên cột
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Khởi tạo cấu trúc bảng vạn năng cho Version 2.0"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Bảng Giao dịch chung (Tất cả Stock, Crypto, Gold đều lưu ở đây)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    asset_type TEXT, -- STOCK, CRYPTO, GOLD...
                    amount REAL,
                    price REAL,
                    total_value REAL,
                    type TEXT,       -- BUY, SELL, DIVIDEND, IN, OUT
                    date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 2. Bảng giá Cổ phiếu (Thị trường VN)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_prices (
                    ticker TEXT PRIMARY KEY,
                    current_price REAL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 3. Bảng giá Crypto (Giá USD)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crypto_prices (
                    symbol TEXT PRIMARY KEY,
                    price_usd REAL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()

# Khởi tạo instance dùng chung cho toàn bộ ứng dụng
db = DatabaseManager()
