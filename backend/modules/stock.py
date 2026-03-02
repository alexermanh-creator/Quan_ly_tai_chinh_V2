from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        data = self.db.get_dashboard_data()
        w = next((item for item in data['wallets'] if item['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        suc_mua = w['balance'] if w else 0
        # Giá trị theo thị trường
        total_market_val = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
        nav_stock = suc_mua + total_market_val
        
        # Vốn ròng rót vào ví
        capital_invested = w['total_in'] - w['total_out'] if w else 0
        
        # ROI Ví Stock
        pl_stock = nav_stock - capital_invested
        roi_stock = (pl_stock / capital_invested * 100) if capital_invested > 0 else 0

        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(nav_stock)}",
            f"💵 Tổng vốn: {format_currency(capital_invested)}",
            f"📈 Lãi/Lỗ: {format_currency(pl_stock)} ({format_percent(roi_stock)})",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            draw_line("thin")
        ]

        for h in holdings:
            price_buy = h['average_price']
            price_now = h['current_price'] or price_buy
            item_pl = (price_now - price_buy) * h['quantity']
            item_roi = ((price_now / price_buy) - 1) * 100
            
            lines.append(f"💎 {h['symbol']}")
            lines.append(f"• SL: {h['quantity']:,.0f} | Vốn: {price_buy/1000:,.1f}k")
            lines.append(f"• Hiện tại: {price_now/1000:,.1f}k | GT: {format_currency(h['quantity'] * price_now)}")
            lines.append(f"• Lãi: {format_currency(item_pl)} ({format_percent(item_roi)})")
            lines.append(draw_line("thin"))
            
        return "\n".join(lines)
