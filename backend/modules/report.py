# backend/modules/report.py
import pandas as pd
import io
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency

class ReportModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def _process_data(self):
        data = self.db.get_report_raw_data()
        crypto_rate = float(data['settings'].get('crypto_rate', 25000))
        
        # 1. Tính toán Wallets
        total_assets = 0
        total_in = 0
        total_out = 0
        wallet_stats = {}
        for w in data['wallets']:
            wid = w['id']
            if wid == 'CASH':
                total_in = w['total_in'] or 0
                total_out = w['total_out'] or 0
                total_assets += w['balance'] or 0
            wallet_stats[wid] = {'balance': w['balance'] or 0, 'assets': 0, 'realized': 0, 'unrealized': 0}

        # 2. Phân tích Holdings (Lãi chưa chốt)
        symbol_stats = {}
        for h in data['holdings']:
            wid = h['wallet_id']
            sym = h['symbol']
            qty = h['quantity']
            c_price = h['current_price']
            cost = h['cost_basis_vnd']
            
            cur_val = (qty * c_price * crypto_rate) if wid == 'CRYPTO' else (qty * c_price)
            unrealized = cur_val - cost
            
            wallet_stats[wid]['assets'] += cur_val
            wallet_stats[wid]['unrealized'] += unrealized
            total_assets += cur_val
            
            if sym not in symbol_stats:
                symbol_stats[sym] = {'wallet': wid, 'total_pl': 0}
            symbol_stats[sym]['total_pl'] += unrealized

        # 3. Phân tích Transactions (Lãi đã chốt & Win Rate)
        wins = 0
        losses = 0
        total_realized = 0
        
        for t in data['transactions']:
            pl = t['realized_pl']
            if pl:
                total_realized += pl
                wallet_stats[t['wallet_id']]['realized'] += pl
                sym = t['symbol']
                if sym:
                    if sym not in symbol_stats: symbol_stats[sym] = {'wallet': t['wallet_id'], 'total_pl': 0}
                    symbol_stats[sym]['total_pl'] += pl
                
            if t['type'] == 'BAN' and pl is not None:
                if pl > 0: wins += 1
                elif pl < 0: losses += 1

        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Xếp hạng Tội đồ & Công thần
        sorted_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['total_pl'], reverse=True)
        top_winners = [s for s in sorted_symbols if s[1]['total_pl'] > 0][:2]
        top_losers = [s for s in reversed(sorted_symbols) if s[1]['total_pl'] < 0][:2]

        return {
            "total_assets": total_assets,
            "total_in": total_in,
            "total_out": total_out,
            "net_cashflow": total_in - total_out,
            "total_realized": total_realized,
            "total_unrealized": sum(w['unrealized'] for w in wallet_stats.values()),
            "total_pl": total_assets - (total_in - total_out),
            "win_rate": win_rate,
            "wins": wins,
            "losses": losses,
            "wallets": wallet_stats,
            "top_winners": top_winners,
            "top_losers": top_losers,
            "raw_data": data
        }

    def get_telegram_report(self):
        stats = self._process_data()
        
        # NAV
        pl_icon = "🟢" if stats['total_pl'] >= 0 else "🔴"
        sign = "+" if stats['total_pl'] > 0 else ""
        nav_roi = (stats['total_pl'] / stats['net_cashflow'] * 100) if stats['net_cashflow'] > 0 else 0
        
        msg = f"📊 **BÁO CÁO QUẢN TRỊ DANH MỤC**\n━━━━━━━━━━━━━━━━━━━\n"
        msg += f"1️⃣ **HIỆU QUẢ ĐẦU TƯ (NAV)**\n"
        msg += f"💰 Tổng tài sản: {format_currency(stats['total_assets'])}\n"
        msg += f"📈 Lãi/Lỗ tổng: {sign}{format_currency(stats['total_pl'])} ({pl_icon} {sign}{nav_roi:.1f}%)\n"
        msg += f"⚖️ Win Rate: {stats['win_rate']:.1f}% ({stats['wins']} Lãi / {stats['losses']} Lỗ)\n"
        msg += f"────────────\n"
        
        # Phân bổ
        msg += f"2️⃣ & 5️⃣ **PHÂN BỔ TỶ TRỌNG**\n"
        for wid in ['STOCK', 'CRYPTO']:
            w_assets = stats['wallets'][wid]['assets'] + stats['wallets'][wid]['balance']
            pct = (w_assets / stats['total_assets'] * 100) if stats['total_assets'] > 0 else 0
            w_pl = stats['wallets'][wid]['realized'] + stats['wallets'][wid]['unrealized']
            w_icon = "🟢" if w_pl >= 0 else "🔴"
            msg += f"• {wid}: {format_currency(w_assets)} ({pct:.1f}%) | Hiệu suất: {w_icon}\n"
        msg += f"────────────\n"
        
        # Dòng tiền
        msg += f"4️⃣ **LỢI NHUẬN ĐẾN TỪ ĐÂU?**\n"
        msg += f"💵 Lãi đã chốt (Tiền về ví): {format_currency(stats['total_realized'])}\n"
        msg += f"📄 Lãi trên giấy (Chưa chốt): {format_currency(stats['total_unrealized'])}\n"
        if stats['top_winners']:
            msg += f"🏆 **Top Công Thần:**\n"
            for sym, data in stats['top_winners']:
                msg += f"• {sym} ({data['wallet']}): 🟢 +{format_currency(data['total_pl'])}\n"
        msg += f"────────────\n"
        
        if stats['top_losers']:
            msg += f"3️⃣ **TÀI SẢN KÉO LÙI DANH MỤC**\n⚠️ **Top Tội Đồ:**\n"
            for sym, data in stats['top_losers']:
                msg += f"• {sym} ({data['wallet']}): 🔴 {format_currency(data['total_pl'])}\n"
        msg += f"━━━━━━━━━━━━━━━━━━━"

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📊 Tải Báo Cáo Excel Chi Tiết", callback_data="export_excel_report"))
        
        return msg, markup

    def generate_excel_bytes(self):
        stats = self._process_data()
        raw = stats['raw_data']
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet 1: Tổng quan
            overview_data = {
                "Chỉ số": ["Tổng Tài Sản", "Tổng Nạp", "Tổng Rút", "Tiền Mặt (CASH)", "Lãi/Lỗ Tổng", "Win Rate (%)"],
                "Giá trị": [stats['total_assets'], stats['total_in'], stats['total_out'], stats['wallets']['CASH']['balance'], stats['total_pl'], stats['win_rate']]
            }
            pd.DataFrame(overview_data).to_excel(writer, sheet_name="Dashboard", index=False)
            
            # Sheet 2: Danh mục
            portfolio = []
            for h in raw['holdings']:
                portfolio.append({
                    "Ví": h['wallet_id'], "Mã": h['symbol'], "Số Lượng": h['quantity'],
                    "Giá Vốn TB": h['average_price'], "Giá Hiện Tại": h['current_price'],
                    "Vốn Gốc VNĐ": h['cost_basis_vnd']
                })
            if portfolio:
                pd.DataFrame(portfolio).to_excel(writer, sheet_name="Portfolio", index=False)
            else:
                pd.DataFrame({"Thông báo": ["Chưa có tài sản"]}).to_excel(writer, sheet_name="Portfolio", index=False)
            
            # Sheet 3: Lịch sử giao dịch
            transactions = []
            for t in raw['transactions']:
                transactions.append({
                    "ID": t['id'], "Loại": t['type'], "Ví": t['wallet_id'], "Mã": t['symbol'],
                    "Số Lượng": t['quantity'], "Giá": t['price'], "Thành Tiền": t['amount'],
                    "Lãi Chốt": t['realized_pl'], "Ghi Chú": t['note']
                })
            if transactions:
                pd.DataFrame(transactions).to_excel(writer, sheet_name="Ledger", index=False)
            else:
                pd.DataFrame({"Thông báo": ["Chưa có giao dịch"]}).to_excel(writer, sheet_name="Ledger", index=False)

        output.seek(0)
        return output
