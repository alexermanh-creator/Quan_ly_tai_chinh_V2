# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        """Giao diện Danh mục Cổ phiếu chuẩn Layout Sếp yêu cầu"""
        data = self.db.get_dashboard_data()
        w = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        # 1. Tính toán thông số tổng quát
        suc_mua = w['balance'] if w else 0
        total_in = w['total_in'] if w else 0
        total_out = w['total_out'] if w else 0
        von_rong = total_in - total_out
        
        # Giá trị thị trường hiện tại
        gt_thi_truong = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
        nav_stock = suc_mua + gt_thi_truong
        
        # Lãi lỗ thực tế (Floating + Realized)
        realized_pl = data['realized'].get('STOCK', 0)
        floating_pl = gt_thi_truong - sum(h['quantity'] * h['average_price'] for h in holdings)
        pl_tong = realized_pl + floating_pl
        pl_pct = (pl_tong / von_rong * 100) if von_rong > 0 else 0

        # 2. Phân tích Mã Tốt/Kém/Tỉ trọng
        best_ma, worst_ma = "--", "--"
        best_roi, worst_roi = 0, 0
        max_weight_sym, max_weight_pct = "--", 0
        
        if holdings:
            processed_holdings = []
            for h in holdings:
                p_buy = h['average_price']
                p_now = h['current_price'] or p_buy
                roi = ((p_now / p_buy) - 1) * 100
                processed_holdings.append({'sym': h['symbol'], 'roi': roi, 'val': h['quantity'] * p_now})
            
            # Tìm Best/Worst
            best_item = max(processed_holdings, key=lambda x: x['roi'])
            worst_item = min(processed_holdings, key=lambda x: x['roi'])
            best_ma, best_roi = best_item['sym'], best_item['roi']
            worst_ma, worst_roi = worst_item['sym'], worst_item['roi']
            
            # Tìm Tỉ trọng lớn nhất
            max_item = max(processed_holdings, key=lambda x: x['val'])
            max_weight_sym = max_item['sym']
            max_weight_pct = (max_item['val'] / nav_stock * 100) if nav_stock > 0 else 0

        # 3. Render Layout
        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(nav_stock)}",
            f"💵 Tổng vốn: {format_currency(von_rong)}",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            f"📈 Lãi/Lỗ: {format_currency(pl_tong)} ({format_percent(pl_pct)})",
            f"⬆️ Tổng nạp ví: {format_currency(total_in)}",
            f"⬇️ Tổng rút ví: {format_currency(total_out)}",
            f"🏆 Mã tốt nhất: {best_ma} ({format_percent(best_roi)})",
            f"📉 Mã kém nhất: {worst_ma} ({format_percent(worst_roi)})",
            f"📊 Tỉ trọng lớn nhất: {max_weight_sym} ({max_weight_pct:.1f}%)",
            draw_line("thin")
        ]

        if not holdings:
            lines.append("❌ Danh mục hiện đang trống.")
        else:
            for h in holdings:
                p_buy = h['average_price']
                p_now = h['current_price'] or p_buy
                gt_ma = h['quantity'] * p_now
                roi_ma = ((p_now / p_buy) - 1) * 100
                pl_ma = gt_ma - (h['quantity'] * p_buy)
                
                lines.append(f"💎 {h['symbol']}")
                lines.append(f"• SL: {h['quantity']:,.0f} | Vốn TB: {p_buy/1000:,.1f}")
                lines.append(f"• Hiện tại: {p_now/1000:,.1f} | GT: {format_currency(gt_ma)}")
                lines.append(f"• Lãi: {format_currency(pl_ma)} ({format_percent(roi_ma)})")
                lines.append(draw_line("thin"))
            
        lines.append(draw_line("thick"))
        return "\n".join(lines)

    def get_group_report(self):
        """Hàm này Sếp dùng cho nút [📈 Báo cáo nhóm]"""
        # Sếp yêu cầu báo cáo đầy đủ như Báo cáo tài chính
        # Tôi sẽ tái sử dụng Dashboard nhưng trình bày dưới dạng văn bản báo cáo
        return self.get_dashboard().replace("📊 DANH MỤC CỔ PHIẾU", "📑 BÁO CÁO TÀI CHÍNH: CHỨNG KHOÁN")
