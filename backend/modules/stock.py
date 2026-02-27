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
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='STOCK' AND type='TRANSFER_IN'", (user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='STOCK' AND type='TRANSFER_OUT'", (user_id,))
            t_out = cursor.fetchone()[0] or 0
            cursor.execute("SELECT ticker, total_qty, avg_price FROM portfolio WHERE user_id=? AND asset_type='STOCK' AND total_qty > 0", (user_id,))
            rows = [dict(r) for r in cursor.fetchall()]

        total_cost = sum(r['total_qty'] * r['avg_price'] for r in rows)
        total_val = total_cost + bp_stock
        sorted_rows = sorted(rows, key=lambda x: x['total_qty'] * x['avg_price'], reverse=True)

        res = [
            "📊 <b>DANH MỤC CỔ PHIẾU</b>\n━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng giá trị: <b>{self.format_smart(total_val)}</b>",
            f"💵 Vốn đầu tư: {self.format_smart(total_cost)}",
            f"💸 Sức mua: <b>{self.format_smart(bp_stock)}</b>\n━━━━━━━━━━━━━━━━━━━",
            f"⬆️ Tổng nạp ví: {self.format_smart(t_in)}",
            f"⬇️ Tổng rút ví: {self.format_smart(t_out)}",
            f"📊 Tỉ trọng lớn: {sorted_rows[0]['ticker'] if sorted_rows else '---'}\n━━━━━━━━━━━━━━━━━━━"
        ]
        if not rows:
            res.append("<i>(Sếp chưa nắm giữ mã nào)</i>")
        else:
            for r in sorted_rows:
                res.append(f"────────────\n💎 <b>{r['ticker']}</b>\n• SL: {r['total_qty']:,.0f} | Vốn TB: {r['avg_price']:,.0f}\n• GT: {self.format_smart(r['total_qty'] * r['avg_price'])}")
        return "\n".join(res)
