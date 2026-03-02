import sqlite3
import os
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self, db_path='data/finance_manager.db'):
        self.db_path = db_path
        # Đảm bảo thư mục data tồn tại
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Cung cấp connection dưới dạng context manager để tự động đóng"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Giúp truy xuất dữ liệu theo tên cột
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Khởi tạo cấu trúc bảng vạn năng (V2)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Bảng Giao dịch chung (Universal Transactions)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    asset_type TEXT, -- STOCK, CRYPTO, GOLD...
                    amount REAL,
                    price REAL,
                    total_value REAL,
                    type TEXT,       -- BUY, SELL, DIVIDEND, DIVIDEND_STOCK, IN, OUT
                    date DATETIME
                )
            ''')

            # 2. Bảng giá Cổ phiếu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_prices (
                    ticker TEXT PRIMARY KEY,
                    current_price REAL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 3. Bảng giá Crypto (hoặc các tài sản tính theo USD)
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