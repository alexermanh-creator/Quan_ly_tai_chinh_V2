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

    def get_group_report(self):
        """📈 BÁO CÁO HIỆU SUẤT TÀI CHÍNH - LEVEL CHUYÊN GIA"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Lấy giá manual
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            # 2. Lấy toàn bộ giao dịch
            cursor.execute("SELECT ticker, qty, price, total_value, type FROM transactions WHERE user_id = ? AND asset_type = 'STOCK' ORDER BY date ASC", (self.user_id,))
            rows = cursor.fetchall()

            if not rows: return "❌ <b>Chưa có dữ liệu để lập báo cáo.</b>"

            # 3. Tính toán logic dòng tiền chuẩn V1
            portfolio = {}
            total_deposit = 0
            total_withdraw = 0
            
            for r in rows:
                tk = r['ticker']
                if tk not in portfolio: portfolio[tk] = {'qty': 0, 'total_cost': 0, 'last_p': 0}
                
                if r['type'] == 'BUY':
                    portfolio[tk]['qty'] += r['qty']
                    portfolio[tk]['total_cost'] += r['total_value']
                    portfolio[tk]['last_p'] = r['price']
                    total_deposit += r['total_value']
                elif r['type'] == 'SELL':
                    if portfolio[tk]['qty'] > 0:
                        unit_cost = portfolio[tk]['total_cost'] / portfolio[tk]['qty']
                        portfolio[tk]['total_cost'] -= r['qty'] * unit_cost
                    portfolio[tk]['qty'] -= r['qty']
                    portfolio[tk]['last_p'] = r['price'] # Giá chốt lời/cắt lỗ
                    total_withdraw += r['total_value']

            # 4. Tính toán giá trị hiện tại & ROI
            current_mkt_val = 0
            ticker_stats = []
            for tk, data in portfolio.items():
                if data['qty'] > 0:
                    # Lấy giá manual hoặc giá cuối cùng
                    price = price_map.get(tk, data['last_p'])
                    val = data['qty'] * price * 1000
                    current_mkt_val += val
                    ticker_stats.append({'tk': tk, 'val': val})

            net_cost = total_deposit - total_withdraw
            total_profit = current_mkt_val - net_cost
            roi = (total_profit / net_cost * 100) if net_cost > 0 else 0
            
            # Đánh giá trạng thái
            status = "🔥 TĂNG TRƯỞNG MẠNH" if roi > 15 else "🟢 TÍCH CỰC" if roi >= 0 else "⚠️ CẦN RÀ SOÁT"

            # 5. Render Layout Chuyên gia
            ticker_stats.sort(key=lambda x: x['val'], reverse=True)
            lines = [
                "📈 <b>BÁO CÁO HIỆU SUẤT TÀI CHÍNH</b>",
                "━━━━━━━━━━━━━━━━━━━",
                f"💵 <b>Giá trị hiện tại:</b> {self.format_currency(current_mkt_val).replace('+', '')}",
                f"💰 <b>Vốn ròng thực tế:</b> {self.format_currency(net_cost).replace('+', '')}",
                f"📊 <b>Tổng lãi/lỗ ròng:</b> <b>{self.format_currency(total_profit)}</b>",
                f"🚀 <b>Tỷ suất (ROI):</b> <b>{roi:+.2f}%</b>",
                "",
                "💎 <b>PHÂN BỔ TỈ TRỌNG:</b>"
            ]

            for item in ticker_stats:
                pct = (item['val'] / current_mkt_val * 100) if current_mkt_val > 0 else 0
                bar = "🔵" * int(pct/10) + "⚪" * (10 - int(pct/10))
                lines.append(f"• {item['tk']}: {pct:.1f}%\n  {bar}")

            lines.extend([
                "",
                f"⬆️ Tổng nạp Stock: {self.format_currency(total_deposit).replace('+', '')}",
                f"⬇️ Tổng rút Stock: {self.format_currency(total_withdraw).replace('+', '')}",
                "━━━━━━━━━━━━━━━━━━━",
                f"🔥 <b>TRẠNG THÁI:</b> {status}",
                "🏠 <i>Dữ liệu trích xuất từ Core Tài chính v2.0</i>"
            ])
            return "\n".join(lines)

    def run(self):
        """📊 LAYOUT DANH MỤC CHI TIẾT (10 CHỈ SỐ)"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}
            
            cursor.execute("SELECT ticker, qty, price, total_value, type FROM transactions WHERE user_id = ? AND asset_type = 'STOCK' ORDER BY date ASC", (self.user_id,))
            transactions = cursor.fetchall()

            if not transactions:
                return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nChưa có dữ liệu giao dịch."

            portfolio = {}
            total_deposit = 0 
            total_withdraw = 0 

            for tx in transactions:
                tk = tx['ticker']
                if tk not in portfolio: portfolio[tk] = {'qty': 0, 'total_cost': 0, 'last_p': 0}
                
                if tx['type'] == 'BUY':
                    portfolio[tk]['qty'] += tx['qty']
                    portfolio[tk]['total_cost'] += tx['total_value']
                    portfolio[tk]['last_p'] = tx['price']
                    total_deposit += tx['total_value']
                elif tx['type'] == 'SELL':
                    if portfolio[tk]['qty'] > 0:
                        avg_cost_unit = portfolio[tk]['total_cost'] / portfolio[tk]['qty']
                        portfolio[tk]['total_cost'] -= tx['qty'] * avg_cost_unit
                    portfolio[tk]['qty'] -= tx['qty']
                    portfolio[tk]['last_p'] = tx['price']
                    total_withdraw += tx['total_value']

            stock_details = []
            total_market_value = 0
            stats = []

            for tk, data in portfolio.items():
                if data['qty'] <= 0: continue
                
                avg_cost_price = data['total_cost'] / data['qty'] / 1000
                curr_price = price_map.get(tk, data['last_p']) # Ưu tiên manual, không có lấy giá lệnh cuối
                
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

            lines = [
                "📊", "<b>DANH MỤC CỔ PHIẾU</b>",
                f"💰 Tổng giá trị: {self.format_currency(total_market_value).replace('+', '')}",
                f"💵 Tổng vốn: {self.format_currency(total_net_cost).replace('+', '')}",
                f"📈 Lãi: {self.format_currency(total_profit_all)} ({total_roi_all:+.1f}%)",
                f"⬆️ Tổng nạp: {self.format_currency(total_deposit).replace('+', '')}",
                f"⬇️ Tổng rút: {self.format_currency(total_withdraw).replace('+', '')}",
                f"🏆 Mã tốt nhất: {best['ticker']} ({best['roi']:+.1f}%)",
                f"📉 Mã kém nhất: {worst['ticker']} ({worst['roi']:+.1f}%)",
                f"📊 Tỉ trọng lớn nhất: {biggest['ticker']} ({(biggest['value']/total_market_value*100):.1f}%)",
                "────────────", "\n────────────\n".join(stock_details), "────────────"
            ]
            return "\n".join(lines)
