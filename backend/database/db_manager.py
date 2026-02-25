# backend/database/db_manager.py
import sqlite3
import os
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self, db_path='data/finance_manager.db'):
        self.db_path = db_path
        # Tự động tạo thư mục data nếu chưa có
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Quản lý kết nối an toàn, tự động đóng sau khi dùng"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Giúp truy cập dữ liệu theo tên cột như Dictionary
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Khởi tạo cấu trúc bảng đạt chuẩn tài chính"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Bảng Giao dịch (Lõi hệ thống)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    asset_type TEXT,
                    amount REAL,        -- Số lượng (qty)
                    price REAL,         -- Giá đơn vị
                    total_value REAL,   -- Tổng giá trị (qty * price hoặc số tiền mặt)
                    type TEXT,          -- BUY, SELL, CASH_DIVIDEND, DIVIDEND_STOCK
                    date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 2. Bảng Giá Cổ phiếu (Cập nhật từ API/Crawler)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_prices (
                    ticker TEXT PRIMARY KEY,
                    current_price REAL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 3. Bảng Giá Crypto
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crypto_prices (
                    symbol TEXT PRIMARY KEY,
                    price_usd REAL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 4. Bảng Cài đặt (Lưu tỷ giá VND/USD và các config khác)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    user_id INTEGER
                )
            ''')
            
            conn.commit()

# Khởi tạo instance duy nhất để dùng toàn hệ thống
db = DatabaseManager()
