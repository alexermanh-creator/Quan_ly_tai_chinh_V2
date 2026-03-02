# backend/modules/dashboard.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_main_dashboard(self):
        data = self.db.get_dashboard_data()
        wallets = {w['id']: w for w in data['wallets']}
        holdings = data['holdings']
        
        # 1. Tính toán tầng Module
        def get_mod_stats(mod_id):
            w = wallets.get(mod_id, {'total_in':0, 'total_out':0, 'balance':0})
            h_list = [h for h in holdings if h['wallet_id'] == mod_id]
            asset = w['balance'] + sum(h['quantity'] * (h['current_price'] or h['average_price']) for h in h_list)
            net_inv = w['total_in'] - w['total_out']
            pl = asset - net_inv
            return asset, w['total_in'], w['total_out'], pl, (pl/net_inv*100 if net_inv != 0 else 0)

        s_asset, s_in, s_out, s_pl, s_roi = get_mod_stats('STOCK')
        c_asset, c_in, c_out, c_pl, c_roi = get_mod_stats('CRYPTO')
        k_asset, k_in, k_out, k_pl, k_roi = get_mod_stats('OTHER')

        # 2. Tính toán tầng Master
        cash_left = wallets['CASH']['balance']
        total_asset = s_asset + c_asset + k_asset + cash_left
        total_in = wallets['CASH']['total_in']
        total_out = wallets['CASH']['total_out']
        net_capital = total_in - total_out
        total_pl = total_asset - net_capital

        # 3. Xử lý Mục tiêu linh hoạt
        goal_str = data['goal']
        goal_val = 0
        try:
            if "hoa von" in goal_str: goal_val = 0
            elif "%" in goal_str:
                pct = float(goal_str.replace("lai","").replace("lo","").replace("%","").strip())
                goal_val = net_capital * (pct/100)
            else:
                goal_val = float(goal_str.replace("lai","").replace("lo","").replace("tr","000000").replace("ty","000000000").strip())
        except: goal_val = net_capital * 0.1 # Mặc định lãi 10%

        progress = (total_pl / goal_val * 100) if goal_val != 0 else (100 if total_pl >= 0 else 0)
        
        lines = [
            "🏦 HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0", draw_line("thick"),
            f"💰 Tổng tài sản: {format_currency(total_asset)}",
            f"📤 Tổng nạp: {format_currency(total_in)}",
            f"📥 Tổng rút: {format_currency(total_out)}",
            f"💵 Cash còn lại: {format_currency(cash_left)}",
            f"📈 Lãi/Lỗ tổng: {format_currency(total_pl)} ({format_percent(total_pl/net_capital*100 if net_capital!=0 else 0)})",
            f"🎯 Mục tiêu: {goal_str} ({progress:.1f}% - {format_currency(total_pl)}/{format_currency(goal_val)})",
            draw_line("thin"),
            "📦 PHÂN BỔ VỐN GỐC (BOOK VALUE):",
            f"📈 Stock: {format_currency(s_in - s_out)}",
            f"🟡 Crypto: {format_currency(c_in - c_out)}",
            f"🥇 Khác: {format_currency(k_in - k_out)}",
            draw_line("thick"),
            "📈 STOCK",
            f"💰 Tài sản: {format_currency(s_asset)}",
            f"📤 Nạp: {format_currency(s_in)} | 📥 Rút: {format_currency(s_out)}",
            f"📈 Lãi/Lỗ: {format_currency(s_pl)} ({format_percent(s_roi)})",
            draw_line("thin"),
            "🟡 CRYPTO",
            f"💰 Tài sản: {format_currency(c_asset)}",
            f"📤 Nạp: {format_currency(c_in)} | 📥 Rút: {format_currency(c_out)}",
            f"📈 Lãi/Lỗ: {format_currency(c_pl)} ({format_percent(c_roi)})",
            draw_line("thin"),
            "🥇 TÀI SẢN KHÁC",
            f"💰 Tài sản: {format_currency(k_asset)}",
            f"📤 Nạp: {format_currency(k_in)} | 📥 Rút: {format_currency(k_out)}",
            f"📈 Lãi/Lỗ: {format_currency(k_pl)} ({format_percent(k_roi)})",
            draw_line("thick")
        ]
        return "\n".join(lines)
