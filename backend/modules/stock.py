# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        """Render giao diện chi tiết Danh mục Chứng khoán chuẩn Logic: NAV = Tiền + Cổ"""
        data = self.db.get_dashboard_data()
        stock_wallet = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        # 1. Định nghĩa các thông số cơ bản
        suc_mua = stock_wallet['balance'] if stock_wallet else 0
        total_holdings_val = sum(h['quantity'] * h['average_price'] for h in holdings)
        
        # CHỐT: Tổng giá trị (NAV) = Tiền mặt + Giá trị cổ phiếu
        nav_stock = suc_mua + total_holdings_val
        
        # CHỐT: Tổng vốn = Tiền nạp vào ví - Tiền rút ra khỏi ví
        total_nap_vi = stock_wallet['total_in'] if stock_wallet else 0
        total_rut_vi = stock_wallet['total_out'] if stock_wallet else 0
        von_rong_vi = total_nap_vi - total_rut_vi
        
        # 2. Tính toán Hiệu quả (Lãi/Lỗ)
        # Lãi/Lỗ = NAV hiện tại - Vốn ròng
        total_pl = nav_stock - von_rong_vi if von_rong_vi != 0 else 0
        pl_percent = (total_pl / von_rong_vi * 100) if von_rong_vi > 0 else 0
        
        # 3. Phân tích mã (Tỉ trọng)
        max_weight_symbol, max_weight_pct = "--", 0
        if total_holdings_val > 0:
            best_h = max(holdings, key=lambda x: x['quantity'] * x['average_price'])
            max_weight_symbol = best_h['symbol']
            max_weight_pct = (best_h['quantity'] * best_h['average_price'] / nav_stock) * 100

        # 4. Render Giao diện
        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(nav_stock)}",
            f"💵 Tổng vốn: {format_currency(von_rong_vi)}",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            f"📈 Lãi/Lỗ: {format_currency(total_pl)} ({format_percent(pl_percent)})",
            f"⬆️ Tổng nạp ví: {format_currency(total_nap_vi)}",
            f"⬇️ Tổng rút ví: {format_currency(total_rut_vi)}",
            f"🏆 Mã tốt nhất: --",
            f"📉 Mã kém nhất: --",
            f"📊 Tỉ trọng lớn nhất: {max_weight_symbol} ({max_weight_pct:.1f}%)",
            draw_line("thin")
        ]

        if not holdings:
            lines.append("❌ Danh mục hiện đang trống.")
        else:
            for h in holdings:
                gt_ma = h['quantity'] * h['average_price']
                lines.append(f"💎 {h['symbol']}")
                lines.append(f"• SL: {h['quantity']:,.0f} | Vốn TB: {h['average_price']/1000:,.1f}k")
                lines.append(f"• Hiện tại: {h['average_price']/1000:,.1f}k | GT: {format_currency(gt_ma)}")
                lines.append(f"• Lãi: 0 đ (+0.0%)")
                lines.append(draw_line("thin"))
            
        lines.append(draw_line("thick"))
        return "\n".join(lines)
