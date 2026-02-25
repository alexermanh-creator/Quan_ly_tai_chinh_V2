# backend/database/db_manager.py
import sqlite3
import os
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self, db_path='data/finance_manager.db'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row 
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Khởi tạo cấu trúc bảng - Không phụ thuộc vào bất kỳ Module nào khác"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Bảng giao dịch
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    asset_type TEXT,
                    amount REAL,
                    price REAL,
                    total_value REAL,
                    type TEXT,
                    date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Bảng giá
            cursor.execute('CREATE TABLE IF NOT EXISTS stock_prices (ticker TEXT PRIMARY KEY, current_price REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)')
            cursor.execute('CREATE TABLE IF NOT EXISTS crypto_prices (symbol TEXT PRIMARY KEY, price_usd REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)')
            cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, user_id INTEGER)')
            conn.commit()

db = DatabaseManager()
