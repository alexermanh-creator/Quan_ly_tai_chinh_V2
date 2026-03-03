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
            
            # Lấy tỷ giá Crypto từ Database
            rate_row = self.db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
            crypto_rate = float(rate_row['value']) if rate_row else 25000.0
            
            total_in = sum(w['total_in'] for w in wallets.values())
            total_out = sum(w['total_out'] for w in wallets.values())
            net_invested = total_in - total_out
            cash_balance = wallets.get('CASH', {}).get('balance', 0)

            # Tính GT tài sản theo từng ví (Có xử lý Tỷ giá riêng cho Crypto)
            w_assets = {'STOCK': 0, 'CRYPTO': 0, 'OTHER': 0}
            w_pl = {'STOCK': 0, 'CRYPTO': 0, 'OTHER': 0}
            
            for wid in w_assets.keys():
                w_balance = wallets.get(wid, {}).get('balance', 0)
                h_list = [h for h in holdings if h['wallet_id'] == wid]
                
                gt_thi_truong = 0
                tong_von_mua = 0
                
                # Logic tính toán Market Value
                for h in h_list:
                    p_now = h['current_price'] or h['average_price']
                    if wid == 'CRYPTO':
                        gt_thi_truong += (h['quantity'] * p_now * crypto_rate)
                        tong_von_mua += (h['quantity'] * h['average_price'] * crypto_rate)
                    else:
                        gt_thi_truong += (h['quantity'] * p_now)
                        tong_von_mua += (h['quantity'] * h['average_price'])

                # Tài sản = Tiền mặt dư trong ví + Giá trị thị trường
                w_assets[wid] = w_balance + gt_thi_truong
                
                # Tính Lãi/Lỗ: Lãi chốt + Lãi tạm tính
                r_pl = realized_pl.get(wid, 0)
                float_pl = gt_thi_truong - tong_von_mua
                w_pl[wid] = r_pl + float_pl

            total_assets = cash_balance + sum(w_assets.values())
            total_pl = sum(w_pl.values())
            pl_pct = (total_pl / net_invested * 100) if net_invested > 0 else 0

            # Xử lý Goal
            goal_str = data.get('goal', 'lai 10%')
            goal_target = 0
            goal_pct = 0
            if goal_str.startswith('lai '):
                val = goal_str.replace('lai ', '').strip()
                if '%' in val:
                    goal_target = net_invested * float(val.replace('%','')) / 100
                else:
                    mult = 1_000_000_000 if 'ty' in val else (1_000_000 if 'tr' in val else 1)
                    num_str = val.replace('ty','').replace('trieu','').replace('tr','').strip()
                    try: goal_target = float(num_str) * mult
                    except: pass
                if goal_target > 0: goal_pct = (total_pl / goal_target) * 100
            elif goal_str == 'hoa von':
                goal_target = 0
                goal_pct = 100 if total_pl >= 0 else 0

            # Cấu trúc hiển thị
            lines = [
                "🏦 HỆ ĐIỀU HÀNH TÀI CHÍNH V3.0", draw_line("thick"),
                f"💰 Tổng tài sản: {format_currency(total_assets)}",
                f"📤 Tổng nạp: {format_currency(total_in)}",
                f"📥 Tổng rút: {format_currency(total_out)}",
                f"💵 Cash còn lại: {format_currency(cash_balance)}",
                f"📈 Lãi/Lỗ tổng: {format_currency(total_pl)} ({format_percent(pl_pct)})",
                f"🎯 Mục tiêu: {goal_str} ({goal_pct:.1f}% - {format_currency(total_pl)}/{format_currency(goal_target)})",
                draw_line("thin"),
                "📦 PHÂN BỔ VỐN GỐC (BOOK VALUE):",
                f"📈 Stock: {format_currency(wallets.get('STOCK',{}).get('total_in',0) - wallets.get('STOCK',{}).get('total_out',0))}",
                f"🟡 Crypto: {format_currency(wallets.get('CRYPTO',{}).get('total_in',0) - wallets.get('CRYPTO',{}).get('total_out',0))}",
                f"🥇 Khác: {format_currency(wallets.get('OTHER',{}).get('total_in',0) - wallets.get('OTHER',{}).get('total_out',0))}",
                draw_line("thick")
            ]

            # Chi tiết từng ví
            icons = {'STOCK': '📈', 'CRYPTO': '🟡', 'OTHER': '🥇'}
            names = {'STOCK': 'STOCK', 'CRYPTO': 'CRYPTO', 'OTHER': 'TÀI SẢN KHÁC'}
            
            for wid in ['STOCK', 'CRYPTO', 'OTHER']:
                w = wallets.get(wid, {'total_in':0, 'total_out':0})
                net_w = w['total_in'] - w['total_out']
                pl_w_pct = (w_pl[wid] / net_w * 100) if net_w > 0 else 0
                
                lines += [
                    f"{icons[wid]} {names[wid]}",
                    f"💰 Tài sản: {format_currency(w_assets[wid])}",
                    f"📤 Nạp: {format_currency(w['total_in'])} | 📥 Rút: {format_currency(w['total_out'])}",
                    f"📈 Lãi/Lỗ: {format_currency(w_pl[wid])} ({format_percent(pl_w_pct)})",
                    draw_line("thin") if wid != 'OTHER' else draw_line("thick")
                ]

            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Dashboard: {str(e)}"
