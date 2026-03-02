# backend/modules/dashboard.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_main_dashboard(self):
        data = self.db.get_dashboard_data()
        wallets = {w['id']: w for w in data['wallets']}
        
        # 1. Tiền mặt tại Ví Mẹ
        cash_mother = wallets['CASH']['balance']
        
        # 2. Vốn thực tế đang nằm tại các ví con (Cấp đi - Thu về)
        # Đây chính là con số "Vốn ròng" mà Sếp cấp cho mặt trận đó
        capital_stock = wallets['STOCK']['total_in'] - wallets['STOCK']['total_out']
        capital_crypto = wallets['CRYPTO']['total_in'] - wallets['CRYPTO']['total_out']
        
        # CHỐT LOGIC: Tổng tài sản = Tiền túi Mẹ + Vốn đã rót đi
        total_asset = cash_mother + capital_stock + capital_crypto
        
        # Tổng nạp từ ngoài vào hệ thống
        total_nap_goc = wallets['CASH']['total_in']
        total_rut_goc = wallets['CASH']['total_out']
        investment_goc = total_nap_goc - total_rut_goc
        
        # Lãi/Lỗ tổng ở trang chủ: Chỉ hiện số tiền ĐÃ THU HỒI về Ví Mẹ so với gốc nạp
        pl_total = total_asset - investment_goc
        pl_percent = (pl_total / investment_goc * 100) if investment_goc > 0 else 0

        lines = [
            "🏦 HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0",
            draw_line("thick"),
            f"💰 Tổng tài sản: {format_currency(total_asset)}",
            f"⬆️ Tổng nạp: {format_currency(total_nap_goc)}",
            f"⬇️ Tổng rút: {format_currency(total_rut_goc)}",
            f"📈 Lãi/Lỗ tổng: {format_currency(pl_total)} ({format_percent(pl_percent)})",
            "",
            "📦 PHÂN BỔ NGUỒN VỐN (BOOK VALUE):",
            f"• Vốn Đầu tư (Mẹ): {format_currency(cash_mother)} 🟢",
            f"• Ví Stock: {format_currency(capital_stock)}",
            f"• Ví Crypto: {format_currency(capital_crypto)}",
            "",
            "🛡️ SỨC KHỎE DANH MỤC:",
            f"• Trạng thái: An toàn",
            draw_line("thick")
        ]
        return "\n".join(lines)
