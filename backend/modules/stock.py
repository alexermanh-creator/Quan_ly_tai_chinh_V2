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
            
            # 1. Lấy giá cập nhật thủ công mới nhất
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            # 2. Lấy dữ liệu nạp/rút riêng của nhánh STOCK (nếu có ghi chú)
            # Tạm thời tính tổng nạp/rút dựa trên các lệnh BUY/SELL
            cursor.execute('''
                SELECT ticker, qty, price, total_value, type 
                FROM transactions 
                WHERE user_id = ? AND asset_type = 'STOCK'
            ''', (self.user_id,))
            transactions = cursor.fetchall()

            if not transactions:
                return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nChưa có dữ liệu giao dịch chứng khoán."

            # 3. Xử lý logic tính Giá vốn TB và Số lượng nắm giữ
            portfolio = {}
            total_buy_value = 0 # Tổng vốn đã chi ra
            total_sell_value = 0 # Tổng tiền đã thu về khi bán

            for tx in transactions:
                tk = tx['ticker']
                if tk not in portfolio:
                    portfolio[tk] = {'qty': 0, 'total_cost': 0}
                
                if tx['type'] == 'BUY':
                    portfolio[tk]['qty'] += tx['qty']
                    portfolio[tk]['total_cost'] += tx['total_value']
                    total_buy_value += tx['total_value']
                elif tx['type'] == 'SELL':
                    portfolio[tk]['qty'] -= tx['qty']
                    # Khi bán, ta trừ bớt vốn tương ứng với tỷ lệ số lượng
                    # (Hoặc đơn giản là theo dõi dòng tiền thu về)
                    total_sell_value += tx['total_value']

            # 4. Render danh sách chi tiết mã
            stock_details = []
            total_market_value = 0
            best_code = {"ticker": "N/A", "profit": -999}
            worst_code = {"ticker": "N/A", "profit": 999}
            
            for tk, data in portfolio.items():
                if data['qty'] <= 0: continue # Bỏ qua mã đã bán hết

                avg_price = (data['total_cost'] / data['qty'] / 1000) if data['qty'] > 0 else 0
                curr_price = price_map.get(tk, avg_price) # Nếu chưa có giá manual, coi như bằng giá vốn
                
                mkt_value = data['qty'] * curr_price * 1000
                profit = mkt_value - data['total_cost']
                profit_pct = (profit / data['total_cost'] * 100) if data['total_cost'] > 0 else 0
                
                total_market_value += mkt_value
                
                # Tìm mã tốt nhất/kém nhất
                if profit_pct > best_code["profit"]:
                    best_code = {"ticker": tk, "profit": profit_pct}
                if profit_pct < worst_code["profit"]:
                    worst_code = {"ticker": tk, "profit": profit_pct}

                detail = (
                    f"<b>{tk}</b>\n"
                    f"SL: {data['qty']:,g}\n"
                    f"Giá vốn TB: {avg_price:,.2f}\n"
                    f"Giá hiện tại: {curr_price:,.2f}\n"
                    f"Giá trị: {self.format_currency(mkt_value)}\n"
                    f"Lãi: {profit:+.0f} ({profit_pct:+.1f}%)"
                )
                stock_details.append(detail)

            # 5. Tính toán các chỉ số tổng hợp
            net_profit = total_market_value - (total_buy_value - total_sell_value)
            roi = (net_profit / (total_buy_value - total_sell_value) * 100) if (total_buy_value - total_sell_value) > 0 else 0

            # Render HTML Layout
            lines = [
                "📊",
                "<b>DANH MỤC CỔ PHIẾU</b>",
                f"💰 Tổng giá trị: <b>{self.format_currency(total_market_value)}</b>",
                f"💵 Tổng vốn: {self.format_currency(total_buy_value - total_sell_value)}",
                f"📈 Lãi: {net_profit:+.0f} ({roi:+.1f}%)",
                f"⬆️ Tổng nạp: {self.format_currency(total_buy_value)}",
                f"⬇️ Tổng rút: {self.format_currency(total_sell_value)}",
                f"🏆 Mã tốt nhất: {best_code['ticker']} ({best_code['profit']:+.1f}%)",
                f"📉 Mã kém nhất: {worst_code['ticker']} ({worst_code['profit']:+.1f}%)",
                f"📊 Tỉ trọng lớn nhất: {best_code['ticker']} (Tạm tính...)",
                "────────────",
                "\n────────────\n".join(stock_details),
                "────────────"
            ]
            return "\n".join(lines)
