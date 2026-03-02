# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        """Layout tiêu chuẩn khi bấm 📊 Chứng Khoán"""
        data = self.db.get_dashboard_data()
        w = next((x for x in data['wallets'] if x['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        suc_mua = w['balance'] if w else 0
        market_val = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
        nav = suc_mua + market_val
        von_rong = (w['total_in'] - w['total_out']) if w else 0
        pl = nav - von_rong
        
        # Tìm Best/Worst/Tỉ trọng
        best_ma, worst_ma = "--", "--"
        best_roi, worst_roi = 0, 0
        max_sym, max_pct = "--", 0
        if holdings:
            items = []
            for h in holdings:
                roi = (( (h['current_price'] or h['average_price']) / h['average_price']) - 1) * 100
                items.append({'sym': h['symbol'], 'roi': roi, 'val': h['quantity'] * (h['current_price'] or h['average_price'])})
            
            best = max(items, key=lambda x: x['roi'])
            worst = min(items, key=lambda x: x['roi'])
            best_ma, best_roi = best['sym'], best['roi']
            worst_ma, worst_roi = worst['sym'], worst['roi']
            
            m_item = max(items, key=lambda x: x['val'])
            max_sym, max_pct = m_item['sym'], (m_item['val'] / nav * 100) if nav > 0 else 0

        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(nav)}",
            f"💵 Tổng vốn: {format_currency(von_rong)}",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            f"📈 Lãi/Lỗ: {format_currency(pl)} ({format_percent(pl/von_rong*100 if von_rong>0 else 0)})",
            f"⬆️ Tổng nạp ví: {format_currency(w['total_in'] if w else 0)}",
            f"⬇️ Tổng rút ví: {format_currency(w['total_out'] if w else 0)}",
            f"🏆 Mã tốt nhất: {best_ma} ({format_percent(best_roi)})",
            f"📉 Mã kém nhất: {worst_ma} ({format_percent(worst_roi)})",
            f"📊 Tỉ trọng lớn nhất: {max_sym} ({max_pct:.1f}%)",
            draw_line("thin")
        ]
        if not holdings: lines.append("❌ Danh mục trống.")
        for h in holdings:
            p_now = h['current_price'] or h['average_price']
            roi_h = ((p_now / h['average_price']) - 1) * 100
            lines.append(f"💎 {h['symbol']}")
            lines.append(f"• SL: {h['quantity']:,.0f} | Vốn TB: {h['average_price']/1000:,.1f}")
            lines.append(f"• Hiện tại: {p_now/1000:,.1f} | GT: {format_currency(h['quantity']*p_now)}")
            lines.append(f"• Lãi: {format_currency(h['quantity']*(p_now-h['average_price']))} ({format_percent(roi_h)})")
            lines.append(draw_line("thin"))
        lines.append(draw_line("thick"))
        return "\n".join(lines)

    def get_group_report(self):
        """Layout Báo cáo tài chính Pro Sếp yêu cầu"""
        data = self.db.get_dashboard_data()
        stats = data['stats']
        pl_syms = data['pl_symbols']
        
        # Phân loại Top Đóng Góp vs Kéo lùi
        top_contrib = [p for p in pl_syms if p['pl'] > 0][:3]
        top_drag = [p for p in pl_syms if p['pl'] < 0][::-1][:3]

        lines = [
            "📑 BÁO CÁO TÀI CHÍNH: CHỨNG KHOÁN",
            draw_line("thick"),
            "🔄 HOẠT ĐỘNG GIAO DỊCH:",
            f"🛒 Tổng mua: {format_currency(stats['total_buy'] or 0)}",
            f"💰 Tổng bán: {format_currency(stats['total_sell'] or 0)}",
            "",
            "🏆 Top Đóng Góp (Lãi chốt):"
        ]
        if not top_contrib: lines.append("• Chưa có dữ liệu lãi.")
        for i, p in enumerate(top_contrib, 1):
            lines.append(f"{i}. {p['symbol']}: +{format_currency(p['pl'])}")
        
        lines.append("\n⚠️ Top Kéo Lùi (Lỗ chốt):")
        if not top_drag: lines.append("• Chưa có dữ liệu lỗ.")
        for i, p in enumerate(top_drag, 1):
            lines.append(f"{i}. {p['symbol']}: {format_currency(p['pl'])}")
        
        lines.append(draw_line("thin"))
        lines.append("📊 CHI TIẾT DANH MỤC HIỆN TẠI:")
        # Tái sử dụng logic hiển thị từng mã từ get_dashboard nhưng lược bỏ phần header tổng
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        for h in holdings:
            p_now = h['current_price'] or h['average_price']
            lines.append(f"• {h['symbol']}: ROI {format_percent(((p_now/h['average_price'])-1)*100)} | GT: {format_currency(h['quantity']*p_now)}")

        lines.append(draw_line("thick"))
        return "\n".join(lines)
