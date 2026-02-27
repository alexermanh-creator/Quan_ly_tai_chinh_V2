# backend/modules/stock.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class StockModule(BaseModule):
    def format_smart(self, value):
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1e9: return f"{sign}{value/1e9:.2f} tỷ"
        return f"{sign}{value/1e6:,.1f}tr"

    def run(self, mode="REPORT"):
        user_id = self.user_id
        bp_stock = repo.get_available_cash(user_id, 'STOCK')
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='STOCK' AND type='TRANSFER_IN'", (user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT ticker, total_qty, avg_price FROM portfolio WHERE user_id=? AND asset_type='STOCK' AND total_qty > 0", (user_id,))
            rows = [dict(r) for r in cursor.fetchall()]

        total_cost = sum(r['total_qty'] * r['avg_price'] for r in rows)
        # Giả lập lãi lỗ dựa trên chênh lệch (Trong thực tế sẽ dùng API)
        res_pnl = 0 # Ở bản này sếp chưa nạp giá mới nên tạm thời vẫn 0
        
        if mode == "ANALYZE":
            if not rows: return "❌ Sếp chưa nắm giữ mã nào để phân tích."
            analyze = ["📈 <b>PHÂN TÍCH TỈ TRỌNG</b>\n━━━━━━━━━━━━━━━━━━━"]
            for r in rows:
                pct = (r['total_qty'] * r['avg_price'] / total_cost * 100) if total_cost > 0 else 0
                analyze.append(f"• <b>{r['ticker']}</b>: {pct:.1f}% danh mục")
            return "\n".join(analyze)

        res = [
            "📊 <b>DANH MỤC CỔ PHIẾU</b>\n━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng giá trị: <b>{self.format_smart(total_cost + bp_stock)}</b>",
            f"💵 Vốn đầu tư: {self.format_smart(total_cost)}",
            f"💸 Sức mua: <b>{self.format_smart(bp_stock)}</b>",
            f"📈 Lãi/Lỗ: 0đ (+0.0%)\n━━━━━━━━━━━━━━━━━━━",
            f"📊 Tỉ trọng lớn: {max(rows, key=lambda x: x['total_qty']*x['avg_price'])['ticker'] if rows else '---'}\n━━━━━━━━━━━━━━━━━━━"
        ]
        for r in rows:
            res.append(f"────────────\n💎 <b>{r['ticker']}</b>\n• SL: {r['total_qty']:,.0f} | Vốn TB: {r['avg_price']:,.0f}\n• GT: {self.format_smart(r['total_qty'] * r['avg_price'])}")
        return "\n".join(res)
