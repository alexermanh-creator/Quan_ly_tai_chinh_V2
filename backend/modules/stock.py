# backend/modules/stock.py
from backend.interface import BaseModule
from backend.database.db_manager import db

class StockModule(BaseModule):
    def format_currency(self, value):
        abs_val = abs(value)
        sign = "+" if value > 0 else "-" if value < 0 else ""
        if abs_val >= 10**6:
            return f"{sign}{abs_val / 10**6:,.1f} triệu"
        return f"{sign}{abs_val:,.0f}đ"

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Lấy giá thủ công (nếu có)
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            # 2. Lấy toàn bộ giao dịch
            cursor.execute("SELECT ticker, qty, price, total_value, type FROM transactions WHERE user_id = ? AND asset_type = 'STOCK' ORDER BY date ASC", (self.user_id,))
            transactions = cursor.fetchall()

            if not transactions:
                return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nChưa có dữ liệu giao dịch."

            portfolio = {}
            total_deposit = 0 
            total_withdraw = 0 

            for tx in transactions:
                tk = tx['ticker']
                if tk not in portfolio: portfolio[tk] = {'qty': 0, 'total_cost': 0}
                
                if tx['type'] == 'BUY':
                    portfolio[tk]['qty'] += tx['qty']
                    portfolio[tk]['total_cost'] += tx['total_value']
                    total_deposit += tx['total_value']
                elif tx['type'] == 'SELL':
                    if portfolio[tk]['qty'] > 0:
                        avg_cost_unit = portfolio[tk]['total_cost'] / portfolio[tk]['qty']
                        portfolio[tk]['total_cost'] -= tx['qty'] * avg_cost_unit
                    portfolio[tk]['qty'] -= tx['qty']
                    total_withdraw += tx['total_value']

            stock_details = []
            total_market_value = 0
            stats = []

            for tk, data in portfolio.items():
                if data['qty'] <= 0: continue
                
                # Logic V1: Giá vốn TB
                avg_cost_price = data['total_cost'] / data['qty'] / 1000
                
                # Logic V1: Lấy giá của lệnh cuối cùng làm giá hiện tại
                cursor.execute("SELECT price FROM transactions WHERE ticker=? AND user_id=? ORDER BY date DESC LIMIT 1", (tk, self.user_id))
                last_price = cursor.fetchone()[0]
                
                # Ưu tiên giá manual nếu CEO có dùng lệnh 'gia'
                curr_price = price_map.get(tk, last_price)
                
                mkt_val = data['qty'] * curr_price * 1000
                profit = mkt_val - data['total_cost']
                roi = (profit / data['total_cost'] * 100) if data['total_cost'] > 0 else 0
                
                total_market_value += mkt_val
                stats.append({'ticker': tk, 'roi': roi, 'value': mkt_val})

                stock_details.append(
                    f"<b>{tk}</b>\nSL: {data['qty']:,.0f}\nGiá vốn TB: {avg_cost_price:,.1f}\n"
                    f"Giá hiện tại: {curr_price:,.1f}\nGiá trị: {self.format_currency(mkt_val).replace('+', '')}\n"
                    f"Lãi: {self.format_currency(profit)} ({roi:+.1f}%)"
                )

            total_net_cost = total_deposit - total_withdraw
            total_profit_all = total_market_value - total_net_cost
            total_roi_all = (total_profit_all / total_net_cost * 100) if total_net_cost > 0 else 0
            
            best = max(stats, key=lambda x: x['roi'])
            worst = min(stats, key=lambda x: x['roi'])
            biggest = max(stats, key=lambda x: x['value'])
            biggest_pct = (biggest['value'] / total_market_value * 100) if total_market_value > 0 else 0

            lines = [
                "📊", "<b>DANH MỤC CỔ PHIẾU</b>",
                f"💰 Tổng giá trị: {self.format_currency(total_market_value).replace('+', '')}",
                f"💵 Tổng vốn: {self.format_currency(total_net_cost).replace('+', '')}",
                f"📈 Lãi: {self.format_currency(total_profit_all)} ({total_roi_all:+.1f}%)",
                f"⬆️ Tổng nạp: {self.format_currency(total_deposit).replace('+', '')}",
                f"⬇️ Tổng rút: {self.format_currency(total_withdraw).replace('+', '')}",
                f"🏆 Mã tốt nhất: {best['ticker']} ({best['roi']:+.1f}%)",
                f"📉 Mã kém nhất: {worst['ticker']} ({worst['roi']:+.1f}%)",
                f"📊 Tỉ trọng lớn nhất: {biggest['ticker']} ({biggest_pct:.1f}%)",
                "────────────", "\n────────────\n".join(stock_details), "────────────"
            ]
            return "\n".join(lines)
