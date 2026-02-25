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

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Lấy giá cập nhật thủ công từ bảng manual_prices
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            # 2. Lấy dữ liệu giao dịch STOCK
            cursor.execute('''
                SELECT ticker, qty, price, total_value, type 
                FROM transactions 
                WHERE user_id = ? AND asset_type = 'STOCK'
            ''', (self.user_id,))
            transactions = cursor.fetchall()

            if not transactions:
                return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nChưa có dữ liệu giao dịch chứng khoán."

            # 3. Tính toán Giá vốn TB và Số lượng nắm giữ
            portfolio = {}
            total_buy_all = 0  # Tổng nạp (BUY)
            total_sell_all = 0 # Tổng rút (SELL)

            for tx in transactions:
                tk = tx['ticker']
                if tk not in portfolio:
                    portfolio[tk] = {'qty': 0, 'total_cost': 0}
                
                if tx['type'] == 'BUY':
                    portfolio[tk]['qty'] += tx['qty']
                    portfolio[tk]['total_cost'] += tx['total_value']
                    total_buy_all += tx['total_value']
                elif tx['type'] == 'SELL':
                    # Tính toán giảm số lượng và giảm vốn tương ứng (FIFO đơn giản)
                    if portfolio[tk]['qty'] > 0:
                        avg_cost_temp = portfolio[tk]['total_cost'] / portfolio[tk]['qty']
                        portfolio[tk]['total_cost'] -= tx['qty'] * avg_cost_temp
                    
                    portfolio[tk]['qty'] -= tx['qty']
                    total_sell_all += tx['total_value']

            # 4. Tính toán chi tiết từng mã và tìm mã tốt nhất/kém nhất
            stock_details_list = []
            total_market_value = 0
            total_net_cost = 0 # Tổng vốn hiện tại đang nằm trong CP
            
            # Để tìm mã tốt nhất/kém nhất/tỉ trọng lớn nhất
            codes_stats = []

            for tk, data in portfolio.items():
                if data['qty'] <= 0: continue 

                avg_price = (data['total_cost'] / data['qty'] / 1000) if data['qty'] > 0 else 0
                curr_price = price_map.get(tk, avg_price) 
                
                mkt_value = data['qty'] * curr_price * 1000
                profit = mkt_value - data['total_cost']
                profit_pct = (profit / data['total_cost'] * 100) if data['total_cost'] > 0 else 0
                
                total_market_value += mkt_value
                total_net_cost += data['total_cost']
                
                codes_stats.append({
                    'ticker': tk,
                    'profit_pct': profit_pct,
                    'mkt_value': mkt_value,
                    'qty': data['qty'],
                    'avg_price': avg_price,
                    'curr_price': curr_price,
                    'profit': profit
                })

            if not codes_stats:
                return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nDanh mục hiện tại đang trống."

            # Sắp xếp để tìm các chỉ số
            best = max(codes_stats, key=lambda x: x['profit_pct'])
            worst = min(codes_stats, key=lambda x: x['profit_pct'])
            biggest = max(codes_stats, key=lambda x: x['mkt_value'])

            # 5. Build danh sách hiển thị
            for item in codes_stats:
                detail = (
                    f"<b>{item['ticker']}</b>\n"
                    f"SL: {item['qty']:,.0f}\n"
                    f"Giá vốn TB: {item['avg_price']:,.1f}\n"
                    f"Giá hiện tại: {item['curr_price']:,.1f}\n"
                    f"Giá trị: {self.format_currency(item['mkt_value'])}\n"
                    f"Lãi: {self.format_currency(item['profit'])} ({item['profit_pct']:+.1f}%)"
                )
                stock_details_list.append(detail)

            # 6. Render HTML chuẩn Layout CEO
            profit_total = total_market_value - total_net_cost
            roi_total = (profit_total / total_net_cost * 100) if total_net_cost > 0 else 0
            biggest_pct = (biggest['mkt_value'] / total_market_value * 100) if total_market_value > 0 else 0

            lines = [
                "📊",
                "<b>DANH MỤC CỔ PHIẾU</b>",
                f"💰 Tổng giá trị: <b>{self.format_currency(total_market_value)}</b>",
                f"💵 Tổng vốn: {self.format_currency(total_net_cost)}",
                f"📈 Lãi: {self.format_currency(profit_total)} ({roi_total:+.1f}%)",
                f"⬆️ Tổng nạp: {self.format_currency(total_buy_all)}",
                f"⬇️ Tổng rút: {self.format_currency(total_sell_all)}",
                f"🏆 Mã tốt nhất: {best['ticker']} ({best['profit_pct']:+.1f}%)",
                f"📉 Mã kém nhất: {worst['ticker']} ({worst['profit_pct']:+.1f}%)",
                f"📊 Tỉ trọng lớn nhất: {biggest['ticker']} ({biggest_pct:.1f}%)",
                "────────────",
                "\n────────────\n".join(stock_details_list),
                "────────────"
            ]
            return "\n".join(lines)
