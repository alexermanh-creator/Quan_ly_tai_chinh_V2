# backend/modules/dashboard.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_main_dashboard(self):
        """Render Layout Dashboard Tổng (Vĩ mô)"""
        data = self.db.get_dashboard_data()
        wallets = {w['id']: w for w in data['wallets']}
        
        # Tổng tài sản = Tiền mặt các ví + Giá trị holdings hiện có
        cash_all = sum(w['balance'] for w in wallets.values())
        holding_val = sum(h['quantity'] * h['average_price'] for h in data['holdings'])
        total_asset = cash_all + holding_val
        
        # Vốn ròng = Nạp - Rút (Chỉ tính tại Ví Mẹ)
        net_investment = wallets['CASH']['total_in'] - wallets['CASH']['total_out']
        
        # Lãi lỗ tổng
        pl_total = total_asset - net_investment if net_investment != 0 else 0
        pl_percent = (pl_total / net_investment * 100) if net_investment > 0 else 0

        lines = [
            "🏦 HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0",
            draw_line("thick"),
            f"💰 Tổng tài sản: {format_currency(total_asset)}",
            f"⬆️ Tổng nạp: {format_currency(wallets['CASH']['total_in'])}",
            f"⬇️ Tổng rút: {format_currency(wallets['CASH']['total_out'])}",
            f"📈 Lãi/Lỗ tổng: {format_currency(pl_total)} ({format_percent(pl_percent)})",
            "",
            "📦 PHÂN BỔ NGUỒN VỐN:",
            f"• Vốn Đầu tư (Mẹ): {format_currency(wallets['CASH']['balance'])} 🟢",
            f"• Ví Stock: {format_currency(wallets['STOCK']['balance'])}",
            f"• Ví Crypto: {format_currency(wallets['CRYPTO']['balance'])}",
            "",
            "🛡️ SỨC KHỎE DANH MỤC:",
            f"• Tiền mặt: {format_percent(cash_all/total_asset*100 if total_asset > 0 else 0)}",
            "• Trạng thái: An toàn",
            draw_line("thick")
        ]
        return "\n".join(lines)
