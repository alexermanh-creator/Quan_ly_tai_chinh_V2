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
        
        # 1. Tính toán giá trị thị trường
        suc_mua = w['balance'] if w else 0
        gt_thi_truong = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
        nav_stock = suc_mua + gt_thi_truong
        
        total_in = w['total_in'] if w else 0
        total_out = w['total_out'] if w else 0
        von_rong = total_in - total_out
        
        pl_amt = nav_stock - von_rong if von_rong != 0 else 0
        pl_pct = (pl_amt / von_rong * 100) if von_rong > 0 else 0

        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị (NAV): {format_currency(nav_stock)}",
            f"💵 Tổng vốn: {format_currency(von_rong)}",
            f"📈 Lãi/Lỗ: {format_currency(pl_amt)} ({format_percent(pl_pct)})",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            draw_line("thin")
        ]

        if not holdings:
            lines.append("❌ Danh mục hiện đang trống.")
        else:
            for h in holdings:
                price_buy = h['average_price']
                price_now = h['current_price'] or price_buy
                item_roi = ((price_now / price_buy) - 1) * 100
                lines.append(f"💎 {h['symbol']} ({format_percent(item_roi)})")
                lines.append(f"• SL: {h['quantity']:,.0f} | Giá: {price_now/1000:,.1f}k")
                lines.append(draw_line("thin"))
            
        lines.append(draw_line("thick"))
        return "\n".join(lines)

    def get_group_report(self):
        """BÁO CÁO TÀI CHÍNH CHI TIẾT MODULE STOCK"""
        data = self.db.get_dashboard_data()
        w = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        # Tiền & Giá trị thị trường
        suc_mua = w['balance'] if w else 0
        market_val = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
        nav = suc_mua + market_val
        
        # Vốn & Lãi lỗ
        von_rong = w['total_in'] - w['total_out'] if w else 0
        realized_pl = data['realized'].get('STOCK', 0)
        floating_pl = market_val - sum(h['quantity'] * h['average_price'] for h in holdings)
        total_pl = realized_pl + floating_pl
        roi = (total_pl / von_rong * 100) if von_rong > 0 else 0

        lines = [
            "📑 BÁO CÁO TÀI CHÍNH: CHỨNG KHOÁN",
            draw_line("thick"),
            "🅰️ VỊ THẾ TÀI SẢN (NAV)",
            f"• Tổng tài sản: {format_currency(nav)}",
            f"• Tiền mặt (Sức mua): {format_currency(suc_mua)}",
            f"• Giá trị cổ phiếu: {format_currency(market_val)}",
            "",
            "🅱️ HIỆU QUẢ ĐẦU TƯ (ROI)",
            f"• Vốn ròng đầu tư: {format_currency(von_rong)}",
            f"• Tổng lãi/lỗ: {format_currency(total_pl)} ({format_percent(roi)})",
            f"  + Lãi đã chốt: {format_currency(realized_pl)}",
            f"  + Lãi tạm tính: {format_currency(floating_pl)}",
            draw_line("thin"),
            "📊 CHI TIẾT DANH MỤC & TỈ TRỌNG:"
        ]

        for h in holdings:
            price_buy = h['average_price']
            price_now = h['current_price'] or price_buy
            item_val = h['quantity'] * price_now
            item_weight = (item_val / nav * 100) if nav > 0 else 0
            item_roi = ((price_now / price_buy) - 1) * 100
            
            lines.append(f"💎 {h['symbol']} | Tỉ trọng: {item_weight:.1f}%")
            lines.append(f"   ROI: {format_percent(item_roi)} | GT: {format_currency(item_val)}")
            lines.append(f"   Vốn: {price_buy/1000:,.1f}k | Hiện tại: {price_now/1000:,.1f}k")
            lines.append("")

        lines.append(draw_line("thick"))
        return "\n".join(lines)
