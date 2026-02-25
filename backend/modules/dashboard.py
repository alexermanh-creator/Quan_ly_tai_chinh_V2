# backend/modules/dashboard.py
from backend.interface import BaseModule
from backend.database.db_manager import db

class DashboardModule(BaseModule):
    def format_currency(self, value):
        abs_val = abs(value)
        sign = "-" if value < 0 else ""
        if abs_val >= 10**9: return f"{sign}{value / 10**9:,.2f} tỷ"
        if abs_val >= 10**6: return f"{sign}{value / 10**6:,.1f} triệu"
        return f"{sign}{value:,.0f}đ"

    def run(self):
        EX_RATE = 26300 
        GOAL = 500_000_000 

        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Dòng tiền gốc (10 tỷ nạp)
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='OUT'", (self.user_id,))
            t_out = abs(cursor.fetchone()[0] or 0)
            net_cash_invested = t_in - t_out

            # 2. Giá trị thị trường STOCK thực tế (Phải lấy giá Manual)
            cursor.execute("SELECT ticker, SUM(CASE WHEN type='BUY' THEN qty ELSE -qty END) as q FROM transactions WHERE asset_type='STOCK' GROUP BY ticker")
            stocks = cursor.fetchall()
            stock_mkt_val = 0
            total_spent_on_stock = 0
            total_received_from_stock = 0

            # Lấy giá manual map
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row[0]: row[1] for row in cursor.fetchall()}

            for s in stocks:
                tk, qty = s['ticker'], s['q']
                if qty > 0:
                    price = price_map.get(tk)
                    if not price: # Backup lấy giá mua gần nhất
                        cursor.execute("SELECT price FROM transactions WHERE ticker=? AND type='BUY' ORDER BY date DESC LIMIT 1", (tk,))
                        res = cursor.fetchone()
                        price = res[0] if res else 0
                    stock_mkt_val += qty * price * 1000

            # 3. Tiền mặt khả dụng thực tế (Tính từ lịch sử BUY/SELL)
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE type='BUY' AND asset_type!='CASH'")
            spent = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE type='SELL' AND asset_type!='CASH'")
            received = cursor.fetchone()[0] or 0
            
            cash_balance = net_cash_invested - spent + received

            # 4. Quy đổi Crypto
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE asset_type='CRYPTO'")
            crypto_raw = cursor.fetchone()[0] or 0
            crypto_vnd = crypto_raw * EX_RATE

            total_assets = cash_balance + stock_mkt_val + crypto_vnd
            profit = total_assets - net_cash_invested
            roi = (profit / net_cash_invested * 100) if net_cash_invested > 0 else 0

        lines = [
            "💼 <b>TÀI SẢN CỦA BẠN</b>",
            f"💰 Tổng: <b>{self.format_currency(total_assets)}</b>",
            f"📈 Lãi: {self.format_currency(profit)} (🟢 {roi:+.1f}%)",
            "",
            f"📊 Stock: {self.format_currency(stock_mkt_val)}",
            f"🪙 Crypto: {self.format_currency(crypto_vnd)}",
            "",
            f"⬆️ Tổng nạp: {self.format_currency(t_in)}",
            "━━━━━━━━━━━━━━━━━━━",
            f"🏦 Tiền mặt: {self.format_currency(cash_balance)}",
            f"📊 Cổ phiếu: {self.format_currency(stock_mkt_val)}",
            "",
            "🏠 <i>Hệ thống đã đồng bộ giá thị trường mới nhất.</i>"
        ]
        return "\n".join(lines)
