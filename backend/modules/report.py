# backend/modules/report.py
import pandas as pd
import io
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter
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
            if pl is not None:
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
        
        # NAV & Goal
        pl_icon = "🟢" if stats['total_pl'] >= 0 else "🔴"
        sign = "+" if stats['total_pl'] > 0 else ""
        nav_roi = (stats['total_pl'] / stats['net_cashflow'] * 100) if stats['net_cashflow'] > 0 else 0
        
        goal_text = stats['raw_data']['settings'].get('goal', 'lai 10%')
        goal_pct = 10
        try:
            m = re.search(r'\d+', goal_text)
            if m: goal_pct = float(m.group())
        except: pass
        goal_progress = (nav_roi / goal_pct * 100) if goal_pct > 0 else 0
        
        msg = f"📊 **BÁO CÁO QUẢN TRỊ DANH MỤC**\n━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🎯 **HIỆU QUẢ ĐẦU TƯ (NAV)**\n"
        msg += f"💰 Tổng tài sản: {format_currency(stats['total_assets'])}\n"
        msg += f"📈 Lãi/Lỗ tổng: {sign}{format_currency(stats['total_pl'])} ({pl_icon} {sign}{nav_roi:.1f}%)\n"
        if stats['total_assets'] > 0:
            msg += f"🏁 Tiến độ mục tiêu: Đạt {goal_progress:.1f}% ({goal_text})\n"
        msg += f"⚖️ Win Rate: {stats['win_rate']:.1f}% ({stats['wins']} Lãi / {stats['losses']} Lỗ)\n"
        msg += f"────────────\n"
        
        msg += f"⚖️ **PHÂN BỔ TỶ TRỌNG & HIỆU SUẤT**\n"
        for wid in ['STOCK', 'CRYPTO']:
            w_assets = stats['wallets'][wid]['assets'] + stats['wallets'][wid]['balance']
            pct = (w_assets / stats['total_assets'] * 100) if stats['total_assets'] > 0 else 0
            w_pl = stats['wallets'][wid]['realized'] + stats['wallets'][wid]['unrealized']
            w_icon = "🟢" if w_pl >= 0 else "🔴"
            msg += f"• {wid}: {format_currency(w_assets)} ({pct:.1f}%) | Hiệu suất: {w_icon}\n"
        msg += f"────────────\n"
        
        msg += f"🔍 **LỢI NHUẬN ĐẾN TỪ ĐÂU?**\n"
        msg += f"💵 Lãi đã chốt (Tiền về ví): {format_currency(stats['total_realized'])}\n"
        msg += f"📄 Lãi trên giấy (Chưa chốt): {format_currency(stats['total_unrealized'])}\n"
        if stats['top_winners']:
            msg += f"🏆 **Top Công Thần:**\n"
            for sym, data in stats['top_winners']:
                msg += f"• {sym} ({data['wallet']}): 🟢 +{format_currency(data['total_pl'])}\n"
        msg += f"────────────\n"
        
        if stats['top_losers']:
            msg += f"⚠️ **TÀI SẢN KÉO LÙI DANH MỤC**\n"
            for sym, data in stats['top_losers']:
                msg += f"• {sym} ({data['wallet']}): 🔴 {format_currency(data['total_pl'])}\n"
            msg += f"────────────\n"
            
        msg += f"━━━━━━━━━━━━━━━━━━━"

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📊 Tải Báo Cáo Excel Chi Tiết", callback_data="export_excel_report"))
        
        return msg, markup

    def generate_excel_bytes(self):
        stats = self._process_data()
        raw = stats['raw_data']
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 1. Dashboard
            overview_data = {
                "Chỉ Số": ["Tổng Tài Sản", "Tổng Nạp", "Tổng Rút", "Tiền Mặt (CASH)", "Lãi/Lỗ Tổng", "Win Rate (%)"],
                "Giá Trị": [stats['total_assets'], stats['total_in'], stats['total_out'], stats['wallets']['CASH']['balance'], stats['total_pl'], stats['win_rate']]
            }
            df_dash = pd.DataFrame(overview_data)
            df_dash.to_excel(writer, sheet_name="Dashboard", index=False)
            
            # 2. Portfolio
            portfolio = []
            for h in raw['holdings']:
                portfolio.append({
                    "Ví": h['wallet_id'], "Mã": h['symbol'], "Số Lượng": h['quantity'],
                    "Giá Vốn TB": h['average_price'], "Giá Hiện Tại": h['current_price'],
                    "Vốn Gốc VNĐ": h['cost_basis_vnd']
                })
            df_port = pd.DataFrame(portfolio) if portfolio else pd.DataFrame({"Mã": ["Chưa có dữ liệu"]})
            df_port.to_excel(writer, sheet_name="Portfolio", index=False)

            # 3. Performance
            perf_dict = {}
            for t in raw['transactions']:
                if t['type'] == 'BAN' and t['realized_pl'] is not None and t['symbol']:
                    sym = t['symbol']
                    if sym not in perf_dict:
                        perf_dict[sym] = {"Số Lần Bán": 0, "Tổng Lãi/Lỗ Thực Tế": 0}
                    perf_dict[sym]["Số Lần Bán"] += 1
                    perf_dict[sym]["Tổng Lãi/Lỗ Thực Tế"] += t['realized_pl']
            
            perf_list = [{"Mã": k, "Số Lần Bán": v["Số Lần Bán"], "Tổng Lãi/Lỗ Thực Tế": v["Tổng Lãi/Lỗ Thực Tế"]} for k, v in perf_dict.items()]
            df_perf = pd.DataFrame(perf_list) if perf_list else pd.DataFrame({"Mã": ["Chưa có dữ liệu"]})
            df_perf.to_excel(writer, sheet_name="Performance", index=False)

            # 4. Ledger
            transactions = []
            for t in raw['transactions']:
                transactions.append({
                    "ID": t['id'], "Loại": t['type'], "Ví": t['wallet_id'], "Mã": t['symbol'],
                    "Số Lượng": t['quantity'], "Giá": t['price'], "Thành Tiền": t['amount'],
                    "Lãi Chốt": t['realized_pl'], "Ghi Chú": t['note']
                })
            df_ledger = pd.DataFrame(transactions) if transactions else pd.DataFrame({"ID": ["Chưa có dữ liệu"]})
            df_ledger.to_excel(writer, sheet_name="Ledger", index=False)

            # --- BỌC LỚP CHỐNG LỖI KHI VẼ BẢNG ---
            try:
                wb = writer.book
                for sheet_name, df in [("Dashboard", df_dash), ("Portfolio", df_port), ("Performance", df_perf), ("Ledger", df_ledger)]:
                    ws = wb[sheet_name]
                    
                    # Căn chỉnh độ rộng
                    for i, col in enumerate(df.columns):
                        col_letter = get_column_letter(i + 1)
                        max_len = max(df[col].astype(str).map(len).max() if not df.empty else 0, len(str(col))) + 4
                        ws.column_dimensions[col_letter].width = min(max_len, 40) # Giới hạn không rộng quá 40
                    
                    # Thêm Table nếu có dữ liệu
                    if not df.empty and df.shape[0] > 0 and len(df.columns) > 1:
                        if "Chưa có" not in str(df.iloc[0, 0] if not df.empty else ""):
                            max_row, max_col = df.shape
                            ref = f"A1:{get_column_letter(max_col)}{max_row + 1}"
                            tab = Table(displayName=f"Tbl_{sheet_name}", ref=ref)
                            style = TableStyleInfo(name="TableStyleMedium9", showFirstColumn=False,
                                                   showLastColumn=False, showRowStripes=True, showColumnStripes=True)
                            tab.tableStyleInfo = style
                            ws.add_table(tab)
            except Exception as e:
                pass # Nếu lỗi format thì vẫn trả về file Excel trơn, không sập hệ thống

        return output.getvalue() # Trả về chuẩn bytes thay vì object
