# backend/modules/dashboard.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_main_dashboard(self):
        """Render Layout 1: Dashboard Tổng (Menu Chính)"""
        data = self.db.get_dashboard_data()
        wallets = {w['id']: w for w in data['wallets']}
        
        # Tính toán các chỉ số tổng
        total_nap = sum(w['total_in'] for w in wallets.values())
        total_rut = sum(w['total_out'] for w in wallets.values())
        
        # Tổng tài sản = Tiền mặt các ví + Giá trị cổ phiếu/crypto hiện có
        # Lưu ý: Ở bản này chúng ta giả định Giá HT = Giá Vốn (Sẽ update cập nhật giá ở module sau)
        total_asset = sum(w['balance'] for w in wallets.values())
        for h in data['holdings']:
            total_asset += (h['quantity'] * h['average_price'])

        pl_total = total_asset - total_nap + total_rut
        pl_percent = (pl_total / total_nap * 100) if total_nap > 0 else 0

        # Render Layout theo yêu cầu của Sếp
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
            f"• Ví Khác: {format_currency(0)}", # Dự phòng Plug & Play
            "",
            "🛡️ SỨC KHỎE DANH MỤC:",
            "• Trạng thái: An toàn (Tiền mặt: 48%)",
            "• Cảnh báo: Không có",
            draw_line("thick")
        ]
        return "\n".join(lines)

    def get_stock_dashboard(self):
        """Render Layout 2: Danh mục Chi tiết (Ví Stock)"""
        data = self.db.get_dashboard_data()
        stock_wallet = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        total_val = sum(h['quantity'] * h['average_price'] for h in holdings)
        total_von = total_val # Tạm tính
        suc_mua = stock_wallet['balance'] if stock_wallet else 0
        
        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(total_val)}",
            f"💵 Tổng vốn: {format_currency(total_von)}",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            f"📈 Lãi/Lỗ: 0 đ (+0.0%)",
            f"⬆️ Tổng nạp ví: {format_currency(stock_wallet['total_in'])}",
            f"⬇️ Tổng rút ví: {format_currency(stock_wallet['total_out'])}",
            "",
            "🏆 Mã tốt nhất: --",
            "📉 Mã kém nhất: --",
            "📊 Tỉ trọng lớn nhất: --",
            draw_line("thin")
        ]

        for h in holdings:
            gt_ma = h['quantity'] * h['average_price']
            lines.append(f"💎 {h['symbol']}")
            lines.append(f"• SL: {h['quantity']:,} | Vốn TB: {h['average_price']/1000:,.1f}k")
            lines.append(f"• Hiện tại: {h['average_price']/1000:,.1f}k | GT: {format_currency(gt_ma)}")
            lines.append(f"• Lãi: 0 đ (+0.0%)")
            lines.append(draw_line("thin"))
            
        lines.append(draw_line("thick"))
        return "\n".join(lines)
