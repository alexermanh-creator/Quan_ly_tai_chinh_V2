# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self, is_report=False):
        data = self.db.get_dashboard_data()
        w = next((x for x in data['wallets'] if x['id'] == 'STOCK'), None)
        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        
        suc_mua = w['balance'] if w else 0
        gt_thi_truong = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
        nav = suc_mua + gt_thi_truong
        von_rong = (w['total_in'] - w['total_out']) if w else 0
        
        realized_total = data['realized'].get('STOCK', 0)
        floating_total = gt_thi_truong - sum(h['quantity'] * h['average_price'] for h in holdings)
        pl_tong = realized_total + floating_total

        # --- LOGIC PHÂN TÍCH SIÊU SAO (GỘP LỊCH SỬ & HIỆN TẠI) ---
        perf_map = {}
        # 1. Lấy dữ liệu lịch sử từ perf_symbols (Realized & Total Invested)
        for p in data['perf_symbols']:
            perf_map[p['symbol']] = {
                'total_pl': p['realized'],
                'invested': p['total_invested']
            }
        
        # 2. Cộng thêm lãi treo (Floating) của hàng đang cầm
        for h in holdings:
            p_now = h['current_price'] or h['average_price']
            f_pl = h['quantity'] * (p_now - h['average_price'])
            if h['symbol'] in perf_map:
                perf_map[h['symbol']]['total_pl'] += f_pl
            else:
                perf_map[h['symbol']] = {
                    'total_pl': f_pl,
                    'invested': h['quantity'] * h['average_price']
                }

        best_info, worst_info, max_sym, max_pct = "--", "--", "--", 0
        if perf_map:
            perf_list = []
            for sym, p in perf_map.items():
                roi = (p['total_pl'] / p['invested'] * 100) if p['invested'] > 0 else 0
                perf_list.append({'sym': sym, 'roi': roi, 'amt': p['total_pl']})
            
            # Tìm Mã Tốt Nhất (Dựa trên ROI tổng hợp)
            best = max(perf_list, key=lambda x: x['roi'])
            prefix_b = "+" if best['amt'] > 0 else ""
            best_info = f"{best['sym']} ({format_percent(best['roi'])}) ({prefix_b}{format_currency(best['amt'])})"
            
            # Chỉ hiện Mã Kém Nhất nếu có từ 2 mã khác nhau trở lên
            if len(perf_list) > 1:
                worst = min(perf_list, key=lambda x: x['roi'])
                if worst['sym'] != best['sym']:
                    prefix_w = "+" if worst['amt'] > 0 else ""
                    worst_info = f"{worst['sym']} ({format_percent(worst['roi'])}) ({prefix_w}{format_currency(worst['amt'])})"
            
            # Tỉ trọng lớn nhất (Chỉ tính trên NAV thực tế đang cầm)
            if holdings:
                max_h = max(holdings, key=lambda x: x['quantity'] * (x['current_price'] or x['average_price']))
                max_val = max_h['quantity'] * (max_h['current_price'] or max_h['average_price'])
                max_sym, max_pct = max_h['symbol'], (max_val / nav * 100) if nav > 0 else 0

        # --- RENDER LAYOUT ---
        header = "📑 BÁO CÁO TÀI CHÍNH: CHỨNG KHOÁN" if is_report else "📊 DANH MỤC CỔ PHIẾU"
        lines = [
            header, draw_line("thick"),
            f"💰 Tổng giá trị: {format_currency(nav)}",
            f"💵 Tổng vốn: {format_currency(von_rong)}",
            f"💸 Sức mua: {format_currency(suc_mua)}",
            f"📈 Lãi/Lỗ: {format_currency(pl_tong)} ({format_percent(pl_tong/von_rong*100 if von_rong>0 else 0)})",
            f"⬆️ Tổng nạp ví: {format_currency(w['total_in'] if w else 0)}",
            f"⬇️ Tổng rút ví: {format_currency(w['total_out'] if w else 0)}",
            f"🏆 Mã tốt nhất: {best_info}",
            f"📉 Mã kém nhất: {worst_info}",
            f"📊 Tỉ trọng lớn nhất: {max_sym} ({max_pct:.1f}%)",
            draw_line("thin")
        ]

        if is_report:
            stats = data['stats']
            lines += [
                "🔄 HOẠT ĐỘNG GIAO DỊCH:",
                f"🛒 Tổng mua: {format_currency(stats['total_buy'] or 0)}",
                f"💰 Tổng bán: {format_currency(stats['total_sell'] or 0)}", "",
                "🏆 Top Đóng Góp (Lãi chốt):"
            ]
            contrib = [p for p in data['perf_symbols'] if p['realized'] > 0][:3]
            if not contrib: lines.append("• Chưa có dữ liệu lãi.")
            for i, p in enumerate(contrib, 1): lines.append(f"{i}. {p['symbol']}: +{format_currency(p['realized'])}")
            
            lines += ["", "⚠️ Top Kéo Lùi (Lỗ chốt):"]
            drag = [p for p in data['perf_symbols'] if p['realized'] < 0][::-1][:3]
            if not drag: lines.append("• Chưa có dữ liệu lỗ.")
            for i, p in enumerate(drag, 1): lines.append(f"{i}. {p['symbol']}: {format_currency(p['realized'])}")
            lines.append(draw_line("thin"), "📊 CHI TIẾT DANH MỤC HIỆN TẠI:")

        for h in holdings:
            p_now = h['current_price'] or h['average_price']
            roi_h = ((p_now / h['average_price']) - 1) * 100
            if is_report:
                lines.append(f"• {h['symbol']}: ROI {format_percent(roi_h)} | GT: {format_currency(h['quantity']*p_now)}")
            else:
                lines += [
                    f"💎 {h['symbol']}",
                    f"• SL: {h['quantity']:,.0f} | Vốn TB: {h['average_price']/1000:,.1f}",
                    f"• Hiện tại: {p_now/1000:,.1f} | GT: {format_currency(h['quantity']*p_now)}",
                    f"• Lãi: {format_currency(h['quantity']*(p_now-h['average_price']))} ({format_percent(roi_h)})",
                    draw_line("thin")
                ]
        
        lines.append(draw_line("thick"))
        return "\n".join(lines)

    def get_group_report(self):
        return self.get_dashboard(is_report=True)
