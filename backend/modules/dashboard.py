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
            
            # --- 1. TÍNH DÒNG VỐN (TIỀN NẠP VÀO / RÚT RA) ---
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'OUT'", (self.user_id,))
            t_out = abs(cursor.fetchone()[0] or 0)
            
            # Vốn ròng đã nạp
            net_invested = t_in - t_out

            # --- 2. TÍNH GIÁ TRỊ TÀI SẢN ĐANG NẮM GIỮ ---
            # Chỉ lấy các bản ghi có asset_type là STOCK hoặc CRYPTO
            cursor.execute('''
                SELECT asset_type, SUM(total_value) 
                FROM transactions 
                WHERE user_id = ? AND asset_type IN ('STOCK', 'CRYPTO', 'OTHER')
                GROUP BY asset_type
            ''', (self.user_id,))
            
            data_map = {row[0]: (row[1] or 0) for row in cursor.fetchall()}
            
            stock_val = data_map.get('STOCK', 0)
            crypto_vnd = data_map.get('CRYPTO', 0) * EX_RATE
            other_val = data_map.get('OTHER', 0)

            # --- 3. TÍNH TIỀN MẶT KHẢ DỤNG (CASH BALANCE) ---
            # Tiền mặt = (Vốn nạp ròng) - (Tổng tiền đã chi mua STOCK/CRYPTO) + (Tổng tiền bán được)
            # Trong database của bạn, lệnh MUA có type='BUY', lệnh BÁN có type='SELL'
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND type = 'BUY' AND asset_type != 'CASH'", (self.user_id,))
            total_spent = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND type = 'SELL' AND asset_type != 'CASH'", (self.user_id,))
            total_received = cursor.fetchone()[0] or 0

            # Công thức trừ tiền mặt chuẩn
            cash_balance = net_invested - total_spent + total_received

            # --- 4. TỔNG TÀI SẢN VÀ LÃI LỖ ---
            total_assets = cash_balance + stock_val + crypto_vnd + other_val
            
            profit = total_assets - net_invested
            roi = (profit / net_invested * 100) if net_invested > 0 else 0
            
            # Tiến độ mục tiêu
            progress = (total_assets / GOAL * 100)
            remain = max(0, GOAL - total_assets)

        # Giao diện HTML chuẩn CTO
        lines = [
            "💼 <b>TÀI SẢN CỦA BẠN</b>",
            f"💰 Tổng: <b>{self.format_currency(total_assets)}</b>",
            f"📈 Lãi: {self.format_currency(profit)} (🟢 {roi:+.1f}%)",
            "",
            f"📊 Stock: {self.format_currency(stock_val)}",
            f"🪙 Crypto: {self.format_currency(crypto_vnd)}",
            f"🥇 Khác: {self.format_currency(other_val)}",
            "",
            f"🎯 Mục tiêu: {self.format_currency(GOAL)}",
            f"🏁 Tiến độ: {progress:.1f}%",
            f"Còn thiếu: {self.format_currency(remain)}",
            "",
            f"⬆️ Tổng nạp: {self.format_currency(t_in)}",
            f"⬇️ Tổng rút: {self.format_currency(t_out)}",
            "━━━━━━━━━━━━━━━━━━━",
            f"🏦 Tiền mặt: {self.format_currency(cash_balance)}",
            f"📊 Cổ phiếu: {self.format_currency(stock_val)}",
            f"🪙 Crypto: {self.format_currency(crypto_vnd)}",
            "",
            "🏠 <i>Bấm các nút dưới để quản lý chi tiết.</i>"
        ]
        return "\n".join(lines)
