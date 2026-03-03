# backend/modules/crypto.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class CryptoModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        try:
            data = self.db.get_dashboard_data()
            w = next((x for x in data['wallets'] if x['id'] == 'CRYPTO'), {'total_in':0, 'total_out':0, 'balance':0})
            holdings = [h for h in data['holdings'] if h['wallet_id'] == 'CRYPTO']
            
            rate_row = self.db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
            rate = float(rate_row['value']) if rate_row else 25000.0

            gt_thi_truong_vnd = sum(h['quantity'] * (h['current_price'] or h['average_price']) * rate for h in holdings)
            cost_basis_total_vnd = sum(h.get('cost_basis_vnd', 0) for h in holdings)
            
            nav_vnd = w['balance'] + gt_thi_truong_vnd
            von_ví_vnd = w['total_in'] - w['total_out']
            # Lãi = Lãi đã chốt + (Giá trị hiện tại - Vốn bỏ ra thực tế)
            pl_tong_vnd = data['realized'].get('CRYPTO', 0) + (gt_thi_truong_vnd - cost_basis_total_vnd)

            lines = [
                f"🪙 DANH MỤC TIỀN ĐIỆN TỬ (Rate: {rate:,.0f}đ)", draw_line("thick"),
                f"💰 Tổng giá trị: {format_currency(nav_vnd)} (~{nav_vnd/rate:,.0f} USDT)",
                f"🏦 Tổng vốn: {format_currency(von_ví_vnd)}",
                f"💸 Sức mua: {format_currency(w['balance'])} (~{w['balance']/rate:,.0f} USDT)",
                f"📈 Lãi/Lỗ: {format_currency(pl_tong_vnd)} ({format_percent(pl_tong_vnd/von_ví_vnd*100 if von_ví_vnd>0 else 0)})",
                draw_line("thin")
            ]

            if not holdings:
                lines.append("• Danh mục hiện tại đang trống.")
            else:
                for h in holdings:
                    p_now = h['current_price'] or h['average_price']
                    gt_h_vnd = h['quantity'] * p_now * rate
                    roi_h = (gt_h_vnd / h['cost_basis_vnd'] - 1) * 100 if h['cost_basis_vnd'] > 0 else 0
                    lines += [
                        f"💎 {h['symbol']}",
                        f"• SL: {h['quantity']} | Vốn TB: {h['average_price']:,.2f} $",
                        f"• Hiện tại: {p_now:,.2f} $ | GT: {format_currency(gt_h_vnd)}",
                        f"• Lãi: {format_currency(gt_h_vnd - h['cost_basis_vnd'])} ({format_percent(roi_h)})",
                        draw_line("thin")
                    ]
            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Crypto: {str(e)}"

    def get_group_report(self):
        # Báo cáo nhóm của Crypto
        return self.get_dashboard().replace("DANH MỤC", "BÁO CÁO NHÓM")
