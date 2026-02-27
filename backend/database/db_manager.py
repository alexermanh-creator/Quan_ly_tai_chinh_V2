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
        """Khởi tạo cấu trúc bảng chuẩn - Loại bỏ migration thừa, tập trung vào hiệu suất"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Bảng giao dịch: Dùng 'qty' làm chuẩn ngay từ đầu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    asset_type TEXT,
                    qty REAL,
                    price REAL,
                    total_value REAL,
                    type TEXT, -- BUY, SELL, DEPOSIT, WITHDRAW
                    date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 2. Bảng Portfolio: Lưu trạng thái tài sản hiện tại của User
            # Giúp truy vấn lệnh /balance hoặc /portfolio cực nhanh
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio (
                    user_id INTEGER,
                    ticker TEXT,
                    asset_type TEXT,
                    total_qty REAL DEFAULT 0,
                    avg_price REAL DEFAULT 0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, ticker)
                )
            ''')

            # 3. Các bảng giá (Gộp chung logic lưu trữ giá)
            # manual_prices dành cho cập nhật tay, stock/crypto dành cho API
            tables = [
                'manual_prices (ticker TEXT PRIMARY KEY, current_price REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)',
                'stock_prices (ticker TEXT PRIMARY KEY, current_price REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)',
                'crypto_prices (symbol TEXT PRIMARY KEY, price_usd REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)',
                'settings (key TEXT PRIMARY KEY, value TEXT, user_id INTEGER)'
            ]
            
            for table_def in tables:
                cursor.execute(f'CREATE TABLE IF NOT EXISTS {table_def}')
            
            conn.commit()
            print("🚀 Database Engine: Trạng thái Sẵn sàng (Logic đã hợp nhất).")

db = DatabaseManager()
