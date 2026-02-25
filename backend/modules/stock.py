# backend/modules/stock.py
from backend.interface import BaseModule
from backend.database.db_manager import db

class StockModule(BaseModule):
    def format_currency(self, value):
        """Định dạng tiền tệ chuẩn: triệu hoặc đồng"""
        abs_val = abs(value)
        sign = "+" if value > 0 else "-" if value < 0 else ""
        if abs_val >= 10**6:
            return f"{sign}{abs_val / 10**6:,.1f} triệu"
        return f"{sign}{abs_val:,.0f}đ"

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Lấy bảng giá thị trường
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            # 2. Lấy toàn bộ giao dịch Stock
            cursor.execute("SELECT ticker, qty, price, total_value, type FROM transactions WHERE user_id = ? AND asset_type = 'STOCK'", (self.user_id,))
            transactions = cursor.fetchall()

            if not transactions:
                return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nChưa có dữ liệu giao dịch."

            # 3. Tính toán logic tài chính chuẩn
            portfolio = {}
            total_deposit = 0 # Tổng nạp nhóm Stock (Lệnh BUY)
            total_withdraw = 0 # Tổng rút nhóm Stock (Lệnh SELL)

            for tx in transactions:
                tk = tx['ticker']
                if tk not in portfolio:
                    portfolio[tk] = {'qty': 0, 'total_cost': 0}
                
                if tx['type'] == 'BUY':
                    portfolio[tk]['qty'] += tx['qty']
                    portfolio[tk]['total_cost'] += tx['total_value']
                    total_deposit += tx['total_value']
                elif tx['type'] == 'SELL':
                    # Trừ vốn theo tỷ lệ bình quân gia quyền
                    if portfolio[tk]['qty'] > 0:
                        avg_cost_unit = portfolio[tk]['total_cost'] / portfolio[tk]['qty']
                        portfolio[tk]['total_cost'] -= tx['qty'] * avg_cost_unit
                    
                    portfolio[tk]['qty'] -= tx['qty']
                    total_withdraw += tx['total_value']

            # 4. Phân tích chi tiết từng mã và tìm Top mã
            stock_details = []
            total_market_value = 0
            stats = []

            for tk, data in portfolio.items():
                if data['qty'] <= 0: continue
                
                # Tính các chỉ số cho mỗi mã
                avg_cost_price = data['total_cost'] / data['qty'] / 1000
                curr_price = price_map.get(tk, avg_cost_price) # Mặc định bằng giá vốn nếu chưa cập nhật
                mkt_val = data['qty'] * curr_price * 1000
                profit = mkt_val - data['total_cost']
                roi = (profit / data['total_cost'] * 100) if data['total_cost'] > 0 else 0
                
                total_market_value += mkt_val
                stats.append({'ticker': tk, 'roi': roi, 'value': mkt_val})

                # Render Body chi tiết từng mã
                stock_details.append(
                    f"<b>{tk}</b>\n"
                    f"SL: {data['qty']:,.0f}\n"
                    f"Giá vốn TB: {avg_cost_price:,.1f}\n"
                    f"Giá hiện tại: {curr_price:,.1f}\n"
                    f"Giá trị: {self.format_currency(mkt_val).replace('+', '')}\n"
                    f"Lãi: {self.format_currency(profit)} ({roi:+.1f}%)"
                )

            # 5. Tính toán các chỉ số Header danh mục
            total_net_cost = total_deposit - total_withdraw
            total_profit_all = total_market_value - total_net_cost
            total_roi_all = (total_profit_all / total_net_cost * 100) if total_net_cost > 0 else 0
            
            best = max(stats, key=lambda x: x['roi'])
            worst = min(stats, key=lambda x: x['roi'])
            biggest = max(stats, key=lambda x: x['value'])
            biggest_pct = (biggest['value'] / total_market_value * 100) if total_market_value > 0 else 0

            # --- RENDER LAYOUT ĐẦY ĐỦ NHƯ CEO YÊU CẦU ---
            lines = [
                "📊",
                "<b>DANH MỤC CỔ PHIẾU</b>",
                f"💰 Tổng giá trị: {self.format_currency(total_market_value).replace('+', '')}",
                f"💵 Tổng vốn: {self.format_currency(total_net_cost).replace('+', '')}",
                f"📈 Lãi: {self.format_currency(total_profit_all)} ({total_roi_all:+.1f}%)",
                f"⬆️ Tổng nạp: {self.format_currency(total_deposit).replace('+', '')}",
                f"⬇️ Tổng rút: {self.format_currency(total_withdraw).replace('+', '')}",
                f"🏆 Mã tốt nhất: {best['ticker']} ({best['roi']:+.1f}%)",
                f"📉 Mã kém nhất: {worst['ticker']} ({worst['roi']:+.1f}%)",
                f"📊 Tỉ trọng lớn nhất: {biggest['ticker']} ({biggest_pct:.1f}%)",
                "────────────",
                "\n────────────\n".join(stock_details),
                "────────────"
            ]
            return "\n".join(lines)
