# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def get_user_asset_types(user_id):
        """Lấy danh sách các loại tài sản mà người dùng thực tế đang sở hữu"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT asset_type FROM transactions WHERE user_id = ?", (user_id,))
            return [row['asset_type'] for row in cursor.fetchall()]

    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_val, t_type='BUY'):
        """Lưu một giao dịch mới vào Database"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (user_id, ticker, asset_type, amount, price, total_value, type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, ticker.upper(), asset_type.upper(), qty, price, total_val, t_type.upper()))
            conn.commit()

    @staticmethod
    def get_latest_transactions(user_id, limit=10):
        """Lấy danh sách các giao dịch gần nhất để hiển thị lịch sử"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM transactions 
                WHERE user_id = ? 
                ORDER BY date DESC LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
