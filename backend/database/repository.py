# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        """Lưu giao dịch với các tham số đã đồng bộ chuẩn CTO"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Sử dụng đúng tên cột 'qty' đã khởi tạo trong db_manager
            cursor.execute('''
                INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ''', (user_id, ticker.upper(), asset_type.upper(), qty, price, total_value, type.upper()))
            conn.commit()

    @staticmethod
    def undo_last_transaction(user_id):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM transactions 
                WHERE id = (SELECT MAX(id) FROM transactions WHERE user_id = ?)
            ''', (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def get_latest_transactions(user_id, limit=10):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT ?
            ''', (user_id, limit))
            # Chuyển đổi Row sang dict để dễ xử lý ở Dashboard
            return [dict(row) for row in cursor.fetchall()]
