# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def format_smart_currency(value):
        abs_val = abs(value)
        sign = "-" if value < 0 else ""
        if abs_val >= 1_000_000_000: return f"{sign}{abs_val / 1_000_000_000:.2f} tỷ"
        elif abs_val >= 1_000_000: return f"{sign}{abs_val / 1_000_000:.1f}tr"
        return f"{sign}{abs_val:,.0f}đ"

    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        ticker, asset_type, type = ticker.upper(), asset_type.upper(), type.upper()

        # CHẶN MUA KHỐNG
        if type == 'BUY':
            available = Repository.get_available_cash(user_id, asset_type)
            if available < total_value:
                return False, f"❌ Ví {asset_type} không đủ tiền!\nSức mua hiện tại: <b>{Repository.format_smart_currency(available)}</b>\nCần thêm: {Repository.format_smart_currency(total_value - available)}"

        if type == 'TRANSFER':
            mom_cash = Repository.get_available_cash(user_id, 'CASH')
            if mom_cash < total_value:
                return False, f"❌ Ví Mẹ không đủ! (Có: {Repository.format_smart_currency(mom_cash)})"
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, 'CASH', 1, ?, ?, 'TRANSFER_OUT', datetime('now', 'localtime'))", (user_id, f"SANG_{asset_type}", total_value, total_value))
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_IN', datetime('now', 'localtime'))", (user_id, ticker, asset_type, total_value, total_value))
                conn.commit()
                return True, "✅ Chuyển vốn thành công."

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))", (user_id, ticker, asset_type, qty, price, total_value, type))
            
            if asset_type != 'CASH':
                cursor.execute("SELECT total_qty, avg_price FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, ticker))
                row = cursor.fetchone()
                cq, cp = (row['total_qty'], row['avg_price']) if row else (0, 0)
                
                # Tính giá trị vốn mới để tính avg_price chuẩn
                if type == 'BUY':
                    nq = cq + qty
                    # total_value lúc này đã bao gồm x1000 (stock) hoặc xExRate (crypto)
                    # Chúng ta chia lại cho multiplier để lưu avg_price đồng nhất
                    new_cost = (cq * cp) + total_value
                    np = new_cost / nq if nq > 0 else 0
                else: # SELL
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

repo = Repository()
