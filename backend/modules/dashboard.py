# backend/modules/dashboard.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class DashboardModule(BaseModule):
    def format_smart(self, value):
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1e9: return f"{sign}{abs_v/1e9:.2f} tỷ"
        return f"{sign}{abs_v/1e6:,.1f}tr"

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='OUT'", (self.user_id,))
            t_out = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT asset_type, SUM(total_qty * avg_price) FROM portfolio WHERE user_id=? GROUP BY asset_type", (self.user_id,))
            costs = {r[0]: r[1] for r in cursor.fetchall()}
            
            cash_mom = repo.get_available_cash(self.user_id, 'CASH')
            bp_stock = repo.get_available_cash(self.user_id, 'STOCK')
            bp_crypto = repo.get_available_cash(self.user_id, 'CRYPTO')
            
            stock_v, crypto_v = costs.get('STOCK', 0)*1000, costs.get('CRYPTO', 0)
            total = cash_mom + stock_v + crypto_v + bp_stock + bp_crypto
            pnl = total - (t_in - t_out)

        return f"🏦 <b>HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0</b>\n━━━━━━━━━━━━━━━━━━━\n💰 Tổng: <b>{self.format_smart(total)}</b>\n📈 Lãi/Lỗ: <b>{self.format_smart(pnl)}</b>\n\n📦 <b>PHÂN BỔ:</b>\n• Vốn Mẹ: {self.format_smart(cash_mom)} 🟢\n• Ví Stock: {self.format_smart(stock_v)} (💵 {self.format_smart(bp_stock)})\n• Ví Crypto: {self.format_smart(crypto_v)} (💵 {self.format_smart(bp_crypto)})\n━━━━━━━━━━━━━━━━━━━"
