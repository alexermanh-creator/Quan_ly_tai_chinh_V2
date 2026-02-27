# backend/modules/stock.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class StockModule(BaseModule):
    def format_smart(self, value):
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1_000_000_000: return f"{sign}{value/1_000_000_000:.2f} tỷ"
        return f"{sign}{value/1_000_000:,.1f}tr"

    def run(self):
        user_id = self.user_id
        bp_stock = repo.get_available_cash(user_id, 'STOCK')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='STOCK' AND type='TRANSFER_IN'", (user_id,))
            t_in = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT ticker, total_qty, avg_price FROM portfolio WHERE user_id=? AND asset_type='STOCK' AND total_qty > 0", (user_id,))
            rows = cursor.fetchall()

        # GIÁ TRỊ VỐN = SL * Vốn TB (avg_price đã được tính chuẩn ở Repository)
        total_cost = sum(r['total_qty'] * r['avg_price'] for r in rows) if rows else 0
        
        res = [
            "📊 <b>DANH MỤC CỔ PHIẾU</b>",
            "━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng giá trị: {self.format_smart(total_cost + bp_stock)}",
            f"💵 Tổng vốn đầu tư: {self.format_smart(total_cost)}",
            f"💸 Sức mua: <b>{self.format_smart(bp_stock)}</b>",
            f"📈 Lãi/Lỗ: 0.0tr (+0.0%)",
            f"⬆️ Tổng nạp ví: {self.format_smart(t_in)}",
            "━━━━━━━━━━━━━━━━━━━"
        ]

        if not rows:
            res.insert(-1, "\n<i>(Sếp chưa nắm giữ mã nào trong danh mục này)</i>")
        else:
            for r in rows:
                val = r['total_qty'] * r['avg_price']
                res.append(f"────────────\n💎 <b>{r['ticker']}</b>\n• SL: {r['total_qty']:,.0f} | Vốn TB: {r['avg_price']:,.1f}\n• Giá trị: {self.format_smart(val)}")

        return "\n".join(res)
