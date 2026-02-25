# backend/modules/dashboard.py
from backend.interface import BaseModule
from datetime import datetime

class DashboardModule(BaseModule):
    def format_smart_number(self, num):
        """Hàm định dạng số thông minh chuẩn CTO: Tỷ, Triệu hoặc đồng"""
        abs_num = abs(num)
        if abs_num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f} tỷ"
        elif abs_num >= 1_000_000:
            return f"{num / 1_000_000:.1f} triệu"
        return f"{num:,.0f} đ"

    def run(self):
        """Xây dựng nội dung Dashboard tổng thể với dòng tiền thực tế"""
        # 1. Lấy dữ liệu danh mục từ các Engine
        stock_data = self.get_summary_data('STOCK')
        crypto_data = self.get_summary_data('CRYPTO')
        
        # 2. Lấy toàn bộ lịch sử để tính dòng tiền mặt (Cash Flow)
        transactions = self.repo.get_latest_transactions(self.user_id, limit=5000)
        
        total_in = sum(t['total_value'] for t in transactions if t['type'] == 'IN')
        total_out = sum(t['total_value'] for t in transactions if t['type'] == 'OUT')
        total_buy = sum(t['total_value'] for t in transactions if t['type'] == 'BUY')
        total_sell = sum(t['total_value'] for t in transactions if t['type'] == 'SELL')

        # 3. Tính toán tiền mặt thực tế (Core Cash Logic)
        # Tiền còn lại = (Tiền vào hệ thống) - (Tiền rời hệ thống)
        cash_balance = (total_in + total_sell) - (total_out + total_buy)

        # 4. Tính toán tổng tài sản thị trường (Net Worth)
        stock_mkt_val = stock_data['summary']['total_value']
        crypto_mkt_val = crypto_data['summary']['total_value']
        other_val = 0 # Sẽ kết nối ở module Tài sản khác
        
        # Tổng tài sản = Tiền mặt + Giá trị Chứng khoán + Giá trị Crypto
        total_net_worth = cash_balance + stock_mkt_val + crypto_mkt_val + other_val

        # 5. Tính toán lãi/lỗ danh mục tài sản (Không tính tiền mặt)
        total_cost = stock_data['summary']['total_cost'] + crypto_data['summary']['total_cost']
        total_profit = (stock_mkt_val + crypto_mkt_val) - total_cost
        profit_percent = (total_profit / total_cost * 100) if total_cost > 0 else 0
        profit_icon = "🟢" if total_profit >= 0 else "🔴"

        # 6. Mục tiêu tài chính
        target_val = 500_000_000 # Config này sẽ đưa vào DB sau
        progress = (total_net_worth / target_val * 100) if target_val > 0 else 0
        debt_to_target = max(0, target_val - total_net_worth)

        # --- GIAO DIỆN TEXT HIỂN THỊ ---
        lines = [
            "💼 <b>TÀI SẢN CỦA BẠN</b>",
            f"💰 Tổng tài sản: <b>{self.format_smart_number(total_net_worth)}</b>",
            f"📈 Lãi danh mục: {self.format_smart_number(total_profit)} ({profit_icon} {profit_percent:+.1f}%)",
            "━━━━━━━━━━━━━━━━━━━",
            f"🏦 Tiền mặt: <code>{self.format_smart_number(cash_balance)}</code>",
            f"📊 Cổ phiếu: <code>{self.format_smart_number(stock_mkt_val)}</code>",
            f"🪙 Crypto: <code>{self.format_smart_number(crypto_mkt_val)}</code>",
            "",
            f"🎯 Mục tiêu: {self.format_smart_number(target_val)}",
            f"🏁 Tiến độ: {progress:.1f}% | Còn thiếu: {self.format_smart_number(debt_to_target)}",
            "",
            f"⬆️ Tổng nạp: {self.format_smart_number(total_in)}",
            f"⬇️ Tổng rút: {self.format_smart_number(total_out)}",
            "",
            "🏠 <i>Bấm các nút dưới để quản lý chi tiết.</i>"
        ]

        return "\n".join(lines)
