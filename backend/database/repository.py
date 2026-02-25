# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        """Lưu giao dịch với các tham số đã đồng bộ chuẩn CTO"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Đảm bảo các cột: user_id, ticker, asset_type, qty, price, total_value, type
            cursor.execute('''
                INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (user_id, ticker.upper(), asset_type.upper(), qty, price, total_value, type.upper()))
            conn.commit()

    @staticmethod
    def undo_last_transaction(user_id):
        """Xóa lệnh cuối cùng của user"""
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
            # Sử dụng row_factory để truy cập theo tên cột nếu db_manager hỗ trợ
            cursor.execute('''
                SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT ?
            ''', (user_id, limit))
            return cursor.fetchall()
