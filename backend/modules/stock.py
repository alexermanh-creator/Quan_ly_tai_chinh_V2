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
        
        suc_mua = w['balance'] if w else 0
        market_val = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
        nav = suc_mua + market_val
        
        von_rong = w['total_in'] - w['total_out'] if w else 0
        pl = nav - von_rong
        roi = (pl / von_rong * 100) if von_rong > 0 else 0

        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị (NAV): {format_currency(nav)}",
            f"💵 Tổng vốn: {format_currency(von_rong)}",
            f"📈 Lãi/Lỗ: {format_currency(pl)} ({format_percent(roi)})",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            draw_line("thin")
        ]
        if not holdings: lines.append("❌ Danh mục hiện đang trống.")
        for h in holdings:
            p_now = h['current_price'] or h['average_price']
            lines.append(f"💎 {h['symbol']} | SL: {h['quantity']:,.0f} | Giá: {p_now/1000:,.1f}k")
        lines.append(draw_line("thick"))
        return "\n".join(lines)

    def get_group_report(self):
        data = self.db.get_dashboard_data()
        w = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        suc_mua = w['balance'] if w else 0
        market_val = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
        nav = suc_mua + market_val
        
        von_rong = w['total_in'] - w['total_out'] if w else 0
        realized_pl = data['realized'].get('STOCK', 0)
        floating_pl = market_val - sum(h['quantity'] * h['average_price'] for h in holdings)
        
        lines = [
            "📑 BÁO CÁO TÀI CHÍNH: CHỨNG KHOÁN",
            draw_line("thick"),
            f"• Tổng tài sản: {format_currency(nav)}",
            f"• Sức mua: {format_currency(suc_mua)}",
            f"• Vốn ròng: {format_currency(von_rong)}",
            f"• Lãi chốt: {format_currency(realized_pl)}",
            f"• Lãi tạm tính: {format_currency(floating_pl)}",
            draw_line("thin"),
            "📊 CHI TIẾT & TỈ TRỌNG:"
        ]
        for h in holdings:
            p_now = h['current_price'] or h['average_price']
            val = h['quantity'] * p_now
            weight = (val / nav * 100) if nav > 0 else 0
            lines.append(f"💎 {h['symbol']} | {weight:.1f}% | ROI: {((p_now/h['average_price'])-1)*100:.1f}%")
        return "\n".join(lines)
