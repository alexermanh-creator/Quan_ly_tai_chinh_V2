# backend/modules/dashboard.py
import re
from backend.database.repository import DatabaseRepo
from backend.core.parser import parse_currency

class DashboardModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def _calculate_smart_goal(self, raw_goal_str, total_capital, current_nav):
        raw = str(raw_goal_str).lower().strip()
        target_nav = total_capital
        
        if raw in ['0', 'hoa von', 'hòa vốn']:
            target_nav = total_capital
        elif '%' in raw:
            match = re.search(r'(\d+(\.\d+)?)', raw)
            if match:
                val = float(match.group(1))
                if 'am' in raw or 'âm' in raw or 'lo' in raw or 'lỗ' in raw or '-' in raw:
                    val = -val
                target_nav = total_capital * (1 + val / 100)
        elif 'lai' in raw or 'lãi' in raw or '+' in raw:
            # Gọt sạch chữ "lãi", chỉ đẩy phần số ("100tr") sang cho parser xử lý
            clean_str = raw.replace('lai', '').replace('lãi', '').replace('+', '').strip()
            try:
                val = parse_currency(clean_str)
                target_nav = total_capital + val
            except: pass
        elif 'am' in raw or 'âm' in raw or 'lo' in raw or 'lỗ' in raw or '-' in raw:
            clean_str = raw.replace('am', '').replace('âm', '').replace('lo', '').replace('lỗ', '').replace('-', '').strip()
            try:
                val = parse_currency(clean_str)
                target_nav = total_capital - val
            except: pass
        else:
            try:
                target_nav = parse_currency(raw)
            except: pass

        gap_to_target = target_nav - current_nav
        return target_nav, gap_to_target

    def get_main_dashboard(self):
        data = self.db.get_dashboard_data()
        wallets = {w['id']: w for w in data['wallets']}
        holdings = data['holdings']
        
        crypto_rate = float(data.get('crypto_rate', 25000))
        
        # 1. TÍNH TỔNG VỐN (CAPITAL)
        total_in = wallets.get('CASH', {}).get('total_in', 0)
        total_out = wallets.get('CASH', {}).get('total_out', 0)
        total_capital = total_in - total_out
        
        # 2. TÍNH TỔNG TÀI SẢN (NAV)
        cash_balance = wallets.get('CASH', {}).get('balance', 0)
        total_assets = cash_balance
        
        stock_assets = 0
        crypto_assets = 0
        other_assets = 0
        
        for h in holdings:
            if h['wallet_id'] == 'CRYPTO':
                val = h['quantity'] * h['current_price'] * crypto_rate
                crypto_assets += val
            else:
                val = h['quantity'] * h['current_price']
                if h['wallet_id'] == 'STOCK': stock_assets += val
                elif h['wallet_id'] == 'OTHER': other_assets += val
                
            total_assets += val
            
        stock_assets += wallets.get('STOCK', {}).get('balance', 0)
        crypto_assets += wallets.get('CRYPTO', {}).get('balance', 0)
        other_assets += wallets.get('OTHER', {}).get('balance', 0)

        # 3. TÍNH LÃI LỖ TỔNG
        total_pl = total_assets - total_capital
        pl_pct = (total_pl / total_capital * 100) if total_capital > 0 else 0
        pl_icon = "🟢" if total_pl >= 0 else "🔴"
        sign = "+" if total_pl > 0 else ""

        # 4. TÍNH MỤC TIÊU (SMART GOAL)
        raw_goal = data.get('goal', '0')
        target_nav, gap = self._calculate_smart_goal(raw_goal, total_capital, total_assets)
        
        if gap > 0:
            gap_str = f"Cần thêm {gap/1000000:,.1f} triệu"
        elif gap < 0:
            gap_str = f"Vượt target {-gap/1000000:,.1f} triệu 🎉"
        else:
            gap_str = "Đã đạt target ✅"

        stock_cap = wallets.get('STOCK', {}).get('total_in', 0) - wallets.get('STOCK', {}).get('total_out', 0)
        crypto_cap = wallets.get('CRYPTO', {}).get('total_in', 0) - wallets.get('CRYPTO', {}).get('total_out', 0)
        other_cap = wallets.get('OTHER', {}).get('total_in', 0) - wallets.get('OTHER', {}).get('total_out', 0)

        msg = f"🏦 **HỆ ĐIỀU HÀNH TÀI CHÍNH V3.4**\n━━━━━━━━━━━━━━━━━━━\n"
        msg += f"💰 Tổng tài sản: {total_assets/1000000:,.1f} triệu\n"
        msg += f"📤 Tổng nạp: {total_in/1000000:,.1f} triệu\n"
        msg += f"📥 Tổng rút: {total_out/1000000:,.1f} triệu\n"
        msg += f"💵 Cash còn lại: {cash_balance:,.0f} đ\n"
        msg += f"📈 Lãi/Lỗ tổng: {sign}{total_pl/1000000:,.1f} triệu ({pl_icon} {sign}{pl_pct:.1f}%)\n"
        msg += f"🎯 Mục tiêu: {raw_goal} (Đích: {target_nav/1000000:,.1f}tr | {gap_str})\n"
        msg += f"────────────\n"
        msg += f"📦 PHÂN BỔ VỐN GỐC (BOOK VALUE):\n"
        msg += f"📈 Stock: {stock_cap/1000000:,.1f} triệu\n"
        msg += f"🟡 Crypto: {crypto_cap/1000000:,.1f} triệu\n"
        msg += f"🥇 Khác: {other_cap/1000000:,.1f} triệu\n"
        msg += f"━━━━━━━━━━━━━━━━━━━\n"

        s_pl = stock_assets - stock_cap
        s_pct = (s_pl / stock_cap * 100) if stock_cap > 0 else 0
        s_icon = "🟢" if s_pl >= 0 else "🔴"
        s_sign = "+" if s_pl > 0 else ""
        msg += f"📈 **STOCK**\n"
        msg += f"💰 Tài sản: {stock_assets/1000000:,.1f} triệu\n"
        msg += f"📤 Nạp: {wallets.get('STOCK', {}).get('total_in', 0)/1000000:,.1f} triệu | 📥 Rút: {wallets.get('STOCK', {}).get('total_out', 0)/1000000:,.1f} triệu\n"
        msg += f"📈 Lãi/Lỗ: {s_sign}{s_pl/1000000:,.1f} triệu ({s_icon} {s_sign}{s_pct:.1f}%)\n"
        msg += f"────────────\n"

        c_pl = crypto_assets - crypto_cap
        c_pct = (c_pl / crypto_cap * 100) if crypto_cap > 0 else 0
        c_icon = "🟢" if c_pl >= 0 else "🔴"
        c_sign = "+" if c_pl > 0 else ""
        msg += f"🟡 **CRYPTO**\n"
        msg += f"💰 Tài sản: {crypto_assets/1000000:,.1f} triệu\n"
        msg += f"📤 Nạp: {wallets.get('CRYPTO', {}).get('total_in', 0)/1000000:,.1f} triệu | 📥 Rút: {wallets.get('CRYPTO', {}).get('total_out', 0)/1000000:,.1f} triệu\n"
        msg += f"📈 Lãi/Lỗ: {c_sign}{c_pl/1000000:,.1f} triệu ({c_icon} {c_sign}{c_pct:.1f}%)\n"
        msg += f"────────────\n"

        o_pl = other_assets - other_cap
        o_pct = (o_pl / other_cap * 100) if other_cap > 0 else 0
        o_icon = "🟢" if o_pl >= 0 else "🔴"
        o_sign = "+" if o_pl > 0 else ""
        msg += f"🥇 **TÀI SẢN KHÁC**\n"
        msg += f"💰 Tài sản: {other_assets/1000000:,.1f} triệu\n"
        msg += f"📤 Nạp: {wallets.get('OTHER', {}).get('total_in', 0)/1000000:,.1f} triệu | 📥 Rút: {wallets.get('OTHER', {}).get('total_out', 0)/1000000:,.1f} triệu\n"
        msg += f"📈 Lãi/Lỗ: {o_sign}{o_pl/1000000:,.1f} triệu ({o_icon} {o_sign}{o_pct:.1f}%)\n"

        return msg
