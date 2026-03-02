# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        """Giao diện Danh mục khi bấm nút [📊 Chứng Khoán]"""
        data = self.db.get_dashboard_data()
        w = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        suc_mua = w['balance'] if w else 0
        gt_thi_truong = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
        nav_stock = suc_mua + gt_thi_truong
        
        von_rong = (w['total_in'] - w['total_out']) if w else 0
        realized_pl = data['realized'].get('STOCK', 0)
        floating_pl = gt_thi_truong - sum(h['quantity'] * h['average_price'] for h in holdings)
        pl_tong = realized_pl + floating_pl
        pl_pct = (pl_tong / von_rong * 100) if von_rong > 0 else 0

        # Phân tích Mã Tốt/Kém/Tỉ trọng
        best_ma, worst_ma = "--", "--"
        best_info, worst_info = "", ""
        max_sym, max_pct = "--", 0
        
        if holdings:
            processed = []
            for h in holdings:
                p_buy = h['average_price']
                p_now = h['current_price'] or p_buy
                roi = ((p_now / p_buy) - 1) * 100
                amt = h['quantity'] * (p_now - p_buy)
                processed.append({'sym': h['symbol'], 'roi': roi, 'amt': amt, 'val': h['quantity'] * p_now})
            
            best = max(processed, key=lambda x: x['roi'])
            worst = min(processed, key=lambda x: x['roi'])
            
            best_info = f"{best['sym']} ({format_currency(best['amt'])}) ({format_percent(best['roi'])})"
            worst_info = f"{worst['sym']} ({format_currency(worst['amt'])}) ({format_percent(worst['roi'])})"
            
            m_item = max(processed, key=lambda x: x['val'])
            max_sym, max_pct = m_item['sym'], (m_item['val'] / nav_stock * 100) if nav_stock > 0 else 0

        lines = [
            "📊 DANH MỤC CỔ PHIẾU",
            draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(nav_stock)}",
            f"💵 Tổng vốn: {format_currency(von_rong)}",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            f"📈 Lãi/Lỗ: {format_currency(pl_tong)} ({format_percent(pl_pct)})",
            f"⬆️ Tổng nạp ví: {format_currency(w['total_in'] if w else 0)}",
            f"⬇️ Tổng rút ví: {format_currency(w['total_out'] if w else 0)}",
            f"🏆 Mã tốt nhất: {best_info if holdings else '--'}",
            f"📉 Mã kém nhất: {worst_info if holdings else '--'}",
            f"📊 Tỉ trọng lớn nhất: {max_sym} ({max_pct:.1f}%)",
            draw_line("thin")
        ]

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
        """Layout Báo cáo Tài chính khi bấm nút [📈 Báo cáo nhóm]"""
        data = self.db.get_dashboard_data()
        stats = data.get('stats', {'total_buy': 0, 'total_sell': 0})
        pl_syms = data.get('pl_symbols', [])
        
        # Lấy phần Summary từ Dashboard
        summary = self.get_dashboard().split(draw_line("thin"))[0]
        
        top_contrib = [p for p in pl_syms if p['pl'] > 0][:3]
        top_drag = [p for p in pl_syms if p['pl'] < 0][::-1][:3]

        lines = [
            "📑 BÁO CÁO TÀI CHÍNH: CHỨNG KHOÁN",
            draw_line("thick"),
            summary.replace("📊 DANH MỤC CỔ PHIẾU", "").strip(),
            draw_line("thin"),
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
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        if not holdings:
            lines.append("• Trống")
        else:
            for h in holdings:
                p_now = h['current_price'] or h['average_price']
                roi = ((p_now / h['average_price']) - 1) * 100
                lines.append(f"• {h['symbol']}: ROI {format_percent(roi)} | GT: {format_currency(h['quantity']*p_now)}")

        lines.append(draw_line("thick"))
        return "\n".join(lines)
