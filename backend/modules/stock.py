# backend/modules/stock.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class StockModule(BaseModule):
    def format_smart(self, value):
        abs_v = abs(value)
        if abs_v >= 1e9: return f"{value/1e9:.2f} tỷ"
        return f"{value/1e6:,.1f}tr"

    def run(self):
        user_id = self.user_id
        bp_stock = repo.get_available_cash(user_id, 'STOCK')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, total_qty, avg_price FROM portfolio WHERE user_id=? AND asset_type='STOCK' AND total_qty > 0", (user_id,))
            rows = [dict(r) for r in cursor.fetchall()]

        total_cost = sum(r['total_qty'] * r['avg_price'] for r in rows)
        
        res = [
            "📊 <b>DANH MỤC CỔ PHIẾU</b>",
            "━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng giá trị: <b>{self.format_smart(total_cost + bp_stock)}</b>",
            f"💵 Tổng vốn đầu tư: {self.format_smart(total_cost)}",
            f"💸 Sức mua: <b>{self.format_smart(bp_stock)}</b>",
            f"📊 Tỉ trọng lớn nhất: {rows[0]['ticker'] if rows else '---'}",
            "━━━━━━━━━━━━━━━━━━━"
        ]

        if not rows:
            res.insert(-1, "\n<i>(Sếp chưa nắm giữ mã nào trong ví này)</i>")
        else:
            for r in rows:
                val = r['total_qty'] * r['avg_price']
                res.append(f"────────────\n💎 <b>{r['ticker']}</b>\n• SL: {r['total_qty']:,.0f} | Vốn TB: {r['avg_price']:,.0f}\n• GT: {self.format_smart(val)}")
        
        return "\n".join(res)
