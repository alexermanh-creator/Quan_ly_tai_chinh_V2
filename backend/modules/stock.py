# backend/modules/stock.py
from backend.interface import BaseModule
from backend.database.db_manager import db

class StockModule(BaseModule):
    def format_currency(self, value):
        abs_val = abs(value)
        sign = "-" if value < 0 else ""
        if abs_val >= 10**9: return f"{sign}{value / 10**9:,.2f} tỷ"
        if abs_val >= 10**6: return f"{sign}{value / 10**6:,.1f} triệu"
        return f"{sign}{value:,.0f}đ"

    def get_group_report(self):
        """BÁO CÁO HIỆU SUẤT CỔ PHIẾU CHI TIẾT"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            cursor.execute("SELECT ticker, qty, price, total_value, type FROM transactions WHERE user_id = ? AND asset_type = 'STOCK'", (self.user_id,))
            rows = cursor.fetchall()

            if not rows: return "❌ Chưa có dữ liệu giao dịch."

            total_buy = 0
            total_sell = 0
            portfolio = {}
            for r in rows:
                tk = r['ticker']
                if tk not in portfolio: portfolio[tk] = 0
                if r['type'] == 'BUY':
                    total_buy += r['total_value']
                    portfolio[tk] += r['qty']
                else:
                    total_sell += r['total_value']
                    portfolio[tk] -= r['qty']

            current_mkt_val = sum([qty * price_map.get(tk, 0) * 1000 for tk, qty in portfolio.items() if qty > 0])
            net_invested = total_buy - total_sell
            profit = current_mkt_val - net_invested
            roi = (profit / net_invested * 100) if net_invested > 0 else 0
            status = "🚀 Tốt" if roi > 10 else "⚖️ Ổn định" if roi >= 0 else "⚠️ Cần rà soát"

            lines = [
                "📈 <b>BÁO CÁO HIỆU SUẤT CỔ PHIẾU</b>\n",
                f"💰 <b>Tổng vốn ròng:</b> {self.format_currency(net_invested)}",
                f"💵 <b>Giá trị hiện tại:</b> {self.format_currency(current_mkt_val)}",
                f"📊 <b>Tổng lãi/lỗ:</b> <b>{self.format_currency(profit)}</b>",
                f"🚀 <b>Tỷ suất (ROI):</b> <b>{roi:+.2f}%</b>",
                "",
                f"⬆️ Tổng tiền nạp: {self.format_currency(total_buy)}",
                f"⬇️ Tổng tiền rút: {self.format_currency(total_sell)}",
                "",
                f"🔥 <b>Đánh giá Danh mục:</b> {status}",
                "━━━━━━━━━━━━━━━━━━━",
                "🏠 <i>Dữ liệu dựa trên giá cập nhật mới nhất.</i>"
            ]
            return "\n".join(lines)

    def run(self):
        # ... (Giữ nguyên code hàm run() bạn đã gửi)
        # Tôi khuyên bạn giữ nguyên code cũ của hàm run đã gửi ở trên vì nó đã chuẩn Layout.
