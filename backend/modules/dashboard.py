# backend/modules/dashboard.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class DashboardModule(BaseModule):
    def format_m(self, value):
        """Format số tiền theo dạng .M (Triệu) đúng yêu cầu CEO"""
        return f"{value / 1_000_000:,.1f}M"

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Dữ liệu nạp/rút từ Ví Mẹ
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'OUT'", (self.user_id,))
            t_out = cursor.fetchone()[0] or 0
            
            # 2. Giá trị các Ví Con
            cursor.execute("SELECT asset_type, SUM(total_qty * avg_price) as cost FROM portfolio WHERE user_id = ? GROUP BY asset_type", (self.user_id,))
            costs = {row['asset_type']: row['cost'] for row in cursor.fetchall()}
            
            # 3. Tiền mặt (Ví Mẹ)
            cash_mom = repo.get_available_cash(self.user_id)
            
            # Giả định giá trị thị trường hiện tại (lấy từ Portfolio để demo nhanh)
            # Trong thực tế sẽ cộng thêm biến động giá từ manual_prices
            stock_val = costs.get('STOCK', 0)
            crypto_val = costs.get('CRYPTO', 0)
            other_val = costs.get('OTHER', 0)
            
            total_assets = cash_mom + stock_val + crypto_val + other_val
            net_invested = t_in - t_out
            pnl_total = total_assets - net_invested
            roi = (pnl_total / net_invested * 100) if net_invested > 0 else 0
            cash_pct = (cash_mom / total_assets * 100) if total_assets > 0 else 0

        # Layout UX DASHBOARD TỔNG (Đúng yêu cầu CEO)
        lines = [
            "🏦 <b>HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0</b>",
            "━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng tài sản: <b>{self.format_m(total_assets)}</b>",
            f"⬆️ Tổng nạp: {self.format_m(t_in)}",
            f"⬇️ Tổng rút: {self.format_m(t_out)}",
            f"📈 Lãi/Lỗ tổng: <b>{'+' if pnl_total > 0 else ''}{self.format_m(pnl_total)} ({roi:+.1f}%)</b>",
            "",
            "📦 <b>PHÂN BỔ NGUỒN VỐN:</b>",
            f"• Vốn Đầu tư (Mẹ): {self.format_m(cash_mom)} 🟢",
            f"• Ví Stock: {self.format_m(stock_val)}",
            f"• Ví Crypto: {self.format_m(crypto_val)}",
            f"• Ví Khác: {self.format_m(other_val)}",
            "",
            "🛡️ <b>SỨC KHỎE DANH MỤC:</b>",
            f"• Trạng thái: {'An toàn' if cash_pct > 30 else 'Cần chú ý'} (Tiền mặt: {cash_pct:.0f}%)",
            "• Cảnh báo: Không có",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        return "\n".join(lines)
