# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        try:
            data = self.db.get_dashboard_data()
            w = next((x for x in data['wallets'] if x['id'] == 'STOCK'), {'total_in':0, 'total_out':0, 'balance':0})
            holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
            
            gt_thi_truong = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
            nav = w['balance'] + gt_thi_truong
            von_rong = w['total_in'] - w['total_out']
            pl_tong = data['realized'].get('STOCK', 0) + (gt_thi_truong - sum(h['quantity'] * h['average_price'] for h in holdings))

            best_info, worst_info, max_sym, max_pct = "--", "--", "--", 0
            perf_list = []
            perf_map = {p['symbol']: {'pl': p['realized'], 'inv': p['total_invested']} for p in data['perf_symbols']}
            for h in holdings:
                f_pl = h['quantity'] * ((h['current_price'] or h['average_price']) - h['average_price'])
                if h['symbol'] in perf_map: perf_map[h['symbol']]['pl'] += f_pl
                else: perf_map[h['symbol']] = {'pl': f_pl, 'inv': h['quantity'] * h['average_price']}

            if perf_map:
                for s, v in perf_map.items():
                    roi = (v['pl']/v['inv']*100 if v['inv']>0 else 0)
                    perf_list.append({'sym': s, 'roi': roi, 'amt': v['pl']})
                best = max(perf_list, key=lambda x: x['roi'])
                best_info = f"{best['sym']} ({format_percent(best['roi'])}) ({'+' if best['amt']>0 else ''}{format_currency(best['amt'])})"
                worst = min(perf_list, key=lambda x: x['roi'])
                worst_info = f"{worst['sym']} ({format_percent(worst['roi'])})"
                if holdings:
                    max_h = max(holdings, key=lambda x: x['quantity'] * (x['current_price'] or x['average_price']))
                    max_pct = (max_h['quantity'] * (max_h['current_price'] or max_h['average_price']) / nav * 100) if nav > 0 else 0
                    max_sym = max_h['symbol']

            lines = [
                "📊 DANH MỤC CỔ PHIẾU", draw_line("thick"),
                f"💰 Tổng giá trị: {format_currency(nav)}",
                f"🏦 Tổng vốn: {format_currency(von_rong)}",
                f"💸 Sức mua: {format_currency(w['balance'])}",
                f"📈 Lãi/Lỗ: {format_currency(pl_tong)} ({format_percent(pl_tong/von_rong*100 if von_rong>0 else 0)})",
                f"⬆️ Tổng nạp ví: {format_currency(w['total_in'])}",
                f"⬇️ Tổng rút ví: {format_currency(w['total_out'])}",
                f"🏆 Mã tốt nhất: {best_info}",
                f"📉 Mã kém nhất: {worst_info}",
                f"📊 Tỉ trọng lớn nhất: {max_sym} ({max_pct:.1f}%)",
                draw_line("thin")
            ]
            for h in holdings:
                p_now = h['current_price'] or h['average_price']
                roi = ((p_now / h['average_price']) - 1) * 100
                lines += [f"💎 {h['symbol']}", f"• SL: {h['quantity']:,.0f} | Vốn TB: {h['average_price']/1000:,.1f}", 
                          f"• Hiện tại: {p_now/1000:,.1f} | GT: {format_currency(h['quantity']*p_now)}", 
                          f"• Lãi: {format_currency(h['quantity']*(p_now-h['average_price']))} ({format_percent(roi)})", draw_line("thin")]
            lines.append(draw_line("thick"))
            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Stock: {str(e)}"
