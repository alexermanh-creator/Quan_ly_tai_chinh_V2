# backend/modules/stock.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self, is_report=False):
        try:
            data = self.db.get_dashboard_data()
            w = next((x for x in data['wallets'] if x['id'] == 'STOCK'), {'balance':0, 'total_in':0, 'total_out':0})
            holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
            
            # Lọc dữ liệu giao dịch cho ví STOCK
            perf = [p for p in data['perf_symbols'] if p['wallet_id'] == 'STOCK']
            best = max(perf, key=lambda x: x['realized'], default=None)
            worst = min(perf, key=lambda x: x['realized'], default=None)

            gt_thi_truong = sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in holdings)
            cost_basis_vnd = sum(h.get('cost_basis_vnd', 0) for h in holdings)
            pl_thuc_te = data['realized'].get('STOCK', 0) + (gt_thi_truong - cost_basis_vnd)
            von_cap = w['total_in'] - w['total_out']

            header = "📑 BÁO CÁO TÀI CHÍNH: CHỨNG KHOÁN" if is_report else "📊 DANH MỤC CỔ PHIẾU"
            lines = [
                header, draw_line("thick"),
                f"💰 Tổng giá trị: {format_currency(w['balance'] + gt_thi_truong)}",
                f"💵 Tổng vốn: {format_currency(von_cap)}",
                f"💸 Sức mua: {format_currency(w['balance'])}",
                f"📈 Lãi/Lỗ: {format_currency(pl_thuc_te)} ({format_percent(pl_thuc_te/von_cap*100 if von_cap>0 else 0)})",
                f"⬆️ Tổng nạp ví: {format_currency(w['total_in'])}",
                f"⬇️ Tổng rút ví: {format_currency(w['total_out'])}",
                f"🏆 Mã tốt nhất: {best['symbol'] if best else '--'} ({format_currency(best['realized'] if best else 0)})",
                f"📉 Mã kém nhất: {worst['symbol'] if worst else '--'}",
                draw_line("thin"),
                "🔄 HOẠT ĐỘNG GIAO DỊCH:",
                f"🛒 Tổng mua: {format_currency(sum(abs(p['total_invested']) for p in perf))}",
                f"💰 Tổng bán: {format_currency(sum(p['realized'] + p['total_invested'] for p in perf if p['realized'] != 0))}",
                "",
                "🏆 Top Đóng Góp (Lãi chốt):"
            ]
            
            # Khối Top Lãi/Lỗ
            top_gain = sorted([p for p in perf if p['realized'] > 0], key=lambda x: x['realized'], reverse=True)
            if not top_gain: lines.append("• Chưa có dữ liệu lãi.")
            for i, p in enumerate(top_gain[:3], 1):
                lines.append(f"{i}. {p['symbol']}: +{format_currency(p['realized'])}")
            
            lines += [draw_line("thin"), "📊 CHI TIẾT DANH MỤC HIỆN TẠI:"]
            if not holdings:
                lines.append("• Trống")
            else:
                for h in holdings:
                    p_now = h['current_price'] or h['average_price']
                    roi = ((p_now / h['average_price']) - 1) * 100
                    lines.append(f"• {h['symbol']}: ROI {format_percent(roi)} | GT: {format_currency(h['quantity']*p_now)}")
            
            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Stock Report: {str(e)}"

    def get_group_report(self):
        return self.get_dashboard(is_report=True)
