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
    def get_available_cash(user_id, asset_type):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Bọc thép: Chỉ tính toán trong phạm vi asset_type được yêu cầu
            cursor.execute("""
                SELECT SUM(CASE 
                    WHEN type IN ('IN', 'SELL', 'TRANSFER_IN', 'CASH_DIVIDEND') THEN total_value 
                    WHEN type IN ('OUT', 'BUY', 'TRANSFER_OUT') THEN -total_value 
                    ELSE 0 END) 
                FROM transactions WHERE user_id = ? AND asset_type = ?
            """, (user_id, asset_type.upper()))
            res = cursor.fetchone()[0]
            return res if res else 0

    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        ticker, asset_type, type = ticker.upper(), asset_type.upper(), type.upper()

        # LOGIC TRANSFER: Bọc thép nguyên tử
        if type == 'TRANSFER':
            target_wallet = asset_type # Ví đích (STOCK/CRYPTO/CASH)
            # Nếu đích không phải CASH thì nguồn chắc chắn là CASH (Mẹ)
            source_wallet = "CASH" if target_wallet != "CASH" else ticker.replace("MOVE_", "")
            
            # Kiểm tra nguồn lực trước khi chuyển
            available = Repository.get_available_cash(user_id, source_wallet)
            if available < total_value:
                return False, f"❌ Ví {source_wallet} chỉ còn {Repository.format_smart_currency(available)}. Thiếu {Repository.format_smart_currency(total_value - available)}!"

            with db.get_connection() as conn:
                cursor = conn.cursor()
                # 1. Ghi nhận phiếu chi từ ví Nguồn
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_OUT', datetime('now', 'localtime'))", 
                              (user_id, f"TO_{target_wallet}", source_wallet, total_value, total_value))
                # 2. Ghi nhận phiếu thu vào ví Đích
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_IN', datetime('now', 'localtime'))", 
                              (user_id, f"FROM_{source_wallet}", target_wallet, total_value, total_value))
                conn.commit()
            return True, f"✅ Đã điều chuyển {Repository.format_smart_currency(total_value)} từ {source_wallet} sang {target_wallet}."

        # LOGIC MUA HÀNG: Chặn mua khống triệt để
        if type == 'BUY':
            available = Repository.get_available_cash(user_id, asset_type)
            if available < total_value:
                return False, f"❌ Ví {asset_type} không đủ sức mua! (Còn {Repository.format_smart_currency(available)} - Cần {Repository.format_smart_currency(total_value)})"

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))", (user_id, ticker, asset_type, qty, price, total_value, type))
            
            # Cập nhật Portfolio (Chỉ dành cho tài sản không phải CASH)
            if asset_type != 'CASH' and type in ['BUY', 'SELL']:
                cursor.execute("SELECT total_qty, avg_price FROM portfolio WHERE user_id=? AND ticker=?", (user_id, ticker))
                row = cursor.fetchone()
                cq, cp = (row[0], row[1]) if row else (0, 0)
                nq = cq + qty if type == 'BUY' else max(0, cq - qty)
                np = ((cq * cp) + total_value) / nq if type == 'BUY' and nq > 0 else cp
                cursor.execute("INSERT INTO portfolio (user_id, ticker, asset_type, total_qty, avg_price, last_updated) VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime')) ON CONFLICT(user_id, ticker) DO UPDATE SET total_qty=excluded.total_qty, avg_price=excluded.avg_price, last_updated=excluded.last_updated", (user_id, ticker, asset_type, nq, np))
            conn.commit()
        return True, "✅ Thành công."

repo = Repository()
