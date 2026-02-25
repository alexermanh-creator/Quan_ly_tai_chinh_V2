# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        """Lưu giao dịch với các tham số đã đồng bộ chuẩn CTO"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ''', (user_id, ticker.upper(), asset_type.upper(), qty, price, total_value, type.upper()))
            conn.commit()

    @staticmethod
    def get_latest_transactions(user_id, limit=10, offset=0, asset_type=None, search_query=None):
        """Truy vấn lịch sử với Phân trang và Tìm kiếm"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM transactions WHERE user_id = ?"
            params = [user_id]

            if asset_type:
                query += " AND asset_type = ?"
                params.append(asset_type)
            
            if search_query:
                query += " AND ticker LIKE ?"
                params.append(f"%{search_query.upper()}%")

            query += " ORDER BY date DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_transaction_by_id(trx_id):
        """Lấy chi tiết 1 giao dịch để Sửa/Xóa"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transactions WHERE id = ?", (trx_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def delete_transaction(trx_id):
        """Xóa vĩnh viễn 1 giao dịch theo ID"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transactions WHERE id = ?", (trx_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def update_transaction(trx_id, qty, price, total_value):
        """Cập nhật lại số liệu của 1 giao dịch"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE transactions 
                SET qty = ?, price = ?, total_value = ?, date = datetime('now', 'localtime')
                WHERE id = ?
            ''', (qty, price, total_value, trx_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def undo_last_transaction(user_id):
        """Hàm cũ: Hoàn tác lệnh cuối cùng"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM transactions 
                WHERE id = (SELECT MAX(id) FROM transactions WHERE user_id = ?)
            ''', (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def get_available_cash(user_id):
        """Đếm số dư Tiền mặt khả dụng để chặn vung tay quá trán"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT SUM(
                    CASE 
                        WHEN type IN ('IN', 'DEPOSIT', 'SELL', 'CASH_DIVIDEND') THEN total_value
                        WHEN type IN ('OUT', 'WITHDRAW', 'BUY') THEN -total_value
                        ELSE 0
                    END
                ) as balance
                FROM transactions WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            return result['balance'] if result and result['balance'] else 0
