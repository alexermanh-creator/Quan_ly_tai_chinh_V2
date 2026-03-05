# backend/modules/stock.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from backend.database.repository import DatabaseRepo

class StockModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def format_money(self, amount):
        if abs(amount) >= 1000000:
            return f"{amount / 1000000:,.1f} triệu"
        return f"{amount:,.0f} đ"

    def _calculate_metrics(self):
        data = self.db.get_dashboard_data()
        wallet = next((w for w in data['wallets'] if w['id'] == 'STOCK'), None)
        if not wallet: return None

        holdings = [h for h in data['holdings'] if h['wallet_id'] == 'STOCK']
        transactions = self.db.execute_query("SELECT * FROM transactions WHERE wallet_id = 'STOCK'", fetch_all=True)

        cash = wallet['balance']
        total_in = wallet['total_in']
        total_out = wallet['total_out']
        book_value = total_in - total_out

        total_asset_value = 0
        best_sym, worst_sym, largest_sym = None, None, None
        best_profit, worst_profit, max_val = -float('inf'), float('inf'), -1

        holdings_details = []

        for h in holdings:
            qty = h['quantity']
            avg_price = h['average_price']
            cur_price = h['current_price']
            cost = h['cost_basis_vnd']
            val = qty * cur_price
            
            total_asset_value += val
            profit = val - cost
            roi = (profit / cost * 100) if cost > 0 else 0

            holdings_details.append({
                'sym': h['symbol'],
                'qty': qty,
                'avg': avg_price,
                'cur': cur_price,
                'val': val,
                'profit': profit,
                'roi': roi
            })

            if profit > best_profit:
                best_profit = profit
                best_sym = h['symbol']
            if profit < worst_profit:
                worst_profit = profit
                worst_sym = h['symbol']
            if val > max_val:
                max_val = val
                largest_sym = h['symbol']

        total_value = cash + total_asset_value
        total_profit = total_value - book_value
        total_roi = (total_profit / book_value * 100) if book_value > 0 else 0

        # Lịch sử giao dịch
        total_buy = sum(abs(t['amount']) for t in transactions if t['type'] == 'MUA')
        total_sell = sum(abs(t['amount']) for t in transactions if t['type'] == 'BAN')
        
        realized_pl = [t for t in transactions if t['realized_pl'] and t['symbol']]
        realized_dict = {}
        for t in realized_pl:
            realized_dict[t['symbol']] = realized_dict.get(t['symbol'], 0) + t['realized_pl']
        
        top_gainers = sorted([(k, v) for k, v in realized_dict.items() if v > 0], key=lambda x: x[1], reverse=True)
        top_losers = sorted([(k, v) for k, v in realized_dict.items() if v < 0], key=lambda x: x[1])

        return {
            'cash': cash, 'total_in': total_in, 'total_out': total_out, 'book_value': book_value,
            'total_value': total_value, 'total_profit': total_profit, 'total_roi': total_roi,
            'best_sym': best_sym, 'best_profit': best_profit,
            'worst_sym': worst_sym, 'worst_profit': worst_profit,
            'largest_sym': largest_sym, 'max_val': max_val,
            'holdings': holdings_details,
            'total_buy': total_buy, 'total_sell': total_sell,
            'top_gainers': top_gainers, 'top_losers': top_losers
        }

    def get_dashboard(self):
        m = self._calculate_metrics()
        if not m: return "Chưa có dữ liệu Ví Chứng Khoán."

        icon_roi = "🟢" if m['total_roi'] >= 0 else "🔴"
        
        msg = f"📊 **DANH MỤC CỔ PHIẾU**\n━━━━━━━━━━━━━━━━━━━\n"
        msg += f"💰 Tổng giá trị: {self.format_money(m['total_value'])}\n"
        msg += f"💵 Tổng vốn: {self.format_money(m['book_value'])}\n"
        msg += f"💸 Sức mua: {self.format_money(m['cash'])}\n"
        msg += f"📈 Lãi/Lỗ: {self.format_money(m['total_profit'])} ({icon_roi} {m['total_roi']:+.1f}%)\n"
        msg += f"⬆️ Tổng nạp ví: {self.format_money(m['total_in'])}\n"
        msg += f"⬇️ Tổng rút ví: {self.format_money(m['total_out'])}\n"

        if m['holdings']:
            best_roi = next((h['roi'] for h in m['holdings'] if h['sym'] == m['best_sym']), 0)
            worst_roi = next((h['roi'] for h in m['holdings'] if h['sym'] == m['worst_sym']), 0)
            
            b_icon = "🟢" if best_roi >= 0 else "🔴"
            w_icon = "🟢" if worst_roi >= 0 else "🔴"
            
            msg += f"🏆 Mã tốt nhất: {m['best_sym']} ({b_icon} {best_roi:+.1f}%) ({self.format_money(m['best_profit'])})\n"
            msg += f"📉 Mã kém nhất: {m['worst_sym']} ({w_icon} {worst_roi:+.1f}%) ({self.format_money(m['worst_profit'])})\n"
            msg += f"📊 Tỉ trọng lớn nhất: {m['largest_sym']} ({(m['max_val']/sum(h['val'] for h in m['holdings'])*100):.1f}%)\n"
        else:
            msg += f"🏆 Mã tốt nhất: -- (0 đ)\n"
            msg += f"📉 Mã kém nhất: --\n"
            msg += f"📊 Tỉ trọng lớn nhất: --\n"
        
        msg += f"────────────\n"

        for h in m['holdings']:
            icon = "🟢" if h['profit'] >= 0 else "🔴"
            msg += f"💎 **{h['sym']}**\n"
            msg += f"• SL: {h['qty']:,.0f} | Vốn TB: {h['avg']/1000:,.1f}\n" 
            msg += f"• Hiện tại: {h['cur']/1000:,.1f} | GT: {self.format_money(h['val'])}\n"
            msg += f"• Lãi: {self.format_money(h['profit'])} ({icon} {h['roi']:+.1f}%)\n"
            msg += f"───────────\n"
        
        msg += f"━━━━━━━━━━━━━━━━━━━"
        return msg

    def get_group_report(self):
        m = self._calculate_metrics()
        if not m: return "Chưa có dữ liệu Báo cáo."

        icon_roi = "🟢" if m['total_roi'] >= 0 else "🔴"

        msg = f"📑 **BÁO CÁO TÀI CHÍNH: CHỨNG KHOÁN**\n━━━━━━━━━━━━━━━━━━━\n"
        msg += f"📊 **DANH MỤC CỔ PHIẾU**\n"
        msg += f"💰 Tổng giá trị: {self.format_money(m['total_value'])}\n"
        msg += f"💵 Tổng vốn: {self.format_money(m['book_value'])}\n"
        msg += f"💸 Sức mua: {self.format_money(m['cash'])}\n"
        msg += f"📈 Lãi/Lỗ: {self.format_money(m['total_profit'])} ({icon_roi} {m['total_roi']:+.1f}%)\n"
        msg += f"⬆️ Tổng nạp ví: {self.format_money(m['total_in'])}\n"
        msg += f"⬇️ Tổng rút ví: {self.format_money(m['total_out'])}\n"

        if m['holdings']:
            best_roi = next((h['roi'] for h in m['holdings'] if h['sym'] == m['best_sym']), 0)
            worst_roi = next((h['roi'] for h in m['holdings'] if h['sym'] == m['worst_sym']), 0)
            b_icon = "🟢" if best_roi >= 0 else "🔴"
            w_icon = "🟢" if worst_roi >= 0 else "🔴"
            
            msg += f"🏆 Mã tốt nhất: {m['best_sym']} ({b_icon} {best_roi:+.1f}%)\n"
            msg += f"📉 Mã kém nhất: {m['worst_sym']} ({w_icon} {worst_roi:+.1f}%)\n"
            msg += f"📊 Tỉ trọng lớn nhất: {m['largest_sym']} ({(m['max_val']/sum(h['val'] for h in m['holdings'])*100):.1f}%)\n"
        else:
            msg += f"🏆 Mã tốt nhất: --\n"
            msg += f"📉 Mã kém nhất: --\n"
            msg += f"📊 Tỉ trọng lớn nhất: --\n"
        
        msg += f"────────────\n"
        msg += f"🔄 **HOẠT ĐỘNG GIAO DỊCH:**\n"
        msg += f"🛒 Tổng mua: {self.format_money(m['total_buy'])}\n"
        msg += f"💰 Tổng bán: {self.format_money(m['total_sell'])}\n\n"

        msg += f"🏆 **Top Đóng Góp (Lãi chốt):**\n"
        if m['top_gainers']:
            for i, (sym, val) in enumerate(m['top_gainers'][:3], 1):
                msg += f"{i}. {sym}: +{self.format_money(val)}\n"
        else:
            msg += "• Chưa có dữ liệu lãi.\n"

        msg += f"⚠️ **Top Kéo Lùi (Lỗ chốt):**\n"
        if m['top_losers']:
            for i, (sym, val) in enumerate(m['top_losers'][:3], 1):
                msg += f"{i}. {sym}: {self.format_money(val)}\n"
        else:
            msg += "• Chưa có dữ liệu lỗ.\n"

        msg += f"────────────\n"
        msg += f"📊 **CHI TIẾT DANH MỤC HIỆN TẠI:**\n"
        for h in m['holdings']:
            icon = "🟢" if h['profit'] >= 0 else "🔴"
            msg += f"• {h['sym']}: ROI {icon} {h['roi']:+.1f}% | GT: {self.format_money(h['val'])}\n"

        return msg
