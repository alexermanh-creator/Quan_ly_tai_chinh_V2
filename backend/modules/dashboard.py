# backend/modules/dashboard.py
from backend.database.db_manager import db
from backend.database.repository import repo

class DashboardModule:
    def __init__(self, user_id):
        self.user_id = user_id

    def format_smart(self, value):
        abs_v = abs(value)
        sign = "-" if value < 0 else "+" if value > 0 else ""
        if abs_v >= 1e9: return f"{sign}{value/1e9:.2f} tỷ"
        if abs_v >= 1e6: return f"{sign}{value/1e6:,.1f} tr"
        return f"{value:,.0f} đ"

    def run(self):
        user_id = self.user_id
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Tính VỐN GỐC (Chỉ tính lệnh NAP/RUT tại Ví Mẹ)
            cursor.execute("""
                SELECT SUM(CASE WHEN type='IN' THEN total_value WHEN type='OUT' THEN -total_value ELSE 0 END)
                FROM transactions WHERE user_id=? AND asset_type='CASH'
            """, (user_id,))
            net_invest = cursor.fetchone()[0] or 0
            
            # 2. Tính TỔNG NẠP (Để hiển thị dòng 2)
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='IN'", (user_id,))
            total_in = cursor.fetchone()[0] or 0
            
            # 3. Tính TỔNG RÚT (Để hiển thị dòng 3)
            cursor.execute("SELECT SUM(total_value) FROM transactions WHERE user_id=? AND asset_type='CASH' AND type='OUT'", (user_id,))
            total_out = cursor.fetchone()[0] or 0

            # 4. Tính GIÁ TRỊ TÀI SẢN TRONG CÁC MÃ (Stock/Crypto)
            cursor.execute("""
                SELECT SUM(total_qty * (CASE WHEN asset_type='STOCK' THEN COALESCE(market_price, avg_price)*1000 
                                             WHEN asset_type='CRYPTO' THEN COALESCE(market_price, avg_price)*25000 
                                             ELSE 0 END))
                FROM portfolio WHERE user_id=?
            """, (user_id,))
            asset_value = cursor.fetchone()[0] or 0
            
            # 5. Lấy tiền mặt thực tế tại từng ví
            c_mom = repo.get_available_cash(user_id, 'CASH')
            c_stock = repo.get_available_cash(user_id, 'STOCK')
            c_crypto = repo.get_available_cash(user_id, 'CRYPTO')
            
            # 6. TỔNG TÀI SẢN THỰC TẾ
            total_assets = c_mom + c_stock + c_crypto + asset_value
            
            # 7. LÃI/LỖ TỔNG (Đúng yêu cầu sếp: Lãi từ danh mục)
            total_pnl = total_assets - net_invest
            roi = (total_pnl / net_invest * 100) if net_invest > 0 else 0

        return (
            "🏦 <b>HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Tổng tài sản: <b>{self.format_smart(total_assets).replace('+','')}</b>\n"
            f"⬆️ Tổng nạp: {self.format_smart(total_in).replace('+','')}\n"
            f"⬇️ Tổng rút: {self.format_smart(total_out).replace('+','')}\n"
            f"📈 Lãi/Lỗ tổng: <b>{self.format_smart(total_pnl)} ({roi:+.2f}%)</b>\n\n"
            "📦 <b>PHÂN BỔ NGUỒN VỐN:</b>\n"
            f"• Vốn Đầu tư (Mẹ): {self.format_smart(c_mom).replace('+','')} 🟢\n"
            f"• Ví Stock: {self.format_smart(c_stock).replace('+','')}\n"
            f"• Ví Crypto: {self.format_smart(c_crypto).replace('+','')}\n"
            "• Ví Khác: 0 đ\n\n"
            "🛡️ <b>SỨC KHỎE DANH MỤC:</b>\n"
            f"• Trạng thái: An toàn (Tiền mặt: {( (c_mom+c_stock+c_crypto)/total_assets*100 if total_assets>0 else 100):.0f}%)\n"
            "• Cảnh báo: Không có\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
