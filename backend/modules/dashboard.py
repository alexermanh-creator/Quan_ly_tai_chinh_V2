# backend/modules/dashboard.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_main_dashboard(self):
        data = self.db.get_dashboard_data()
        wallets = {w['id']: w for w in data['wallets']}
        
        # CHỐT: Tổng nạp/rút chỉ lấy từ Ví Mẹ (Gốc)
        total_nap = wallets['CASH']['total_in']
        total_rut = wallets['CASH']['total_out']
        
        # Tổng tài sản = Tiền mặt tất cả các ví + Giá trị hiện giá của holdings
        cash_all_wallets = sum(w['balance'] for w in wallets.values())
        current_holding_value = sum(h['quantity'] * h['average_price'] for h in data['holdings'])
        total_asset = cash_all_wallets + current_holding_value

        # Lãi/Lỗ tổng = Tổng tài sản hiện tại - (Vốn ròng còn lại trong hệ thống)
        # Vốn ròng = Tổng nạp - Tổng rút
        net_investment = total_nap - total_rut
        pl_total = total_asset - net_investment if net_investment != 0 else total_asset
        pl_percent = (pl_total / net_investment * 100) if net_investment > 0 else 0

        lines = [
            "🏦 HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0",
            draw_line("thick"),
            f"💰 Tổng tài sản: {format_currency(total_asset)}",
            f"⬆️ Tổng nạp: {format_currency(total_nap)}",
            f"⬇️ Tổng rút: {format_currency(total_rut)}",
            f"📈 Lãi/Lỗ tổng: {format_currency(pl_total)} ({format_percent(pl_percent)})",
            "",
            "📦 PHÂN BỔ NGUỒN VỐN:",
            f"• Vốn Đầu tư (Mẹ): {format_currency(wallets['CASH']['balance'])} 🟢",
            f"• Ví Stock: {format_currency(wallets['STOCK']['balance'])}",
            f"• Ví Crypto: {format_currency(wallets['CRYPTO']['balance'])}",
            "",
            "🛡️ SỨC KHỎE DANH MỤC:",
            f"• Tiền mặt: {format_percent(cash_all_wallets/total_asset*100 if total_asset > 0 else 0)}",
            "• Trạng thái: An toàn",
            draw_line("thick")
        ]
        return "\n".join(lines)

    def get_stock_dashboard(self):
        data = self.db.get_dashboard_data()
        stock_wallet = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        # Giá trị hiện tại của danh mục Stock
        current_val = sum(h['quantity'] * h['average_price'] for h in holdings)
        # Giả định tạm thời: Lãi lỗ đang treo = 0 (vì chưa có module cập nhật giá realtime)
        # Sau này: floating_pl = (Giá HT - Giá Vốn) * Số lượng
        
        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(current_val)}",
            f"💸 Sức mua: {format_currency(stock_wallet['balance'] if stock_wallet else 0)}",
            draw_line("thin")
        ]

        for h in holdings:
            val = h['quantity'] * h['average_price']
            lines.append(f"💎 {h['symbol']}")
            lines.append(f"• SL: {h['quantity']:,} | Giá vốn: {h['average_price']/1000:,.1f}k")
            lines.append(f"• Thành tiền: {format_currency(val)}")
            lines.append(draw_line("thin"))
            
        return "\n".join(lines)
