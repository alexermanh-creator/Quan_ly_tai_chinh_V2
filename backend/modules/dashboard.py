# backend/modules/dashboard.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo

class DashboardModule(BaseModule):
    def format_smart(self, value):
        """Định dạng thông minh: Tỷ hoặc Triệu (.M) tùy độ lớn"""
        abs_val = abs(value)
        sign = "-" if value < 0 else ""
        if abs_val >= 1_000_000_000:
            return f"{sign}{abs_val / 1_000_000_000:.2f} tỷ"
        return f"{sign}{abs_val / 1_000_000:,.1f}M"

    def run(self):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Dữ liệu nạp/rút từ ngoại biên vào hệ thống (Ví Mẹ)
            # Chỉ tính các lệnh nạp/rút thực tế, không tính chuyển nội bộ
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'OUT'", (self.user_id,))
            t_out = cursor.fetchone()[0] or 0
            
            # 2. Giá trị tài sản đang nắm giữ trong các Ví Con (Giá trị thị trường)
            # Lấy giá manual để tính mkt_value thay vì chỉ dùng giá vốn (cost)
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            cursor.execute("SELECT ticker, asset_type, total_qty, avg_price FROM portfolio WHERE user_id = ?", (self.user_id,))
            portfolio_rows = cursor.fetchall()

            stock_mkt_val = 0
            crypto_mkt_val = 0
            other_mkt_val = 0

            for r in portfolio_rows:
                qty = r['total_qty']
                if qty <= 0: continue
                
                ticker = r['ticker']
                a_type = r['asset_type']
                curr_p = price_map.get(ticker, r['avg_price'])
                
                # Hệ số nhân đặc thù
                multiplier = 1000 if a_type == 'STOCK' else 1
                val = qty * curr_p * multiplier

                if a_type == 'STOCK': stock_mkt_val += val
                elif a_type == 'CRYPTO': crypto_mkt_val += val
                else: other_mkt_val += val
            
            # 3. Sức mua khả dụng (Tiền mặt thực tế tại từng Ví)
            cash_mom = repo.get_available_cash(self.user_id, 'CASH')
            buying_power_stock = repo.get_available_cash(self.user_id, 'STOCK')
            buying_power_crypto = repo.get_available_cash(self.user_id, 'CRYPTO')
            
            # 4. Tính toán chỉ số tổng
            total_assets = cash_mom + stock_mkt_val + crypto_mkt_val + other_mkt_val + buying_power_stock + buying_power_crypto
            net_invested = t_in - t_out
            pnl_total = total_assets - net_invested
            roi = (pnl_total / net_invested * 100) if net_invested > 0 else 0
            
            # Tỷ lệ tiền mặt tổng (bao gồm cả tiền mặt trong ví con)
            total_cash = cash_mom + buying_power_stock + buying_power_crypto
            cash_pct = (total_cash / total_assets * 100) if total_assets > 0 else 0

        # Layout UX DASHBOARD TỔNG (Nâng cấp quản trị đa lớp)
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
            f"• Ví Stock: {self.format_smart(stock_mkt_val)} (💵 {self.format_smart(buying_power_stock)})",
            f"• Ví Crypto: {self.format_smart(crypto_mkt_val)} (💵 {self.format_smart(buying_power_crypto)})",
            f"• Ví Khác: {self.format_smart(other_mkt_val)}",
            "",
            "🛡️ <b>SỨC KHỎE DANH MỤC:</b>",
            f"• Trạng thái: {'An toàn' if cash_pct > 30 else 'Cần chú ý'} (Tiền mặt: {cash_pct:.0f}%)",
            f"• Sức mua tổng: {self.format_smart(total_cash)}",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        return "\n".join(lines)
