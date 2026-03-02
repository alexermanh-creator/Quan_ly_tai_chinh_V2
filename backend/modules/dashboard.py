# backend/modules/dashboard.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_main_dashboard(self):
        data = self.db.get_dashboard_data()
        wallets = {w['id']: w for w in data['wallets']}
        
        # 1. Thông số từ Ví Mẹ
        cash_mother = wallets['CASH']['balance']
        total_nap_goc = wallets['CASH']['total_in']
        total_rut_goc = wallets['CASH']['total_out']
        investment_net = total_nap_goc - total_rut_goc

        # 2. Tính toán cho các Ví Con
        summary_con = []
        real_nav_system = cash_mother # Để tính % lãi lỗ thực tế toàn hệ thống
        display_asset_home = cash_mother # Để hiển thị Tổng tài sản "An toàn" theo ý Sếp

        for v_id in ['STOCK', 'CRYPTO']:
            w = wallets[v_id]
            # Vốn ròng đã cấp cho ví này (Cấp đi - Thu về)
            capital_allocated = w['total_in'] - w['total_out']
            
            # Giá trị thực tế hiện tại (Tiền mặt + Cổ/Crypto)
            h_val = sum(h['quantity'] * h['average_price'] for h in data['holdings'] if h['wallet_id'] == v_id)
            current_nav_con = w['balance'] + h_val
            
            # CÔNG THỨC "AN TOÀN": Home chỉ hiện số Vốn đã cấp (Book Value)
            # Nếu ví con đang lãi, chỉ hiện số Vốn. Nếu ví con lỗ, hiện số NAV thực (để cảnh báo rủi ro).
            display_val = min(current_nav_con, capital_allocated)
            display_asset_home += display_val
            
            # Cộng dồn để tính % lãi lỗ thực tế (Gồm cả lãi treo)
            real_nav_system += current_nav_con
            summary_con.append(f"• Ví {v_id.capitalize()}: {format_currency(capital_allocated)}")

        # 3. Tính Lãi/Lỗ tổng (Hiển thị hiệu suất thực tế nhưng không cộng vào Asset)
        pl_real_amt = real_nav_system - investment_net if investment_net > 0 else 0
        pl_real_pct = (pl_real_amt / investment_net * 100) if investment_net > 0 else 0

        lines = [
            "🏦 HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0",
            draw_line("thick"),
            f"💰 Tổng tài sản: {format_currency(display_asset_home)}",
            f"⬆️ Tổng nạp: {format_currency(total_nap_goc)}",
            f"⬇️ Tổng rút: {format_currency(total_rut_goc)}",
            f"📈 Lãi/Lỗ tổng: {format_currency(pl_real_amt)} ({format_percent(pl_real_pct)})",
            "",
            "📦 PHÂN BỔ VỐN GỐC (BOOK VALUE):",
            f"• Vốn Đầu tư (Mẹ): {format_currency(cash_mother)} 🟢"
        ]
        lines.extend(summary_con)
        lines.extend([
            "",
            "🛡️ SỨC KHỎE DANH MỤC:",
            f"• Trạng thái: {'Ổn định' if pl_real_pct >= 0 else 'Cảnh báo'}",
            draw_line("thick")
        ])
        return "\n".join(lines)
