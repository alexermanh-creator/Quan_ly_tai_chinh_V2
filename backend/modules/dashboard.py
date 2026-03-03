# backend/modules/dashboard.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_main_dashboard(self):
        try:
            data = self.db.get_dashboard_data()
            wallets = {w['id']: w for w in data['wallets']}
            holdings = data['holdings']
            realized_pl = data['realized']
            
            rate_row = self.db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
            crypto_rate = float(rate_row['value']) if rate_row else 25000.0
            
            # Master Total: Chỉ tính từ Ví Mẹ
            total_in = wallets.get('CASH', {}).get('total_in', 0)
            total_out = wallets.get('CASH', {}).get('total_out', 0)
            net_invested = total_in - total_out
            cash_balance = wallets.get('CASH', {}).get('balance', 0)

            w_assets, w_pl, w_book_value = {}, {}, {}
            for wid in ['STOCK', 'CRYPTO', 'OTHER']:
                w = wallets.get(wid, {'balance':0, 'total_in':0, 'total_out':0})
                h_list = [h for h in holdings if h['wallet_id'] == wid]
                
                gt_thi_truong = 0
                cost_vnd = 0
                for h in h_list:
                    p_now = h['current_price'] or h['average_price']
                    mult = crypto_rate if wid == 'CRYPTO' else 1
                    gt_thi_truong += (h['quantity'] * p_now * mult)
                    cost_vnd += h.get('cost_basis_vnd', 0)

                w_assets[wid] = w['balance'] + gt_thi_truong
                w_pl[wid] = realized_pl.get(wid, 0) + (gt_thi_truong - cost_vnd)
                w_book_value[wid] = w['balance'] + cost_vnd

            total_assets = cash_balance + sum(w_assets.values())
            total_pl = sum(w_pl.values())
            pl_pct = (total_pl / net_invested * 100) if net_invested > 0 else 0

            lines = [
                "🏦 HỆ ĐIỀU HÀNH TÀI CHÍNH V3.2", draw_line("thick"),
                f"💰 Tổng tài sản: {format_currency(total_assets)}",
                f"📤 Tổng nạp: {format_currency(total_in)} | 📥 Rút: {format_currency(total_out)}",
                f"💵 Cash còn lại: {format_currency(cash_balance)}",
                f"📈 Lãi/Lỗ tổng: {format_currency(total_pl)} ({format_percent(pl_pct)})",
                draw_line("thin"),
                "📦 PHÂN BỔ VỐN GỐC (BOOK VALUE):",
                f"📈 Stock: {format_currency(w_book_value['STOCK'])}",
                f"🟡 Crypto: {format_currency(w_book_value['CRYPTO'])}",
                f"🥇 Khác: {format_currency(w_book_value['OTHER'])}",
                draw_line("thick")
            ]

            icons = {'STOCK': '📈', 'CRYPTO': '🟡', 'OTHER': '🥇'}
            for wid in ['STOCK', 'CRYPTO', 'OTHER']:
                w = wallets.get(wid, {'total_in': 0, 'total_out': 0})
                von_ví = w['total_in'] - w['total_out']
                roi = (w_pl[wid] / von_ví * 100) if von_ví > 0 else 0
                lines += [
                    f"{icons[wid]} {wid}",
                    f"💰 Tài sản: {format_currency(w_assets[wid])}",
                    f"📤 Nạp: {format_currency(w['total_in'])} | 📥 Rút: {format_currency(w['total_out'])}",
                    f"📈 Lãi/Lỗ: {format_currency(w_pl[wid])} ({format_percent(roi)})",
                    draw_line("thin")
                ]
            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Dashboard: {str(e)}"
