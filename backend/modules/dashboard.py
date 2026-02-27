# backend/modules/dashboard.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class DashboardModule(BaseModule):
    def format_smart(self, value):
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1_000_000_000: return f"{sign}{abs_v/1_000_000_000:.2f} tỷ"
        if abs_v >= 1_000_000: return f"{sign}{abs_v/1_000_000:,.1f}tr"
        return f"{sign}{abs_v:,.0f}đ"

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Tính vốn nạp thực tế (Ví Mẹ)
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='OUT'", (self.user_id,))
            t_out = cursor.fetchone()[0] or 0
            
            # Sức mua tại các ví
            cash_mom = repo.get_available_cash(self.user_id, 'CASH')
            bp_stock = repo.get_available_cash(self.user_id, 'STOCK')
            bp_crypto = repo.get_available_cash(self.user_id, 'CRYPTO')
            
            # Giá trị thị trường tài sản
            cursor.execute("SELECT asset_type, SUM(total_qty * avg_price) FROM portfolio WHERE user_id=? GROUP BY asset_type", (self.user_id,))
            costs = {r[0]: r[1] for r in cursor.fetchall()}
            
            stock_v = costs.get('STOCK', 0) * 1000
            crypto_v = costs.get('CRYPTO', 0)
            
            total = cash_mom + stock_v + crypto_v + bp_stock + bp_crypto
            pnl = total - (t_in - t_out)
            total_cash = cash_mom + bp_stock + bp_crypto

        return (
            f"🏦 <b>HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Tổng: <b>{self.format_smart(total)}</b>\n"
            f"📈 Lãi/Lỗ: {self.format_smart(pnl)}\n\n"
            f"📦 <b>PHÂN BỔ:</b>\n"
            f"• Vốn Mẹ: {self.format_smart(cash_mom)} 🟢\n"
            f"• Ví Stock: {self.format_smart(stock_v)} (💵 {self.format_smart(bp_stock)})\n"
            f"• Ví Crypto: {self.format_smart(crypto_v)} (💵 {self.format_smart(bp_crypto)})\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
