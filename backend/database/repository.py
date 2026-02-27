# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def format_smart_currency(value):
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1e9: return f"{sign}{value/1e9:.2f} tỷ"
        if abs_v >= 1e6: return f"{sign}{value/1e6:,.1f}tr"
        return f"{sign}{value:,.0f}đ"

    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        ticker, asset_type, type = ticker.upper(), asset_type.upper(), type.upper()

        # 🛡️ LOGIC ĐIỀU CHUYỂN VỐN BỌC THÉP
        if type == 'TRANSFER':
            # Nếu ticker là MOVE_CASH -> Sếp muốn rút từ Ví con (đang thao tác) về Ví Mẹ
            if "MOVE_CASH" in ticker:
                # Sếp cần cung cấp asset_type gốc từ đâu chuyển về. 
                # Nếu lệnh từ module Stock, ta cần xác định nguồn là STOCK
                source = "STOCK" # Mặc định trong ngữ cảnh này, hoặc logic parser cần truyền đúng
                target = "CASH"
            else:
                source = "CASH"
                target = asset_type
            
            if Repository.get_available_cash(user_id, source) < total_value:
                return False, f"❌ Ví {source} không đủ tiền mặt để chuyển!"

            with db.get_connection() as conn:
                cursor = conn.cursor()
                # Phiếu chi từ ví nguồn
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_OUT', datetime('now', 'localtime'))", (user_id, f"SANG_{target}", source, total_value, total_value))
                # Phiếu thu vào ví đích
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_IN', datetime('now', 'localtime'))", (user_id, f"NHAN_TU_{source}", target, total_value, total_value))
                conn.commit()
            return True, f"✅ Đã điều chuyển {Repository.format_smart_currency(total_value)} từ {source} sang {target}."

        # 🛡️ CHẶN MUA VƯỢT HẠN MỨC
        if type == 'BUY' and Repository.get_available_cash(user_id, asset_type) < total_value:
            return False, f"❌ Ví {asset_type} không đủ hạn mức!"

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))", (user_id, ticker, asset_type, qty, price, total_value, type))
            if asset_type != 'CASH':
                cursor.execute("SELECT total_qty, avg_price FROM portfolio WHERE user_id=? AND ticker=?", (user_id, ticker))
                row = cursor.fetchone()
                cq, cp = (row[0], row[1]) if row else (0, 0)
                if type == 'BUY':
                    nq = cq + qty
                    np = ((cq * cp) + total_value) / nq if nq > 0 else 0
                else:
                    nq = max(0, cq - qty)
                    np = cp if nq > 0 else 0
                cursor.execute("INSERT INTO portfolio (user_id, ticker, asset_type, total_qty, avg_price, last_updated) VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime')) ON CONFLICT(user_id, ticker) DO UPDATE SET total_qty=excluded.total_qty, avg_price=excluded.avg_price, last_updated=excluded.last_updated", (user_id, ticker, asset_type, nq, np))
            conn.commit()
        return True, "✅ Ghi nhận thành công."

    @staticmethod
    def get_available_cash(user_id, asset_type):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(CASE WHEN type IN ('IN', 'SELL', 'TRANSFER_IN', 'CASH_DIVIDEND') THEN total_value WHEN type IN ('OUT', 'BUY', 'TRANSFER_OUT') THEN -total_value ELSE 0 END) FROM transactions WHERE user_id = ? AND asset_type = ?", (user_id, asset_type))
            res = cursor.fetchone()[0]
            return res if res else 0

repo = Repository()
