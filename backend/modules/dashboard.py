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
            
            # --- 1. TÍNH DÒNG VỐN GỐC (VỐN NẠP VÀO HỆ THỐNG) ---
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'IN'", (self.user_id,))
            t_in = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'CASH' AND type = 'OUT'", (self.user_id,))
            t_out = abs(cursor.fetchone()[0] or 0)
            
            # Vốn ròng CEO đã nạp vào túi tiền chính
            net_invested = t_in - t_out

            # --- 2. TÍNH TIỀN MẶT KHẢ DỤNG (CASH BALANCE) ---
            # Tiền mặt = (Vốn nạp ròng) - (Tiền đã chi mua Stock/Crypto) + (Tiền thu về khi bán)
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND type = 'BUY' AND asset_type != 'CASH'", (self.user_id,))
            total_spent = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND type = 'SELL' AND asset_type != 'CASH'", (self.user_id,))
            total_received = cursor.fetchone()[0] or 0

            cash_balance = net_invested - total_spent + total_received

            # --- 3. TÍNH GIÁ TRỊ THỊ TRƯỜNG CỦA TÀI SẢN (MARKET VALUE) ---
            # Lấy giá manual CEO đã cập nhật
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            # Tính giá trị Stock hiện tại theo giá thị trường
            cursor.execute('''
                SELECT ticker, SUM(CASE WHEN type='BUY' THEN qty ELSE -qty END) as current_qty
                FROM transactions 
                WHERE user_id = ? AND asset_type = 'STOCK'
                GROUP BY ticker
            ''', (self.user_id,))
            stocks = cursor.fetchall()
            
            stock_mkt_val = 0
            for s in stocks:
                qty = s['current_qty']
                if qty > 0:
                    # Lấy giá từ manual_prices, nếu không có lấy giá mua gần nhất làm gốc
                    price = price_map.get(s['ticker'])
                    if price is None:
                        cursor.execute("SELECT price FROM transactions WHERE ticker=? AND type='BUY' ORDER BY date DESC LIMIT 1", (s['ticker'],))
                        res = cursor.fetchone()
                        price = res[0] if res else 0
                    stock_mkt_val += qty * price * 1000

            # Tính giá trị Crypto quy đổi
            cursor.execute('''
                SELECT SUM(CASE WHEN type='BUY' THEN qty ELSE -qty END * price) 
                FROM transactions 
                WHERE user_id = ? AND asset_type = 'CRYPTO'
            ''', (self.user_id,))
            crypto_raw_val = cursor.fetchone()[0] or 0
            crypto_vnd = crypto_raw_val * EX_RATE

            # Giá trị tài sản khác
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id = ? AND asset_type = 'OTHER'", (self.user_id,))
            other_val = cursor.fetchone()[0] or 0

            # --- 4. TỔNG TÀI SẢN VÀ HIỆU SUẤT ---
            total_assets = cash_balance + stock_mkt_val + crypto_vnd + other_val
            
            # Lãi lỗ thực tế dựa trên sự tăng trưởng của Market Value so với Vốn nạp ròng
            profit = total_assets - net_invested
            roi = (profit / net_invested * 100) if net_invested > 0 else 0
            
            # Tiến độ mục tiêu
            progress = (total_assets / GOAL * 100)
            remain = max(0, GOAL - total_assets)

        # Giao diện HTML chuẩn CEO
        lines = [
            "💼 <b>TÀI SẢN CỦA BẠN</b>",
            f"💰 Tổng: <b>{self.format_currency(total_assets)}</b>",
            f"📈 Lãi: {self.format_currency(profit)} (🟢 {roi:+.1f}%)",
            "",
            f"📊 Stock: {self.format_currency(stock_mkt_val)}",
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
            f"📊 Cổ phiếu: {self.format_currency(stock_mkt_val)}",
            f"🪙 Crypto: {self.format_currency(crypto_vnd)}",
            "",
            "🏠 <i>Dữ liệu đã đồng bộ với giá thị trường.</i>"
        ]
        return "\n".join(lines)
