# backend/database/db_manager.py
import sqlite3
import os
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self, db_path='data/finance_manager.db'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._auto_migrate() # Tự động nâng cấp khi chạy trên Railway

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row 
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Khởi tạo cấu trúc bảng chuẩn"""
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
                    type TEXT, -- BUY, SELL, TRANSFER_IN, TRANSFER_OUT
                    date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 2. Bảng Portfolio
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio (
                    user_id INTEGER,
                    ticker TEXT,
                    asset_type TEXT,
                    total_qty REAL DEFAULT 0,
                    avg_price REAL DEFAULT 0,
                    market_price REAL DEFAULT 0, -- Sẽ được cập nhật tự động ở bước migrate
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, ticker)
                )
            ''')

            # 3. Các bảng bổ trợ
            tables = [
                'manual_prices (ticker TEXT PRIMARY KEY, current_price REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)',
                'stock_prices (ticker TEXT PRIMARY KEY, current_price REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)',
                'crypto_prices (symbol TEXT PRIMARY KEY, price_usd REAL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)',
                'settings (key TEXT PRIMARY KEY, value TEXT, user_id INTEGER)'
            ]
            
            for table_def in tables:
                cursor.execute(f'CREATE TABLE IF NOT EXISTS {table_def}')
            
            conn.commit()

    def _auto_migrate(self):
        """Bọc thép Railway: Tự động thêm cột thiếu mà không cần can thiệp thủ công"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Kiểm tra cột market_price
                cursor.execute("SELECT market_price FROM portfolio LIMIT 1")
            except sqlite3.OperationalError:
                print("🛠 Railway Alert: Đang nâng cấp bảng portfolio, thêm cột market_price...")
                try:
                    cursor.execute("ALTER TABLE portfolio ADD COLUMN market_price REAL DEFAULT 0")
                    conn.commit()
                    print("✅ Nâng cấp Database thành công!")
                except Exception as e:
                    print(f"❌ Lỗi nâng cấp: {e}")
        
        print("🚀 Database Engine: Trạng thái Sẵn sàng (V2.0 Bọc thép).")

db = DatabaseManager()
