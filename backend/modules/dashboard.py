# backend/modules/dashboard.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class DashboardModule(BaseModule):
    def format_currency(self, value):
        abs_val = abs(value)
        sign = "-" if value < 0 else ""
        if abs_val >= 10**9: return f"{sign}{value / 10**9:,.2f} tỷ"
        if abs_val >= 10**6: return f"{sign}{value / 10**6:,.1f} triệu"
        return f"{sign}{value:,.0f}đ"

    def run(self):
        EX_RATE = 26300  # CEO có thể điều chỉnh hoặc lấy từ settings
        GOAL = 500_000_000 

        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. VỐN NẠP RÒNG (Lấy từ Repository)
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'OUT'", (self.user_id,))
            t_out = abs(cursor.fetchone()[0] or 0)
            net_invested = t_in - t_out

            # 2. TIỀN MẶT KHẢ DỤNG
            cash_balance = repo.get_available_cash(self.user_id)

            # 3. GIÁ TRỊ THỊ TRƯỜNG (Lấy từ bảng Portfolio đã hợp nhất)
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}
            
            cursor.execute("SELECT ticker, asset_type, total_qty, avg_price FROM portfolio WHERE user_id = ?", (self.user_id,))
            portfolio_rows = cursor.fetchall()
            
            stock_mkt_val = 0
            crypto_vnd = 0
            other_val = 0

            for row in portfolio_rows:
                qty = row['total_qty']
                if qty <= 0: continue
                
                ticker = row['ticker']
                # Ưu tiên giá manual, nếu không có lấy giá vốn trung bình
                price = price_map.get(ticker, row['avg_price'])
                
                if row['asset_type'] == 'STOCK':
                    stock_mkt_val += qty * price * 1000
                elif row['asset_type'] == 'CRYPTO':
                    # Quy đổi USD sang VND nếu giá lưu là USD
                    crypto_vnd += qty * price * EX_RATE
                elif row['asset_type'] == 'OTHER':
                    other_val += qty * price

            # 4. TỔNG KẾT & CHỈ SỐ
            total_assets = cash_balance + stock_mkt_val + crypto_vnd + other_val
            profit = total_assets - net_invested
            roi = (profit / net_invested * 100) if net_invested > 0 else 0
            progress = (total_assets / GOAL * 100)
            remain = max(0, GOAL - total_assets)

        # Layout đúng như thống nhất
        lines = [
            "💼 <b>TÀI SẢN CỦA BẠN</b>",
            f"💰 Tổng: <b>{self.format_currency(total_assets)}</b>",
            f"📈 Lãi: {self.format_currency(profit)} (🟢 {roi:+.1f}%)",
            "",
            f"📊 Stock: {self.format_currency(stock_mkt_val)}",
            f"🪙 Crypto: {self.format_currency(crypto_vnd)}",
            f"🥇 Khác: {self.format_currency(other_val)}",
            "",
            f"🎯 Mục tiêu: {self.format_currency(GOAL)}",
            f"🏁 Tiến độ: {progress:.1f}%",
            f"Còn thiếu: {self.format_currency(remain)}",
            "",
            f"⬆️ Tổng nạp: {self.format_currency(t_in)}",
            f"⬇️ Tổng rút: {self.format_currency(t_out)}",
            "━━━━━━━━━━━━━━━━━━━",
            f"🏦 Tiền mặt: {self.format_currency(cash_balance)}",
            f"📊 Cổ phiếu: {self.format_currency(stock_mkt_val)}",
            f"🪙 Crypto: {self.format_currency(crypto_vnd)}",
            "",
            "🏠 <i>Quay Về Trang Chủ.</i>"
        ]
        return "\n".join(lines)
