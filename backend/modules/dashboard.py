# backend/modules/dashboard.py
from backend.interface import BaseModule
from backend.database.db_manager import db

class DashboardModule(BaseModule):
    def format_currency(self, value):
        """Định dạng tiền tệ chuẩn: tỷ, triệu hoặc đồng"""
        abs_val = abs(value)
        sign = "-" if value < 0 else ""
        if abs_val >= 10**9: return f"{sign}{value / 10**9:,.2f} tỷ"
        if abs_val >= 10**6: return f"{sign}{value / 10**6:,.1f} triệu"
        return f"{sign}{value:,.0f}đ"

    def run(self):
        EX_RATE = 26300 # Tỷ giá USDT/VND
        GOAL = 500_000_000 # Mục tiêu 500tr

        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Lấy tổng giá trị theo từng loại tài sản
            cursor.execute('''
                SELECT asset_type, SUM(total_value) 
                FROM transactions WHERE user_id = ? 
                GROUP BY asset_type
            ''', (self.user_id,))
            data_map = {row[0]: (row[1] or 0) for row in cursor.fetchall()}

            # Phân loại tài sản
            cash = data_map.get('CASH', 0)
            stock = data_map.get('STOCK', 0)
            crypto_vnd = data_map.get('CRYPTO', 0) * EX_RATE
            other = data_map.get('OTHER', 0)
            
            total_assets = cash + stock + crypto_vnd + other

            # Tính toán Nạp/Rút để tính Lãi thực tế
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND total_value > 0", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND total_value < 0", (self.user_id,))
            t_out = abs(cursor.fetchone()[0] or 0)

            net_invested = t_in - t_out
            profit = total_assets - net_invested
            roi = (profit / net_invested * 100) if net_invested > 0 else 0
            
            # Tính tiến độ mục tiêu
            progress = (total_assets / GOAL * 100)
            remain = max(0, GOAL - total_assets)

        # Giao diện HTML chuẩn CTO
        lines = [
            "💼 <b>TÀI SẢN CỦA BẠN</b>",
            f"💰 Tổng: <b>{self.format_currency(total_assets)}</b>",
            f"📈 Lãi: {self.format_currency(profit)} (🟢 {roi:+.1f}%)",
            "",
            f"📊 Stock: {self.format_currency(stock)}",
            f"🪙 Crypto: {self.format_currency(crypto_vnd)}",
            f"🥇 Khác: {self.format_currency(other)}",
            "",
            f"🎯 Mục tiêu: {self.format_currency(GOAL)}",
            f"🏁 Tiến độ: {progress:.1f}%",
            f"Còn thiếu: {self.format_currency(remain)}",
            "",
            f"⬆️ Tổng nạp: {self.format_currency(t_in)}",
            f"⬇️ Tổng rút: {self.format_currency(t_out)}",
            "━━━━━━━━━━━━━━━━━━━",
            f"🏦 Tiền mặt: {self.format_currency(cash)}",
            f"📊 Cổ phiếu: {self.format_currency(stock)}",
            f"🪙 Crypto: {self.format_currency(crypto_vnd)}",
            "",
            "🏠 <i>Bấm các nút dưới để quản lý chi tiết.</i>"
        ]
        return "\n".join(lines)
