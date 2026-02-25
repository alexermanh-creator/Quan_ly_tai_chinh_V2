# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def get_all_asset_types(user_id):
        """Lấy danh sách các loại tài sản mà user đang sở hữu"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT asset_type FROM transactions WHERE user_id = ?", (user_id,))
            return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_val, t_type='BUY'):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (user_id, ticker, asset_type, amount, price, total_value, type, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (user_id, ticker.upper(), asset_type.upper(), qty, price, total_val, t_type))
            conn.commit()