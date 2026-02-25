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
        """Khởi tạo cấu trúc bảng chuẩn CTO"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Bảng giao dịch: Dùng 'qty' thay vì 'amount' để đồng bộ toàn hệ thống
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    asset_type TEXT,
                    qty REAL,
                    price REAL,
                    total_value REAL,
                    type TEXT,
                    date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # --- MIGRATION: Tự động sửa lỗi nếu database cũ đang dùng 'amount' ---
            try:
                # Kiểm tra xem cột qty đã tồn tại chưa
                cursor.execute("SELECT qty FROM transactions LIMIT 1")
            except sqlite3.OperationalError:
                # Nếu chưa có qty, tiến hành đổi tên cột amount thành qty (hoặc thêm mới)
                try:
                    cursor.execute("ALTER TABLE transactions RENAME COLUMN amount TO qty")
                    print("✅ Đã cập nhật: Đổi tên cột 'amount' thành 'qty'")
                except:
                    cursor.execute("ALTER TABLE transactions ADD COLUMN qty REAL DEFAULT 0")
                    print("✅ Đã cập nhật: Thêm cột 'qty' mới")
            
            cursor.execute('CREATE TABLE IF NOT EXISTS stock_prices (ticker TEXT PRIMARY KEY, current_price REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)')
            cursor.execute('CREATE TABLE IF NOT EXISTS crypto_prices (symbol TEXT PRIMARY KEY, price_usd REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)')
            cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, user_id INTEGER)')
            conn.commit()

db = DatabaseManager()
