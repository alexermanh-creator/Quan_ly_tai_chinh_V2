# backend/modules/report.py
import pandas as pd
import io
import re
import datetime
import numpy as np
from scipy.interpolate import make_interp_spline
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter
from openpyxl.chart import PieChart, Reference
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency

class ReportModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def _process_data(self):
        data = self.db.get_report_raw_data()
        crypto_rate = float(data['settings'].get('crypto_rate', 25000))
        
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
            wallet_stats[wid] = {'balance': w['balance'] or 0, 'assets': 0, 'realized': 0, 'unrealized': 0, 'in': w['total_in'] or 0, 'out': w['total_out'] or 0}

        symbol_details = []
        for h in data['holdings']:
            wid = h['wallet_id']
            sym = h['symbol']
            qty = h['quantity']
            c_price = h['current_price']
            cost = h['cost_basis_vnd']
            
            cur_val = (qty * c_price * crypto_rate) if wid == 'CRYPTO' else (qty * c_price)
            unrealized = cur_val - cost
            roi = (unrealized / cost * 100) if cost > 0 else 0
            
            wallet_stats[wid]['assets'] += cur_val
            wallet_stats[wid]['unrealized'] += unrealized
            total_assets += cur_val
            
            symbol_details.append({
                "wid": wid, "sym": sym, "val": cur_val, "roi": roi, "cost": cost
            })

        wins = 0
        losses = 0
        total_realized = 0
        for t in data['transactions']:
            pl = t['realized_pl']
            if pl is not None:
                total_realized += pl
                wallet_stats[t['wallet_id']]['realized'] += pl
            if t['type'] == 'BAN' and pl is not None:
                if pl > 0: wins += 1
                elif pl < 0: losses += 1

        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Max Drawdown Logic
        current_cap = 0
        current_realized_pl = 0
        peak_nav_proxy = 0
        transactions = sorted(data['transactions'], key=lambda x: x['id'])
        for t in transactions:
            if t['type'] in ['NAP', 'RUT'] and t['wallet_id'] == 'CASH':
                current_cap += (t['amount'] or 0)
            if t['realized_pl'] is not None:
                current_realized_pl += t['realized_pl']
            nav_proxy = current_cap + current_realized_pl
            if nav_proxy > peak_nav_proxy: peak_nav_proxy = nav_proxy
        
        max_drawdown = ((peak_nav_proxy - total_assets) / peak_nav_proxy * 100) if peak_nav_proxy > total_assets else 0

        return {
            "total_assets": total_assets,
            "total_in": total_in,
            "total_out": total_out,
            "net_cashflow": total_in - total_out,
            "total_realized": total_realized,
            "total_pl": total_assets - (total_in - total_out),
            "win_rate": win_rate,
            "max_drawdown": max_drawdown,
            "wallets": wallet_stats,
            "symbols": symbol_details,
            "raw_data": data
        }

    def _generate_nav_chart_io(self, stats, raw):
        capital_history = []
        date_history = []
        current_calc_capital = 0
        transactions = sorted(raw['transactions'], key=lambda x: x['id'])
        for t in transactions:
            if t['type'] in ['NAP', 'RUT'] and t['wallet_id'] == 'CASH':
                current_calc_capital += (t['amount'] or 0)
                capital_history.append(current_calc_capital)
                tx_date = datetime.date.today()
                if t.get('note'):
                    match = re.search(r'\[(\d{4}-\d{2}-\d{2})\]', str(t['note']))
                    if match: tx_date = datetime.datetime.strptime(match.group(1), '%Y-%m-%d').date()
                date_history.append(tx_date)
        if not capital_history:
            capital_history = [stats['net_cashflow'], stats['net_cashflow']]
            date_history = [datetime.date.today() - datetime.timedelta(days=30), datetime.date.today()]
        diff = stats['net_cashflow'] - capital_history[-1]
        capital_history = [val + diff for val in capital_history]
        daily_data = {d: c for d, c in zip(date_history, capital_history)}
        unique_dates = list(daily_data.keys()); unique_caps = list(daily_data.values())
        fig, ax = plt.subplots(figsize=(10, 5))
        if len(unique_dates) >= 4:
            x_num = mdates.date2num(unique_dates); x_smooth = np.linspace(x_num.min(), x_num.max(), 300)
            spl = make_interp_spline(x_num, unique_caps, k=3)
            y_smooth = np.clip(spl(x_smooth), 0, None)
            ax.fill_between(x_smooth, y_smooth, color='#1f77b4', alpha=0.15)
            ax.plot(x_smooth, y_smooth, color='#1f77b4', linewidth=2.5)
        else:
            ax.plot(unique_dates, unique_caps, marker='o', color='#1f77b4', linewidth=2.5)
        ax.plot(unique_dates[-1], stats['total_assets'], marker='o', color='#d62728', markersize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        plt.title('BIỂU ĐỒ NAV', fontsize=13, fontweight='bold')
        plt.grid(True, linestyle='--', alpha=0.6)
        buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=120); plt.close(); buf.seek(0)
        return buf

    def generate_excel_bytes(self):
        stats = self._process_data()
        raw = stats['raw_data']
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Dashboard
            df_dash = pd.DataFrame({"Chỉ Số": ["Tổng Tài Sản", "Tổng Nạp", "Tổng Rút", "Lãi/Lỗ Tổng", "Win Rate (%)"], 
                                    "Giá Trị": [stats['total_assets'], stats['total_in'], stats['total_out'], stats['total_pl'], stats['win_rate']]})
            df_dash.to_excel(writer, sheet_name="Dashboard", index=False)
            
            # Lấy data chung cho các sheet
            ledger_cols = ["ID", "Loại", "Ví", "Mã", "Số Lượng", "Giá", "Thành Tiền", "Lãi Chốt", "Ghi Chú"]
            txs = [[t['id'], t['type'], t['wallet_id'], t['symbol'], t['quantity'], t['price'], t['amount'], t['realized_pl'], t['note']] for t in raw['transactions']]
            df_ledger = pd.DataFrame(txs, columns=ledger_cols)

            # Xuất các sheet với Summary rỗng ở trên (Dòng 1-15 dành cho Summary)
            for name, wid in [("LS Nạp Rút", "CASH"), ("LS Chứng Khoán", "STOCK"), ("LS Crypto", "CRYPTO")]:
                df_sub = df_ledger[df_ledger['Ví'] == wid] if wid != "CASH" else df_ledger[df_ledger['Loại'].isin(['NAP','RUT'])]
                df_sub.to_excel(writer, sheet_name=name, index=False, startrow=16)

            # Các sheet khác
            pd.DataFrame([[h['wallet_id'], h['symbol'], h['quantity'], h['average_price'], h['current_price'], h['cost_basis_vnd']] for h in raw['holdings']], 
                         columns=["Ví", "Mã", "SL", "Giá Vốn", "Giá HT", "Vốn Gốc"]).to_excel(writer, sheet_name="Portfolio", index=False)

        # Hậu xử lý Openpyxl để chèn text Báo cáo
        wb = writer.book
        for name in ["LS Chứng Khoán", "LS Crypto", "LS Nạp Rút"]:
            ws = wb[name]
            w_key = "STOCK" if "Chứng Khoán" in name else ("CRYPTO" if "Crypto" in name else "CASH")
            w_data = stats['wallets'].get(w_key, {})
            
            # Fill thông tin Summary vào đầu sheet
            title = f"📑 BÁO CÁO TÀI CHÍNH: {name.split()[-1].upper()}"
            ws['A1'] = title; ws['A1'].font = Font(bold=True, size=14)
            
            summary_lines = []
            if w_key != "CASH":
                syms = [s for s in stats['symbols'] if s['wid'] == w_key]
                best = max(syms, key=lambda x: x['roi']) if syms else {"sym": "N/A", "roi": 0}
                worst = min(syms, key=lambda x: x['roi']) if syms else {"sym": "N/A", "roi": 0}
                total_val = w_data['assets'] + w_data['balance']
                pl = w_data['realized'] + w_data['unrealized']
                
                summary_lines = [
                    f"💰 Tổng giá trị: {format_currency(total_val)}",
                    f"💵 Tổng vốn gốc: {format_currency(w_data['in'] - w_data['out'])}",
                    f"📈 Lãi/Lỗ: {format_currency(pl)} ({pl/(w_data['in']-w_data['out'])*100:.1f}%" if (w_data['in']-w_data['out'])>0 else "0.0%)",
                    f"⬆️ Tổng nạp ví: {format_currency(w_data['in'])} | ⬇️ Tổng rút ví: {format_currency(w_data['out'])}",
                    f"🏆 Mã tốt nhất: {best['sym']} ({best['roi']:.1f}%) | 📉 Mã kém nhất: {worst['sym']} ({worst['roi']:.1f}%)"
                ]
            else:
                summary_lines = [
                    f"💰 Tổng tài sản HT: {format_currency(stats['total_assets'])}",
                    f"📤 Tổng nạp HT: {format_currency(stats['total_in'])}",
                    f"📥 Tổng rút HT: {format_currency(stats['total_out'])}",
                    f"📈 Lãi/Lỗ tổng: {format_currency(stats['total_pl'])}",
                    f"📉 Max Drawdown: -{stats['max_drawdown']:.1f}%"
                ]

            for i, line in enumerate(summary_lines):
                ws[f'A{i+3}'] = line
                ws[f'A{i+3}'].font = Font(size=11)

            # Kẻ bảng dữ liệu phía dưới
            last_row = ws.max_row
            if last_row > 17:
                tab = Table(displayName=f"Tbl_{w_key}", ref=f"A17:{get_column_letter(ws.max_column)}{last_row}")
                tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
                ws.add_table(tab)
            
            # Format tiền
            for row in ws.iter_rows(min_row=18, max_row=last_row):
                for cell in row:
                    if isinstance(cell.value, (int, float)): cell.number_format = '#,##0'

        return output.getvalue()

    def get_telegram_report(self):
        stats = self._process_data()
        msg = f"📊 **BÁO CÁO TỔNG QUAN V3.4**\n💰 Tài sản: {format_currency(stats['total_assets'])}\n📈 PnL: {format_currency(stats['total_pl'])}\n win rate: {stats['win_rate']:.1f}%"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📈 Biểu đồ NAV", callback_data="view_nav_chart"))
        markup.add(InlineKeyboardButton("📊 Xuất Excel Full", callback_data="export_excel_report"))
        return msg, markup
