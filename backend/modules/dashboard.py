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
            # 1. Tính vốn nạp rút thực tế (Chỉ tính tại ví Mẹ - CASH)
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='IN'", (user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='OUT'", (user_id,))
            t_out = cursor.fetchone()[0] or 0
            
            # 2. Lấy giá trị hàng trong kho (Portfolio)
            cursor.execute("SELECT SUM(total_qty * avg_price) FROM portfolio WHERE user_id=?", (user_id,))
            inv_value = cursor.fetchone()[0] or 0
            
            # 3. Lấy tiền mặt tại tất cả các ví
            cash_mom = repo.get_available_cash(user_id, 'CASH')
            bp_stock = repo.get_available_cash(user_id, 'STOCK')
            bp_crypto = repo.get_available_cash(user_id, 'CRYPTO')
            
            # CÔNG THỨC CHUẨN: Tổng tài sản = Tiền mặt (tất cả các túi) + Giá trị hàng hóa
            total_assets = cash_mom + bp_stock + bp_crypto + inv_value
            net_invested = t_in - t_out
            pnl = total_assets - net_invested
            roi = (pnl / net_invested * 100) if net_invested > 0 else 0
            total_bp = cash_mom + bp_stock + bp_crypto
            cash_pct = (total_bp / total_assets * 100) if total_assets > 0 else 0

        return (
            "🏦 <b>HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Tổng tài sản: <b>{self.format_smart(total_assets)}</b>\n"
            f"⬆️ Tổng nạp: {self.format_smart(t_in)}\n"
            f"📈 Lãi/Lỗ tổng: <b>{self.format_smart(pnl)} ({roi:+.1f}%)</b>\n\n"
            "📦 <b>PHÂN BỔ NGUỒN VỐN:</b>\n"
            f"• Vốn Đầu tư (Mẹ): {self.format_smart(cash_mom)} 🟢\n"
            f"• Ví Stock: (💵 {self.format_smart(bp_stock)})\n"
            f"• Ví Crypto: (💵 {self.format_smart(bp_crypto)})\n\n"
            "🛡️ <b>SỨC KHỎE DANH MỤC:</b>\n"
            f"• Sức mua tổng: <b>{self.format_smart(total_bp)}</b>\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
