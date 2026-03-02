from backend.database.db_manager import db

class Repository:
    @staticmethod
    def get_available_cash(user_id, asset_type):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(CASE WHEN type IN ('IN', 'SELL', 'TRANSFER_IN', 'CASH_DIVIDEND') THEN total_value WHEN type IN ('OUT', 'BUY', 'TRANSFER_OUT') THEN -total_value ELSE 0 END) FROM transactions WHERE user_id = ? AND asset_type = ?", (user_id, asset_type.upper()))
            res = cursor.fetchone()[0]
            return res if res else 0

    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        ticker, asset_type, type = ticker.upper(), asset_type.upper(), type.upper()

        if type == 'TRANSFER':
            target = asset_type
            source = "CASH" if target != "CASH" else ticker.replace("MOVE_", "")
            if Repository.get_available_cash(user_id, source) < total_value:
                return False, f"❌ Ví {source} không đủ tiền!"
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type) VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_OUT')", (user_id, f"TO_{target}", source, total_value, total_value))
                cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type) VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_IN')", (user_id, f"FROM_{source}", target, total_value, total_value))
                conn.commit()
            return True, "✅ Thành công."

        if type == 'BUY' and Repository.get_available_cash(user_id, asset_type) < total_value:
            return False, f"❌ Ví {asset_type} thiếu tiền mặt!"

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, ticker, asset_type, qty, price, total_value, type))
            if asset_type != 'CASH':
                cursor.execute("SELECT total_qty, avg_price FROM portfolio WHERE user_id=? AND ticker=?", (user_id, ticker))
                row = cursor.fetchone()
                cq, cp = (row[0], row[1]) if row else (0, 0)
                nq = cq + qty if type == 'BUY' else max(0, cq - qty)
                np = ((cq * cp) + total_value) / nq if type == 'BUY' and nq > 0 else cp
                cursor.execute("INSERT INTO portfolio (user_id, ticker, asset_type, total_qty, avg_price, market_price) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, ticker) DO UPDATE SET total_qty=excluded.total_qty, avg_price=excluded.avg_price, market_price=excluded.market_price", (user_id, ticker, asset_type, nq, np, price))
            conn.commit()
        return True, "✅ Thành công."

repo = Repository()
