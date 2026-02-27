# backend/database/repository.py
from backend.database.db_manager import db
import sqlite3

class Repository:
    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        ticker = ticker.upper()
        asset_type = asset_type.upper()
        type = type.upper()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Lưu vào lịch sử giao dịch
            cursor.execute('''
                INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ''', (user_id, ticker, asset_type, qty, price, total_value, type))

            # 2. CẬP NHẬT BẢNG PORTFOLIO (Logic mới để tối ưu Dashboard)
            if asset_type != 'CASH':
                # Lấy dữ liệu hiện tại trong portfolio
                cursor.execute("SELECT total_qty, avg_price FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, ticker))
                row = cursor.fetchone()
                
                current_qty = row['total_qty'] if row else 0
                current_avg_price = row['avg_price'] if row else 0
                
                new_qty = current_qty
                new_avg_price = current_avg_price

                if type == 'BUY':
                    new_qty = current_qty + qty
                    # Công thức tính giá vốn bình quân (Weighted Average Cost)
                    if new_qty > 0:
                        new_avg_price = ((current_qty * current_avg_price) + total_value) / new_qty
                elif type == 'SELL':
                    new_qty = current_qty - qty
                elif type == 'DIVIDEND_STOCK':
                    new_qty = current_qty + qty
                    # Nhận cổ tức cổ phiếu làm giảm giá vốn
                    if new_qty > 0:
                        new_avg_price = (current_qty * current_avg_price) / new_qty

                # Cập nhật hoặc Thêm mới vào Portfolio
                cursor.execute('''
                    INSERT INTO portfolio (user_id, ticker, asset_type, total_qty, avg_price, last_updated)
                    VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
                    ON CONFLICT(user_id, ticker) DO UPDATE SET 
                        total_qty = excluded.total_qty,
                        avg_price = excluded.avg_price,
                        last_updated = excluded.last_updated
                ''', (user_id, ticker, asset_type, new_qty, new_avg_price))

            conn.commit()

    @staticmethod
    def get_available_cash(user_id):
        """Giữ nguyên logic tính tiền mặt từ transactions"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT SUM(CASE 
                    WHEN type IN ('IN', 'DEPOSIT', 'SELL', 'CASH_DIVIDEND') THEN total_value
                    WHEN type IN ('OUT', 'WITHDRAW', 'BUY') THEN -total_value
                    ELSE 0 END) as balance
                FROM transactions WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            return result['balance'] if result and result['balance'] else 0

    # ... Các hàm get_latest_transactions, delete_transaction giữ nguyên như bản cũ của bạn ...
    @staticmethod
    def get_latest_transactions(user_id, limit=10, offset=0, asset_type=None, search_query=None):
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

# Khởi tạo instance duy nhất để dùng chung
repo = Repository()
