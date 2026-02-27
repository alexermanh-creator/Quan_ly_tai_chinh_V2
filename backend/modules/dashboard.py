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
        return f"{sign}{value:,.0f}đ"

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='OUT'", (self.user_id,))
            t_out = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT asset_type, SUM(total_qty * avg_price) FROM portfolio WHERE user_id=? GROUP BY asset_type", (self.user_id,))
            costs = {r[0]: r[1] for r in cursor.fetchall()}
            
            # Logic Chuyên gia: DB đã lưu VNĐ chuẩn, tuyệt đối không nhân thêm hệ số ở đây
            stock_mkt_val = costs.get('STOCK', 0)
            crypto_mkt_val = costs.get('CRYPTO', 0)
            other_mkt_val = costs.get('OTHER', 0)
            
            cash_mom = repo.get_available_cash(self.user_id, 'CASH')
            bp_stock = repo.get_available_cash(self.user_id, 'STOCK')
            bp_crypto = repo.get_available_cash(self.user_id, 'CRYPTO')
            
            total_assets = cash_mom + stock_mkt_val + crypto_mkt_val + other_mkt_val + bp_stock + bp_crypto
            net_invested = t_in - t_out
            pnl_total = total_assets - net_invested
            roi = (pnl_total / net_invested * 100) if net_invested > 0 else 0
            total_bp = cash_mom + bp_stock + bp_crypto
            cash_pct = (total_bp / total_assets * 100) if total_assets > 0 else 0

        lines = [
            "🏦 <b>HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0</b>",
            "━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng tài sản: <b>{self.format_smart(total_assets)}</b>",
            f"📈 Lãi/Lỗ tổng: <b>{self.format_smart(pnl_total)} ({roi:+.1f}%)</b>",
            "",
            "📦 <b>PHÂN BỔ NGUỒN VỐN:</b>",
            f"• Vốn Đầu đầu (Mẹ): {self.format_smart(cash_mom)} 🟢",
            f"• Ví Stock: {self.format_smart(stock_mkt_val)} (💵 {self.format_smart(bp_stock)})",
            f"• Ví Crypto: {self.format_smart(crypto_mkt_val)} (💵 {self.format_smart(bp_crypto)})",
            "",
            "🛡️ <b>SỨC KHỎE DANH MỤC:</b>",
            f"• Trạng thái: {'An toàn' if cash_pct > 30 else 'Cần chú ý'} (Tiền mặt: {cash_pct:.0f}%)",
            f"• Sức mua tổng: <b>{self.format_smart(total_bp)}</b>",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        return "\n".join(lines)
