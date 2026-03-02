from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_main_dashboard(self):
        data = self.db.get_dashboard_data()
        wallets = {w['id']: w for w in data['wallets']}
        
        cash_mother = wallets['CASH']['balance']
        total_nap = wallets['CASH']['total_in']
        total_rut = wallets['CASH']['total_out']
        net_invested = total_nap - total_rut

        # Tính NAV thực tế (Giá thị trường)
        total_market_val = sum(w['balance'] for w in wallets.values())
        total_market_val += sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in data['holdings'])

        # Lãi/Lỗ tổng dựa trên NAV thực tế
        pl_total = total_market_val - net_invested if net_invested > 0 else 0
        pl_percent = (pl_total / net_invested * 100) if net_invested > 0 else 0

        # Phân bổ vốn gốc hiển thị (Book Value)
        capital_stock = wallets['STOCK']['total_in'] - wallets['STOCK']['total_out']
        capital_crypto = wallets['CRYPTO']['total_in'] - wallets['CRYPTO']['total_out']

        lines = [
            "🏦 HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0",
            draw_line("thick"),
            f"💰 Tổng tài sản: {format_currency(total_market_val)}",
            f"⬆️ Tổng nạp: {format_currency(total_nap)}",
            f"⬇️ Tổng rút: {format_currency(total_rut)}",
            f"📈 Lãi/Lỗ tổng: {format_currency(pl_total)} ({format_percent(pl_percent)})",
            "",
            "📦 PHÂN BỔ VỐN GỐC (BOOK VALUE):",
            f"• Ví Mẹ (CASH): {format_currency(cash_mother)} 🟢",
            f"• Ví Stock: {format_currency(capital_stock)}",
            f"• Ví Crypto: {format_currency(capital_crypto)}",
            draw_line("thick")
        ]
        return "\n".join(lines)
