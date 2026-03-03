# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        try:
            data = self.db.get_dashboard_data()
            w = next((x for x in data['wallets'] if x['id'] == 'STOCK'), {'balance':0, 'total_in':0, 'total_out':0})
            holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
            
            # Lọc chỉ lấy các mã thuộc ví STOCK để tìm mã tốt nhất/kém nhất
            perf = [p for p in data['perf_symbols'] if p['wallet_id'] == 'STOCK']
            best = max(perf, key=lambda x: x['realized'], default=None)
            worst = min(perf, key=lambda x: x['realized'], default=None)

            gt_thi_truong = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
            cost_vnd = sum(h.get('cost_basis_vnd', 0) for h in holdings)
            pl_thuc_te = data['realized'].get('STOCK', 0) + (gt_thi_truong - cost_vnd)
            von_cap = w['total_in'] - w['total_out']

            lines = [
                "📊 DANH MỤC CỔ PHIẾU", draw_line("thick"),
                f"💰 Tổng giá trị: {format_currency(w['balance'] + gt_thi_truong)}",
                f"🏦 Tổng vốn: {format_currency(von_cap)}",
                f"💸 Sức mua: {format_currency(w['balance'])}",
                f"📈 Lãi/Lỗ: {format_currency(pl_thuc_te)} ({format_percent(pl_thuc_te/von_cap*100 if von_cap>0 else 0)})",
                f"⬆️ Tổng nạp ví: {format_currency(w['total_in'])}",
                f"⬇️ Tổng rút ví: {format_currency(w['total_out'])}",
                f"🏆 Mã tốt nhất: {best['symbol'] if best else '--'} ({format_currency(best['realized'] if best else 0)})",
                f"📉 Mã kém nhất: {worst['symbol'] if worst else '--'}",
                f"📊 Tỉ trọng lớn nhất: {max(holdings, key=lambda x: x['quantity']*x['average_price'], default={'symbol':'--'})['symbol']}",
                draw_line("thin")
            ]
            for h in holdings:
                p_now = h['current_price'] or h['average_price']
                lines += [f"💎 {h['symbol']}", f"• SL: {h['quantity']:,} | Vốn TB: {h['average_price']:,}", f"• Hiện tại: {p_now:,} | GT: {format_currency(h['quantity']*p_now)}", draw_line("thin")]
            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Stock Dashboard: {str(e)}"

    def get_group_report(self):
        # Tương tự như get_dashboard nhưng format theo kiểu báo cáo
        return self.get_dashboard().replace("DANH MỤC", "BÁO CÁO NHÓM")
