# backend/modules/dashboard.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class DashboardModule(BaseModule):
    def format_smart(self, value):
        """Định dạng thông minh: Tỷ hoặc tr tùy độ lớn"""
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1_000_000_000:
            return f"{sign}{abs_v/1_000_000_000:.2f} tỷ"
        if abs_v >= 1_000_000:
            return f"{sign}{abs_v/1_000_000:,.1f}tr"
        return f"{sign}{abs_v:,.0f}đ"

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Dòng tiền gốc hệ thống (Nạp/Rút vào Ví Mẹ)
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='OUT'", (self.user_id,))
            t_out = cursor.fetchone()[0] or 0
            
            # 2. Giá trị tài sản (Portfolio)
            cursor.execute("SELECT asset_type, SUM(total_qty * avg_price) FROM portfolio WHERE user_id=? GROUP BY asset_type", (self.user_id,))
            costs = {r[0]: r[1] for r in cursor.fetchall()}
            
            # Quy đổi Stock (x1000) và các loại khác
            stock_mkt_val = costs.get('STOCK', 0) * 1000
            crypto_mkt_val = costs.get('CRYPTO', 0)
            other_mkt_val = costs.get('OTHER', 0)
            
            # 3. Tiền mặt tại các ví (Sức mua)
            cash_mom = repo.get_available_cash(self.user_id, 'CASH')
            bp_stock = repo.get_available_cash(self.user_id, 'STOCK')
            bp_crypto = repo.get_available_cash(self.user_id, 'CRYPTO')
            
            # 4. Tính toán chỉ số tổng lực
            total_assets = cash_mom + stock_mkt_val + crypto_mkt_val + other_mkt_val + bp_stock + bp_crypto
            net_invested = t_in - t_out
            pnl_total = total_assets - net_invested
            roi = (pnl_total / net_invested * 100) if net_invested > 0 else 0
            
            total_buying_power = cash_mom + bp_stock + bp_crypto
            cash_pct = (total_buying_power / total_assets * 100) if total_assets > 0 else 0

        # LAYOUT FULL OPTION ĐÚNG Ý CEO
        lines = [
            "🏦 <b>HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0</b>",
            "━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng tài sản: <b>{self.format_smart(total_assets)}</b>",
            f"⬆️ Tổng nạp: {self.format_smart(t_in)}",
            f"⬇️ Tổng rút: {self.format_smart(t_out)}",
            f"📈 Lãi/Lỗ tổng: <b>{self.format_smart(pnl_total)} ({roi:+.1f}%)</b>",
            "",
            "📦 <b>PHÂN BỔ NGUỒN VỐN:</b>",
            f"• Vốn Đầu tư (Mẹ): {self.format_smart(cash_mom)} 🟢",
            f"• Ví Stock: {self.format_smart(stock_mkt_val)} (💵 {self.format_smart(bp_stock)})",
            f"• Ví Crypto: {self.format_smart(crypto_mkt_val)} (💵 {self.format_smart(bp_crypto)})",
            f"• Ví Khác: {self.format_smart(other_mkt_val)}",
            "",
            "🛡️ <b>SỨC KHỎE DANH MỤC:</b>",
            f"• Trạng thái: {'An toàn' if cash_pct > 30 else 'Cần chú ý'} (Tiền mặt: {cash_pct:.0f}%)",
            f"• Sức mua tổng: <b>{self.format_smart(total_buying_power)}</b>",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        return "\n".join(lines)
