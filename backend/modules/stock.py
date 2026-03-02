# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        data = self.db.get_dashboard_data()
        w = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        # NAV = Tiền mặt + Giá trị cổ phiếu
        suc_mua = w['balance'] if w else 0
        gt_holdings = sum(h['quantity'] * h['average_price'] for h in holdings)
        nav_stock = suc_mua + gt_holdings
        
        # Vốn ròng tại ví Stock
        total_in = w['total_in'] if w else 0
        total_out = w['total_out'] if w else 0
        von_rong = total_in - total_out
        
        # Lãi lỗ của riêng mặt trận Stock
        pl_amt = nav_stock - von_rong if von_rong != 0 else 0
        pl_pct = (pl_amt / von_rong * 100) if von_rong > 0 else 0

        # Phân tích tỉ trọng
        max_sym, max_pct = "--", 0
        if gt_holdings > 0:
            best = max(holdings, key=lambda x: x['quantity'] * x['average_price'])
            max_sym = best['symbol']
            max_pct = (best['quantity'] * best['average_price'] / nav_stock) * 100

        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(nav_stock)}",
            f"💵 Tổng vốn: {format_currency(von_rong)}",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            f"📈 Lãi/Lỗ: {format_currency(pl_amt)} ({format_percent(pl_pct)})",
            f"⬆️ Tổng nạp ví: {format_currency(total_in)}",
            f"⬇️ Tổng rút ví: {format_currency(total_out)}",
            f"🏆 Mã tốt nhất: --",
            f"📉 Mã kém nhất: --",
            f"📊 Tỉ trọng lớn nhất: {max_sym} ({max_pct:.1f}%)",
            draw_line("thin")
        ]

        for h in holdings:
            gt = h['quantity'] * h['average_price']
            lines.append(f"💎 {h['symbol']}")
            lines.append(f"• SL: {h['quantity']:,.0f} | Vốn TB: {h['average_price']/1000:,.1f}k")
            lines.append(f"• Hiện tại: {h['average_price']/1000:,.1f}k | GT: {format_currency(gt)}")
            lines.append(f"• Lãi: 0 đ (+0.0%)")
            lines.append(draw_line("thin"))
            
        lines.append(draw_line("thick"))
        return "\n".join(lines)
