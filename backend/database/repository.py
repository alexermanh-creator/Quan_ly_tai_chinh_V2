# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_val, t_type):
        """Lưu giao dịch với nhãn (type) linh hoạt"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (user_id, ticker, asset_type, amount, price, total_value, type, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (user_id, ticker.upper(), asset_type.upper(), qty, price, total_val, t_type.upper()))
            conn.commit()

    @staticmethod
    def undo_last_transaction(user_id):
        """Xóa lệnh cuối cùng của user - Cực kỳ quan trọng cho nút Undo"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM transactions 
                WHERE id = (SELECT MAX(id) FROM transactions WHERE user_id = ?)
            ''', (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def get_user_asset_types(user_id):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT UPPER(asset_type) as asset_type FROM transactions WHERE user_id = ?", (user_id,))
            return [row['asset_type'] for row in cursor.fetchall()]

    @staticmethod
    def get_latest_transactions(user_id, limit=10):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
