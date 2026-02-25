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
        """BÁO CÁO HIỆU SUẤT CỔ PHIẾU CHI TIẾT - FIXED LOGIC"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            cursor.execute("SELECT ticker, qty, price, total_value, type FROM transactions WHERE user_id = ? AND asset_type = 'STOCK'", (self.user_id,))
            rows = cursor.fetchall()

            if not rows: return "❌ Chưa có dữ liệu giao dịch."

            portfolio_qty = {}
            total_buy_val = 0
            total_sell_val = 0

            for r in rows:
                tk = r['ticker']
                if tk not in portfolio_qty: portfolio_qty[tk] = 0
                if r['type'] == 'BUY':
                    total_buy_val += r['total_value']
                    portfolio_qty[tk] += r['qty']
                else:
                    total_sell_val += r['total_value']
                    portfolio_qty[tk] -= r['qty']

            current_mkt_val = 0
            for tk, qty in portfolio_qty.items():
                if qty > 0:
                    # Lấy giá manual, nếu không có lấy giá mua trung bình gần nhất
                    price = price_map.get(tk)
                    if not price:
                        cursor.execute("SELECT price FROM transactions WHERE ticker=? AND type='BUY' ORDER BY date DESC LIMIT 1", (tk,))
                        res = cursor.fetchone()
                        price = res[0] if res else 0
                    current_mkt_val += qty * price * 1000

            net_invested = total_buy_val - total_sell_val
            profit = current_mkt_val - net_invested
            roi = (profit / net_invested * 100) if net_invested > 0 else 0
            status = "🚀 Tốt" if roi > 10 else "⚖️ Ổn định" if roi >= 0 else "⚠️ Cần rà soát"

            lines = [
                "📈 <b>BÁO CÁO HIỆU SUẤT CỔ PHIẾU</b>",
                f"💰 <b>Vốn ròng còn lại:</b> {self.format_currency(net_invested)}",
                f"💵 <b>Giá trị hiện tại:</b> {self.format_currency(current_mkt_val)}",
                f"📊 <b>Tổng lãi/lỗ:</b> <b>{self.format_currency(profit)}</b>",
                f"🚀 <b>ROI:</b> <b>{roi:+.2f}%</b>",
                "",
                f"⬆️ Tổng nạp Stock: {self.format_currency(total_buy_val)}",
                f"⬇️ Tổng rút Stock: {self.format_currency(total_sell_val)}",
                "",
                f"🔥 <b>Đánh giá Danh mục:</b> {status}",
                "━━━━━━━━━━━━━━━━━━━",
                "🏠 <i>Dữ liệu dựa trên giá cập nhật mới nhất.</i>"
            ]
            return "\n".join(lines)

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            cursor.execute("SELECT ticker, qty, price, total_value, type FROM transactions WHERE user_id = ? AND asset_type = 'STOCK'", (self.user_id,))
            transactions = cursor.fetchall()

            if not transactions: return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nChưa có dữ liệu."

            portfolio = {}
            for tx in transactions:
                tk = tx['ticker']
                if tk not in portfolio: portfolio[tk] = {'qty': 0, 'total_cost': 0}
                if tx['type'] == 'BUY':
                    portfolio[tk]['qty'] += tx['qty']
                    portfolio[tk]['total_cost'] += tx['total_value']
                else:
                    if portfolio[tk]['qty'] > 0:
                        avg_cost = portfolio[tk]['total_cost'] / portfolio[tk]['qty']
                        portfolio[tk]['total_cost'] -= tx['qty'] * avg_cost
                    portfolio[tk]['qty'] -= tx['qty']

            stock_details = []
            total_mkt_val = 0
            total_cost_val = 0
            stats = []

            for tk, data in portfolio.items():
                if data['qty'] <= 0: continue
                avg_p = data['total_cost'] / data['qty'] / 1000
                curr_p = price_map.get(tk, avg_p)
                val = data['qty'] * curr_p * 1000
                profit = val - data['total_cost']
                profit_pct = (profit / data['total_cost'] * 100) if data['total_cost'] > 0 else 0
                
                total_mkt_val += val
                total_cost_val += data['total_cost']
                stats.append({'tk': tk, 'pct': profit_pct, 'val': val})

                stock_details.append(
                    f"<b>{tk}</b>\nSL: {data['qty']:,.0f}\nGiá vốn TB: {avg_p:,.1f}\nGiá hiện tại: {curr_p:,.1f}\n"
                    f"Giá trị: {self.format_currency(val)}\nLãi: {self.format_currency(profit)} ({profit_pct:+.1f}%)"
                )

            best = max(stats, key=lambda x: x['pct'])
            biggest = max(stats, key=lambda x: x['val'])

            lines = [
                "📊 <b>DANH MỤC CỔ PHIẾU</b>",
                f"💰 Tổng giá trị: <b>{self.format_currency(total_mkt_val)}</b>",
                f"💵 Tổng vốn: {self.format_currency(total_cost_val)}",
                f"📈 Lãi: {self.format_currency(total_mkt_val - total_cost_val)} ({(total_mkt_val/total_cost_val-1)*100:+.1f}%)",
                f"🏆 Tốt nhất: {best['tk']} ({best['pct']:+.1f}%)",
                f"📊 Tỉ trọng lớn nhất: {biggest['tk']} ({(biggest['val']/total_mkt_val*100):.1f}%)",
                "────────────",
                "\n────────────\n".join(stock_details),
                "────────────"
            ]
            return "\n".join(lines)
