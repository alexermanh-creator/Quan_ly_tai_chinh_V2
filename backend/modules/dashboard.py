# backend/modules/dashboard.py
from backend.interface import BaseModule
from datetime import datetime

class DashboardModule(BaseModule):
    def format_smart_number(self, num):
        """Hàm định dạng số thông minh: Tỷ, Triệu hoặc đồng"""
        abs_num = abs(num)
        if abs_num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f} tỷ"
        elif abs_num >= 1_000_000:
            return f"{num / 1_000_000:.1f} triệu"
        return f"{num:,.0f} đ"

    def run(self):
        """Xây dựng nội dung Dashboard tổng thể"""
        # 1. Lấy dữ liệu từ các Module lõi thông qua Engine
        stock_data = self.get_summary_data('STOCK')
        crypto_data = self.get_summary_data('CRYPTO')
        
        # Giả lập dữ liệu "Khác" và "Mục tiêu" (Sẽ kết nối DB ở phần Setting sau)
        other_val = 0 
        target_val = 500_000_000 # Ví dụ 500 triệu
        
        # 2. Tính toán các chỉ số Dòng tiền (Nạp/Rút) từ Repository
        transactions = self.repo.get_latest_transactions(self.user_id, limit=1000)
        total_in = sum(t['total_value'] for t in transactions if t['type'] == 'IN')
        total_out = sum(t['total_value'] for t in transactions if t['type'] == 'OUT')
        
        # 3. Tính toán tổng tài sản và lãi lỗ
        total_mkt_value = stock_data['summary']['total_value'] + crypto_data['summary']['total_value'] + other_val
        total_cost = stock_data['summary']['total_cost'] + crypto_data['summary']['total_cost']
        
        total_profit = total_mkt_value - total_cost
        profit_percent = (total_profit / total_cost * 100) if total_cost > 0 else 0
        profit_icon = "🟢" if total_profit >= 0 else "🔴"

        # 4. Tính toán tiền mặt (Cash)
        # Cash = (Nạp - Rút) - (Vốn đã mua) + (Tiền đã bán & Cổ tức tiền mặt)
        # Lưu ý: Engine đã tính realized_pnl bao gồm cả chênh lệch bán và cổ tức tiền
        cash_balance = (total_in - total_out) - total_cost # Logic cơ bản, sẽ hoàn thiện sâu hơn ở module Cash

        # 5. Tính tiến độ mục tiêu
        progress = (total_mkt_value / target_val * 100) if target_val > 0 else 0
        debt_to_target = max(0, target_val - total_mkt_value)

        # --- XÂY DỰNG GIAO DIỆN TEXT ---
        lines = [
            "💼 <b>TÀI SẢN CỦA BẠN</b>",
            f"💰 Tổng: <b>{self.format_smart_number(total_mkt_value)}</b>",
            f"📈 Lãi: {self.format_smart_number(total_profit)} ({profit_icon} {profit_percent:+.1f}%)",
            "",
            f"📊 Stock: {self.format_smart_number(stock_data['summary']['total_value'])}",
            f"🪙 Crypto: {self.format_smart_number(crypto_data['summary']['total_value'])}",
            f"🥇 Khác: {self.format_smart_number(other_val)}",
            "",
            f"🎯 Mục tiêu: {self.format_smart_number(target_val)}",
            f"Tiến độ: {progress:.1f}%",
            f"Còn thiếu: {self.format_smart_number(debt_to_target)}",
            "",
            f"⬆️ Tổng nạp: {self.format_smart_number(total_in)}",
            f"⬇️ Tổng rút: {self.format_smart_number(total_out)}",
            "━━━━━━━━━━━━━━━━━━━",
            f"🏦 Tiền mặt: {self.format_smart_number(cash_balance)}",
            f"📊 Cổ phiếu: {self.format_smart_number(stock_data['summary']['total_value'])}",
            f"🪙 Crypto: {self.format_smart_number(crypto_data['summary']['total_value'])}",
            "",
            "🏠 <i>Bấm các nút dưới để quản lý chi tiết.</i>"
        ]

        return "\n".join(lines)
