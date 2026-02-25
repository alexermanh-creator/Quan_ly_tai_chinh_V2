# backend/modules/stock.py
from backend.interface import BaseModule
from backend.database.db_manager import db

class StockModule(BaseModule):
    def format_currency(self, value):
        """Định dạng tiền tệ: tỷ, triệu hoặc đồng"""
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
        """Hiển thị danh mục chi tiết từng mã"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            cursor.execute('''
                SELECT ticker, qty, price, total_value, type 
                FROM transactions WHERE user_id = ? AND asset_type = 'STOCK'
            ''', (self.user_id,))
            transactions = cursor.fetchall()

            if not transactions:
                return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nChưa có dữ liệu giao dịch."

            portfolio = {}
            total_buy_all = 0
            total_sell_all = 0

            for tx in transactions:
                tk = tx['ticker']
                if tk not in portfolio: portfolio[tk] = {'qty': 0, 'total_cost': 0}
                if tx['type'] == 'BUY':
                    portfolio[tk]['qty'] += tx['qty']
                    portfolio[tk]['total_cost'] += tx['total_value']
                    total_buy_all += tx['total_value']
                elif tx['type'] == 'SELL':
                    if portfolio[tk]['qty'] > 0:
                        avg_cost_temp = portfolio[tk]['total_cost'] / portfolio[tk]['qty']
                        portfolio[tk]['total_cost'] -= tx['qty'] * avg_cost_temp
                    portfolio[tk]['qty'] -= tx['qty']
                    total_sell_all += tx['total_value']

            stock_details_list = []
            total_market_value = 0
            total_net_cost = 0
            codes_stats = []

            for tk, data in portfolio.items():
                if data['qty'] <= 0: continue 
                avg_price = (data['total_cost'] / data['qty'] / 1000)
                curr_price = price_map.get(tk, avg_price)
                mkt_value = data['qty'] * curr_price * 1000
                profit = mkt_value - data['total_cost']
                profit_pct = (profit / data['total_cost'] * 100) if data['total_cost'] > 0 else 0
                total_market_value += mkt_value
                total_net_cost += data['total_cost']
                
                codes_stats.append({'ticker': tk, 'profit_pct': profit_pct, 'mkt_value': mkt_value, 'qty': data['qty'], 'avg_price': avg_price, 'curr_price': curr_price, 'profit': profit})

            if not codes_stats: return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nDanh mục trống."

            best = max(codes_stats, key=lambda x: x['profit_pct'])
            worst = min(codes_stats, key=lambda x: x['profit_pct'])
            biggest = max(codes_stats, key=lambda x: x['mkt_value'])

            for item in codes_stats:
                detail = (f"<b>{item['ticker']}</b>\nSL: {item['qty']:,.0f}\nGiá vốn TB: {item['avg_price']:,.1f}\nGiá hiện tại: {item['curr_price']:,.1f}\n"
                          f"Giá trị: {self.format_currency(item['mkt_value'])}\nLãi: {self.format_currency(item['profit'])} ({item['profit_pct']:+.1f}%)")
                stock_details_list.append(detail)

            profit_total = total_market_value - total_net_cost
            roi_total = (profit_total / total_net_cost * 100) if total_net_cost > 0 else 0
            biggest_pct = (biggest['mkt_value'] / total_market_value * 100) if total_market_value > 0 else 0

            lines = [
                "📊 <b>DANH MỤC CỔ PHIẾU</b>",
                f"💰 Tổng giá trị: <b>{self.format_currency(total_market_value)}</b>",
                f"💵 Tổng vốn: {self.format_currency(total_net_cost)}",
                f"📈 Lãi: {self.format_currency(profit_total)} ({roi_total:+.1f}%)",
                f"⬆️ Tổng nạp: {self.format_currency(total_buy_all)} | ⬇️ Tổng rút: {self.format_currency(total_sell_all)}",
                f"🏆 Tốt nhất: {best['ticker']} ({best['profit_pct']:+.1f}%)",
                f"📊 Tỉ trọng lớn nhất: {biggest['ticker']} ({biggest_pct:.1f}%)",
                "────────────",
                "\n────────────\n".join(stock_details_list),
                "────────────"
            ]
            return "\n".join(lines)
