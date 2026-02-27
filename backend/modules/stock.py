# backend/modules/stock.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class StockModule(BaseModule):
    def format_smart(self, value):
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1e9: return f"{sign}{value/1e9:.2f} tỷ"
        if abs_v >= 1e6: return f"{sign}{value/1e6:,.1f}tr"
        return f"{sign}{value:,.0f}đ"

    def run(self):
        user_id = self.user_id
        # Lấy sức mua thực tế từ Repository
        bp_stock = repo.get_available_cash(user_id, 'STOCK')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Thống kê dòng tiền nạp/rút riêng của ví Stock
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN type = 'TRANSFER_IN' THEN total_value ELSE 0 END),
                    SUM(CASE WHEN type = 'TRANSFER_OUT' THEN total_value ELSE 0 END)
                FROM transactions WHERE user_id=? AND asset_type='STOCK'
            """, (user_id,))
            t_in, t_out = cursor.fetchone()
            t_in = t_in or 0
            t_out = t_out or 0
            
            # 2. Lấy danh sách danh mục hiện có
            cursor.execute("""
                SELECT ticker, total_qty, avg_price 
                FROM portfolio 
                WHERE user_id=? AND asset_type='STOCK' AND total_qty > 0
            """, (user_id,))
            rows = [dict(r) for r in cursor.fetchall()]

        # 3. Tính toán giá trị vốn và sắp xếp tỉ trọng
        total_cost = sum(r['total_qty'] * r['avg_price'] for r in rows)
        total_val = total_cost + bp_stock
        sorted_rows = sorted(rows, key=lambda x: x['total_qty'] * x['avg_price'], reverse=True)

        # 4. Xây dựng Layout Full Option cho CEO
        res = [
            "📊 <b>DANH MỤC CỔ PHIẾU</b>",
            "━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng giá trị: <b>{self.format_smart(total_val)}</b>",
            f"💵 Vốn đầu tư: {self.format_smart(total_cost)}",
            f"💸 Sức mua: <b>{self.format_smart(bp_stock)}</b>",
            f"📈 Lãi/Lỗ: 0đ (+0.0%)",
            "━━━━━━━━━━━━━━━━━━━",
            f"⬆️ Tổng nạp ví: {self.format_smart(t_in)}",
            f"⬇️ Tổng rút ví: {self.format_smart(t_out)}",
            f"🏆 Mã tốt nhất: {sorted_rows[0]['ticker'] if sorted_rows else '---'}",
            f"📊 Tỉ trọng lớn: {sorted_rows[0]['ticker'] if sorted_rows else '---'}",
            "━━━━━━━━━━━━━━━━━━━"
        ]

        if not rows:
            res.insert(-1, "\n<i>(Sếp chưa nắm giữ mã nào trong ví này)</i>")
        else:
            for r in sorted_rows:
                val = r['total_qty'] * r['avg_price']
                res.append(
                    f"────────────\n"
                    f"💎 <b>{r['ticker']}</b>\n"
                    f"• SL: {r['total_qty']:,.0f} | Vốn TB: {r['avg_price']:,.0f}\n"
                    f"• GT: {self.format_smart(val)}"
                )
        
        return "\n".join(res)
