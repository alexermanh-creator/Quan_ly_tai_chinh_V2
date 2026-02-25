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
        """Khởi tạo cấu trúc bảng chuẩn CTO - Đã bổ sung manual_prices"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Bảng giao dịch
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
            
            # --- MIGRATION: Xử lý cột qty ---
            try:
                cursor.execute("SELECT qty FROM transactions LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    cursor.execute("ALTER TABLE transactions RENAME COLUMN amount TO qty")
                    print("✅ Đã cập nhật: Đổi tên cột 'amount' thành 'qty'")
                except:
                    cursor.execute("ALTER TABLE transactions ADD COLUMN qty REAL DEFAULT 0")
                    print("✅ Đã cập nhật: Thêm cột 'qty' mới")
            
            # 2. BẢNG GIÁ THỦ CÔNG (Dứt điểm lỗi crash Stock Module)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS manual_prices (
                    ticker TEXT PRIMARY KEY, 
                    current_price REAL, 
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 3. Các bảng phụ trợ
            cursor.execute('CREATE TABLE IF NOT EXISTS stock_prices (ticker TEXT PRIMARY KEY, current_price REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)')
            cursor.execute('CREATE TABLE IF NOT EXISTS crypto_prices (symbol TEXT PRIMARY KEY, price_usd REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)')
            cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, user_id INTEGER)')
            
            conn.commit()
            print("🚀 Database initialized: All tables are ready.")

db = DatabaseManager()
