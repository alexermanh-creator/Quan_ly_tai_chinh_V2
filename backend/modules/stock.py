# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        """Render giao diện chi tiết Danh mục Chứng khoán"""
        data = self.db.get_dashboard_data()
        stock_wallet = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        total_val = sum(h['quantity'] * h['average_price'] for h in holdings)
        # Tạm thời HT = Vốn (Sẽ update module cập nhật giá sau)
        total_von = total_val 
        
        # Tính toán Mã tốt nhất / Tỉ trọng
        max_weight_symbol = "--"
        max_weight_pct = 0
        if total_val > 0:
            best_h = max(holdings, key=lambda x: x['quantity'] * x['average_price'])
            max_weight_symbol = best_h['symbol']
            max_weight_pct = (best_h['quantity'] * best_h['average_price'] / total_val) * 100

        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(total_val)}",
            f"💵 Tổng vốn: {format_currency(total_von)}",
            f"💸 Sức mua: {format_currency(stock_wallet['balance'] if stock_wallet else 0)}",
            f"📈 Lãi/Lỗ: 0đ (+0.0%)",
            f"⬆️ Tổng nạp ví: {format_currency(stock_wallet['total_in'] if stock_wallet else 0)}",
            f"⬇️ Tổng rút ví: {format_currency(stock_wallet['total_out'] if stock_wallet else 0)}",
            f"🏆 Mã tốt nhất: -- (+0.0%)",
            f"📉 Mã kém nhất: -- (+0.0%)",
            f"📊 Tỉ trọng lớn nhất: {max_weight_symbol} ({max_weight_pct:.1f}%)",
            draw_line("thin")
        ]

        for h in holdings:
            val = h['quantity'] * h['average_price']
            lines.append(f"💎 {h['symbol']}")
            lines.append(f"• SL: {h['quantity']:,} | Vốn TB: {h['average_price']/1000:,.1f}k")
            lines.append(f"• Hiện tại: {h['average_price']/1000:,.1f}k | GT: {format_currency(val)}")
            lines.append(f"• Lãi: 0đ (+0.0%)")
            lines.append(draw_line("thin"))
            
        lines.append(draw_line("thick"))
        return "\n".join(lines)
