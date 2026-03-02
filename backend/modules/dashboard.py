# backend/modules/dashboard.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_main_dashboard(self):
        data = self.db.get_dashboard_data()
        wallets = {w['id']: w for w in data['wallets']}
        
        # 1. Gốc nạp rút từ hệ thống
        investment_net = wallets['CASH']['total_in'] - wallets['CASH']['total_out']
        
        # 2. Tổng tài sản hiển thị (Tiền Mẹ + Vốn gốc đang ở các ví con)
        # Vì total_out của ví con giờ chỉ tăng khi rút vượt lãi, nên Book Value sẽ chuẩn
        asset_home = wallets['CASH']['balance']
        for v_id in ['STOCK', 'CRYPTO']:
            asset_home += (wallets[v_id]['total_in'] - wallets[v_id]['total_out'])

        # 3. Lãi lỗ thực tế (Gồm cả lãi treo chưa thu hồi)
        current_nav_all = sum(w['balance'] for w in wallets.values())
        current_nav_all += sum(h['quantity'] * h['average_price'] for h in data['holdings'])
        
        pl_real_amt = current_nav_all - investment_net if investment_net > 0 else 0
        pl_real_pct = (pl_real_amt / investment_net * 100) if investment_net > 0 else 0

        lines = [
            "🏦 HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0",
            draw_line("thick"),
            f"💰 Tổng tài sản: {format_currency(asset_home)}",
            f"⬆️ Tổng nạp: {format_currency(wallets['CASH']['total_in'])}",
            f"⬇️ Tổng rút: {format_currency(wallets['CASH']['total_out'])}",
            f"📈 Lãi/Lỗ tổng: {format_currency(pl_real_amt)} ({format_percent(pl_real_pct)})",
            "",
            "📦 PHÂN BỔ VỐN GỐC (BOOK VALUE):",
            f"• Vốn Đầu tư (Mẹ): {format_currency(wallets['CASH']['balance'])} 🟢",
            f"• Ví Stock: {format_currency(wallets['STOCK']['total_in'] - wallets['STOCK']['total_out'])}",
            f"• Ví Crypto: {format_currency(wallets['CRYPTO']['total_in'] - wallets['CRYPTO']['total_out'])}",
            "",
            "🛡️ SỨC KHỎE DANH MỤC:",
            f"• Trạng thái: Ổn định",
            draw_line("thick")
        ]
        return "\n".join(lines)
