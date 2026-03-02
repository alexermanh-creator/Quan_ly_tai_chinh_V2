# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self, is_report=False):
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
                    perf_list.append({'sym': s, 'roi': (v['pl']/v['inv']*100 if v['inv']>0 else 0), 'amt': v['pl']})
                best = max(perf_list, key=lambda x: x['roi'])
                best_info = f"{best['sym']} ({format_percent(best['roi'])}) ({'+' if best['amt']>0 else ''}{format_currency(best['amt'])})"
                if len(perf_list) > 1:
                    worst = min(perf_list, key=lambda x: x['roi'])
                    if worst['sym'] != best['sym']:
                        worst_info = f"{worst['sym']} ({format_percent(worst['roi'])}) ({'+' if worst['amt']>0 else ''}{format_currency(worst['amt'])})"

            header = "📑 BÁO CÁO TÀI CHÍNH: CHỨNG KHOÁN" if is_report else "📊 DANH MỤC CỔ PHIẾU"
            lines = [header, draw_line("thick"), f"💰 Tổng giá trị: {format_currency(nav)}", f"💸 Sức mua: {format_currency(w['balance'])}", f"📈 Lãi/Lỗ: {format_currency(pl_tong)} ({format_percent(pl_tong/von_rong*100 if von_rong>0 else 0)})", draw_line("thin")]

            for h in holdings:
                p_now = h['current_price'] or h['average_price']
                roi = ((p_now / h['average_price']) - 1) * 100
                lines += [f"💎 {h['symbol']} | Lãi: {format_percent(roi)}", f"• GT: {format_currency(h['quantity']*p_now)}", draw_line("thin")]
            
            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Stock: {str(e)}"

    def get_group_report(self): return self.get_dashboard(is_report=True)
