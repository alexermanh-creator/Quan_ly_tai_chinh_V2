# backend/modules/crypto.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class CryptoModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self, is_report=False):
        try:
            data = self.db.get_dashboard_data()
            w = next((x for x in data['wallets'] if x['id'] == 'CRYPTO'), {'balance':0, 'total_in':0, 'total_out':0})
            holdings = [h for h in data['holdings'] if h['wallet_id'] == 'CRYPTO']
            perf = [p for p in data['perf_symbols'] if p['wallet_id'] == 'CRYPTO']
            
            rate_row = self.db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
            rate = float(rate_row['value']) if rate_row else 25000.0

            gt_thi_truong_vnd = sum(h['quantity'] * (h['current_price'] or h['average_price']) * rate for h in holdings)
            cost_basis_total_vnd = sum(h.get('cost_basis_vnd', 0) for h in holdings)
            von_ví_vnd = w['total_in'] - w['total_out']
            pl_tong_vnd = data['realized'].get('CRYPTO', 0) + (gt_thi_truong_vnd - cost_basis_total_vnd)

            header = "📑 BÁO CÁO TÀI CHÍNH: CRYPTO" if is_report else f"🪙 DANH MỤC TIỀN ĐIỆN TỬ (Rate: {rate:,.0f}đ)"
            lines = [
                header, draw_line("thick"),
                f"💰 Tổng giá trị: {format_currency(w['balance'] + gt_thi_truong_vnd)}",
                f"💵 Tổng vốn: {format_currency(von_ví_vnd)}",
                f"💸 Sức mua: {format_currency(w['balance'])}",
                f"📈 Lãi/Lỗ: {format_currency(pl_tong_vnd)} ({format_percent(pl_tong_vnd/von_ví_vnd*100 if von_ví_vnd>0 else 0)})",
                draw_line("thin"),
                "🔄 HOẠT ĐỘNG GIAO DỊCH (VNĐ):",
                f"🛒 Tổng mua: {format_currency(sum(abs(p['total_invested']) for p in perf))}",
                f"💰 Tổng bán: {format_currency(sum(p['realized'] + abs(p['total_invested']) for p in perf if p['realized'] != 0))}",
                "",
                "🏆 Top Đóng Góp (Lãi chốt):"
            ]
            
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
                    gt_h_vnd = h['quantity'] * p_now * rate
                    roi_h = (gt_h_vnd / h['cost_basis_vnd'] - 1) * 100 if h['cost_basis_vnd'] > 0 else 0
                    lines.append(f"• {h['symbol']}: ROI {format_percent(roi_h)} | GT: {format_currency(gt_h_vnd)}")
            
            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Crypto Report: {str(e)}"

    def get_group_report(self):
        return self.get_dashboard(is_report=True)
