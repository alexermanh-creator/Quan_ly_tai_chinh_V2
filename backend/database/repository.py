# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def format_smart_currency(value):
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1e9: return f"{sign}{value/1e9:.2f} tỷ"
        return f"{sign}{value/1e6:,.1f}tr"

    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        ticker, asset_type, type = ticker.upper(), asset_type.upper(), type.upper()

        # LOGIC ĐIỀU CHUYỂN VỐN 2 CHIỀU
        if type == 'TRANSFER':
            source = 'CASH' if asset_type != 'CASH' else ticker.replace('MOVE_', '')
            target = asset_type if asset_type != 'CASH' else 'CASH'
            
            if Repository.get_available_cash(user_id, source) < total_value:
                return False, f"❌ Ví {source} không đủ tiền mặt!"

            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_OUT', datetime('now', 'localtime'))", (user_id, f"TO_{target}", source, total_value, total_value))
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_IN', datetime('now', 'localtime'))", (user_id, f"FROM_{source}", target, total_value, total_value))
                conn.commit()
            return True, f"✅ Đã chuyển {Repository.format_smart_currency(total_value)} sang {target}."

        # LOGIC CHẶN MUA KHÔNG ĐỦ TIỀN
        if type == 'BUY' and Repository.get_available_cash(user_id, asset_type) < total_value:
            return False, f"❌ Ví {asset_type} không đủ hạn mức!"

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))", (user_id, ticker, asset_type, qty, price, total_value, type))
            
            # CẬP NHẬT PORTFOLIO CHUẨN
            if asset_type != 'CASH':
                cursor.execute("SELECT total_qty, avg_price FROM portfolio WHERE user_id=? AND ticker=?", (user_id, ticker))
                row = cursor.fetchone()
                cq, cp = (row[0], row[1]) if row else (0, 0)
                
                if type == 'BUY':
                    nq = cq + qty
                    # Lưu ý: total_value đã bao gồm x1000/xExRate, nên cp cũng phải tương ứng
                    np = ((cq * cp) + total_value) / nq if nq > 0 else 0
                else:
                    nq = max(0, cq - qty)
                    np = cp if nq > 0 else 0
                
                cursor.execute("INSERT INTO portfolio (user_id, ticker, asset_type, total_qty, avg_price, last_updated) VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime')) ON CONFLICT(user_id, ticker) DO UPDATE SET total_qty=excluded.total_qty, avg_price=excluded.avg_price, last_updated=excluded.last_updated", (user_id, ticker, asset_type, nq, np))
            conn.commit()
        return True, "✅ Thành công."

    @staticmethod
    def get_available_cash(user_id, asset_type):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(CASE WHEN type IN ('IN', 'SELL', 'TRANSFER_IN', 'CASH_DIVIDEND') THEN total_value WHEN type IN ('OUT', 'BUY', 'TRANSFER_OUT') THEN -total_value ELSE 0 END) FROM transactions WHERE user_id = ? AND asset_type = ?", (user_id, asset_type))
            res = cursor.fetchone()[0]
            return res if res else 0
