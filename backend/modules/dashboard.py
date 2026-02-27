# backend/modules/dashboard.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class DashboardModule(BaseModule):
    def format_smart(self, value):
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1e9: return f"{sign}{value/1e9:.2f} tỷ"
        if abs_v >= 1e6: return f"{sign}{value/1e6:,.1f}tr"
        return f"{sign}{abs_v:,.0f}đ"

    def run(self):
        user_id = self.user_id
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='IN'", (user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='OUT'", (user_id,))
            t_out = cursor.fetchone()[0] or 0
            cursor.execute("SELECT asset_type, SUM(total_qty * avg_price) FROM portfolio WHERE user_id=? GROUP BY asset_type", (user_id,))
            costs = {r[0]: r[1] for r in cursor.fetchall()}
            
            cash_mom = repo.get_available_cash(user_id, 'CASH')
            bp_stock = repo.get_available_cash(user_id, 'STOCK')
            bp_crypto = repo.get_available_cash(user_id, 'CRYPTO')
            
            total_assets = cash_mom + bp_stock + bp_crypto + sum(costs.values())
            net_invested = t_in - t_out
            pnl = total_assets - net_invested
            roi = (pnl / net_invested * 100) if net_invested > 0 else 0

        res = [
            "🏦 <b>HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0</b>",
            "━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng tài sản: <b>{self.format_smart(total_assets)}</b>",
            f"⬆️ Tổng nạp: {self.format_smart(t_in)}",
            f"📈 Lãi/Lỗ tổng: <b>{self.format_smart(pnl)} ({roi:+.1f}%)</b>",
            "",
            "📦 <b>PHÂN BỔ NGUỒN VỐN:</b>",
            f"• Vốn Đầu tư (Mẹ): {self.format_smart(cash_mom)} 🟢",
            f"• Ví Stock: {self.format_smart(costs.get('STOCK', 0))} (💵 {self.format_smart(bp_stock)})",
            f"• Ví Crypto: {self.format_smart(costs.get('CRYPTO', 0))} (💵 {self.format_smart(bp_crypto)})",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        return "\n".join(res)
