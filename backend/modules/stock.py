# backend/modules/stock.py
from backend.interface import BaseModule
from backend.database.db_manager import db

class StockModule(BaseModule):
    def format_m(self, value):
        return f"{value / 1_000_000:,.1f}M"

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Lấy giá manual để tính giá thị trường
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}
            
            # Lấy số dư cổ phiếu
            cursor.execute("SELECT * FROM portfolio WHERE user_id = ? AND asset_type = 'STOCK'", (self.user_id,))
            rows = cursor.fetchall()
            
            if not rows: return "📊 <b>DANH MỤC CỔ PHIẾU</b>\n\nChưa có dữ liệu."

            # Tính toán các chỉ số tổng của Ví Stock
            total_cost = sum(r['total_qty'] * r['avg_price'] * 1000 for r in rows)
            total_mkt = sum(r['total_qty'] * price_map.get(r['ticker'], r['avg_price']) * 1000 for r in rows)
            
            stock_details = []
            stats = []

            for r in rows:
                tk = r['ticker']
                curr_p = price_map.get(tk, r['avg_price'])
                mkt_val = r['total_qty'] * curr_p * 1000
                cost_val = r['total_qty'] * r['avg_price'] * 1000
                pnl = mkt_val - cost_val
                roi = (pnl / cost_val * 100) if cost_val > 0 else 0
                
                stats.append({'ticker': tk, 'roi': roi, 'value': mkt_val})
                
                # Layout chi tiết mã với đường kẻ mờ (────────────)
                detail = (
                    f"💎 <b>{tk}</b>\n"
                    f"• SL: {r['total_qty']:,.0f} | Vốn TB: {r['avg_price']:,.1f}\n"
                    f"• Hiện tại: {curr_p:,.1f} | GT: {self.format_m(mkt_val)}\n"
                    f"• Lãi: {pnl:,.0f}đ ({roi:+.1f}%)"
                )
                stock_details.append(detail)

            best = max(stats, key=lambda x: x['roi'])
            worst = min(stats, key=lambda x: x['roi'])
            biggest = max(stats, key=lambda x: x['value'])

        lines = [
            "📊 <b>DANH MỤC CỔ PHIẾU</b>",
            "━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng giá trị: {self.format_m(total_mkt)}",
            f"💵 Tổng vốn: {self.format_m(total_cost)}",
            f"💸 Sức mua: 0đ", # Có thể tích hợp thêm ví phụ sau
            f"📈 Lãi/Lỗ: {self.format_m(total_mkt - total_cost)} ({((total_mkt-total_cost)/total_cost*100):+.1f}%)",
            f"⬆️ Tổng nạp ví: {self.format_m(total_cost)}",
            f"⬇️ Tổng rút ví: 0đ",
            f"🏆 Mã tốt nhất: {best['ticker']} ({best['roi']:+.1f}%)",
            f"📉 Mã kém nhất: {worst['ticker']} ({worst['roi']:+.1f}%)",
            f"📊 Tỉ trọng lớn nhất: {biggest['ticker']} ({(biggest['value']/total_mkt*100):.1f}%)",
            "────────────",
            "\n────────────\n".join(stock_details),
            "━━━━━━━━━━━━━━━━━━━"
        ]
        return "\n".join(lines)
