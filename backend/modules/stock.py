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

    def get_group_report(self):
        """Layout: BÁO CÁO HIỆU SUẤT TÀI CHÍNH"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            cursor.execute("SELECT * FROM portfolio WHERE user_id = ? AND asset_type = 'STOCK'", (self.user_id,))
            rows = cursor.fetchall()

            if not rows: return "❌ <b>Chưa có dữ liệu cổ phiếu.</b>"

            total_mkt_val = 0
            total_cost = 0
            ticker_stats = []

            for r in rows:
                if r['total_qty'] <= 0: continue
                price = price_map.get(r['ticker'], r['avg_price'])
                mkt_val = r['total_qty'] * price * 1000
                cost = r['total_qty'] * r['avg_price'] * 1000
                
                total_mkt_val += mkt_val
                total_cost += cost
                ticker_stats.append({'tk': r['ticker'], 'val': mkt_val})

            profit = total_mkt_val - total_cost
            roi = (profit / total_cost * 100) if total_cost > 0 else 0
            
            ticker_stats.sort(key=lambda x: x['val'], reverse=True)
            lines = [
                "📈 <b>BÁO CÁO HIỆU SUẤT TÀI CHÍNH</b>",
                "━━━━━━━━━━━━━━━━━━━",
                f"💵 <b>Giá trị hiện tại:</b> {self.format_currency(total_mkt_val).replace('+', '')}",
                f"💰 <b>Giá vốn tổng:</b> {self.format_currency(total_cost).replace('+', '')}",
                f"📊 <b>Lãi/lỗ ròng:</b> <b>{self.format_currency(profit)}</b>",
                f"🚀 <b>ROI:</b> <b>{roi:+.2f}%</b>",
                "",
                "💎 <b>PHÂN BỔ TỈ TRỌNG:</b>"
            ]
            for item in ticker_stats:
                pct = (item['val'] / total_mkt_val * 100) if total_mkt_val > 0 else 0
                bar = "🔵" * int(pct/10) + "⚪" * (10 - int(pct/10))
                lines.append(f"• {item['tk']}: {pct:.1f}%\n  {bar}")

            return "\n".join(lines)

    def run(self):
        """Layout: DANH MỤC CHI TIẾT (10 CHỈ SỐ)"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}
            
            cursor.execute("SELECT * FROM portfolio WHERE user_id = ? AND asset_type = 'STOCK'", (self.user_id,))
            rows = cursor.fetchall()

            if not rows: return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nChưa có dữ liệu."

            stock_details = []
            total_val = 0
            total_cost = 0
            stats = []

            for r in rows:
                if r['total_qty'] <= 0: continue
                curr_p = price_map.get(r['ticker'], r['avg_price'])
                mkt_v = r['total_qty'] * curr_p * 1000
                cost_v = r['total_qty'] * r['avg_price'] * 1000
                profit = mkt_v - cost_v
                roi = (profit / cost_v * 100) if cost_v > 0 else 0
                
                total_val += mkt_v
                total_cost += cost_v
                stats.append({'ticker': r['ticker'], 'roi': roi, 'value': mkt_v})

                stock_details.append(
                    f"<b>{r['ticker']}</b>\nSL: {r['total_qty']:,.0f}\nVốn TB: {r['avg_price']:,.1f}\n"
                    f"Giá HT: {curr_p:,.1f}\nGiá trị: {self.format_currency(mkt_v).replace('+', '')}\n"
                    f"Lãi: {self.format_currency(profit)} ({roi:+.1f}%)"
                )

            # Các chỉ số phụ
            best = max(stats, key=lambda x: x['roi'])
            biggest = max(stats, key=lambda x: x['value'])

            lines = [
                "📊 <b>DANH MỤC CỔ PHIẾU</b>",
                f"💰 Tổng giá trị: {self.format_currency(total_val).replace('+', '')}",
                f"📈 Lãi tổng: {self.format_currency(total_val - total_cost)} ({((total_val-total_cost)/total_cost*100):+.1f}%)",
                f"🏆 Tốt nhất: {best['ticker']} ({best['roi']:+.1f}%)",
                f"📊 Tỉ trọng lớn: {biggest['ticker']}",
                "────────────", 
                "\n────────────\n".join(stock_details),
                "🏠 <i>Quay về trang chủ</i>"
            ]
            return "\n".join(lines)
