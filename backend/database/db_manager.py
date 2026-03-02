import sqlite3, os
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
        try: yield conn
        finally: conn.close()

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Bảng giao dịch & Portfolio
            cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ticker TEXT, asset_type TEXT, qty REAL, price REAL, total_value REAL, type TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS portfolio (user_id INTEGER, ticker TEXT, asset_type TEXT, total_qty REAL DEFAULT 0, avg_price REAL DEFAULT 0, last_updated DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, ticker))''')
            # BỌC THÉP: Tự động thêm cột market_price nếu Railway chưa có
            try: cursor.execute("ALTER TABLE portfolio ADD COLUMN market_price REAL DEFAULT 0")
            except: pass 
            conn.commit()

db = DatabaseManager()
