# backend/modules/report.py
import pandas as pd
import io
import re
import datetime
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter
from openpyxl.chart import PieChart, Reference
from openpyxl.drawing.image import Image as ExcelImage
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

    def _generate_nav_chart_io(self, stats, raw):
        capital_history = []
        date_history = []
        current_calc_capital = 0
        
        transactions = sorted(raw['transactions'], key=lambda x: x['id'])
        
        for t in transactions:
            if t['type'] in ['NAP', 'RUT'] and t['wallet_id'] == 'CASH':
                current_calc_capital += (t['amount'] or 0)
                capital_history.append(current_calc_capital)
                
                # Trích xuất ngày từ note (VD: [2024-01-15]), nếu không có thì lấy ngày hôm nay
                tx_date = datetime.date.today()
                if t.get('note'):
                    match = re.search(r'\[(\d{4}-\d{2}-\d{2})\]', str(t['note']))
                    if match:
                        tx_date = datetime.datetime.strptime(match.group(1), '%Y-%m-%d').date()
                date_history.append(tx_date)

        if not capital_history:
            capital_history = [stats['net_cashflow']]
            date_history = [datetime.date.today()]

        # Cân bằng mốc Neo (Để đường nạp ròng khớp với tiền thật hiện tại)
        diff = stats['net_cashflow'] - capital_history[-1]
        capital_history = [val + diff for val in capital_history]

        # Nếu chỉ có 1 điểm giao dịch, tạo thêm 1 điểm lùi lại 30 ngày để vẽ thành đường thẳng
        if len(capital_history) == 1:
            capital_history.insert(0, capital_history[0])
            date_history.insert(0, date_history[0] - datetime.timedelta(days=30))

        # Khởi tạo biểu đồ
        fig, ax = plt.subplots(figsize=(10, 5))
        
        # Vẽ đường & đổ bóng
        ax.fill_between(date_history, capital_history, color='#1f77b4', alpha=0.15)
        ax.plot(date_history, capital_history, marker='.', linestyle='-', color='#1f77b4', label='Vốn Nạp Ròng', linewidth=2)

        # Vẽ Tài sản hiện có (Chấm đỏ)
        current_assets = stats['total_assets']
        last_date = date_history[-1]

        ax.plot([last_date, last_date], [capital_history[-1], current_assets], color='#d62728', linestyle='--', linewidth=2)
        ax.plot(last_date, current_assets, marker='o', color='#d62728', markersize=8, label='Tài Sản Thực Tế (NAV)')

        # Format X-axis thành Thời gian (Tháng/Năm)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        fig.autofmt_xdate()

        plt.title('BIỂU ĐỒ BIẾN ĐỘNG VỐN & TÀI SẢN (NAV)', fontsize=13, fontweight='bold', pad=15)
        plt.ylabel('Giá trị (VNĐ)', fontsize=11)
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.legend(loc='upper left')

        def format_func(value, tick_number):
            if abs(value) >= 1_000_000_000: return f"{value / 1_000_000_000:.1f} Tỷ"
            elif abs(value) >= 1_000_000: return f"{value / 1_000_000:.0f} Tr"
            return f"{value:,.0f}"

        ax.yaxis.set_major_formatter(plt.FuncFormatter(format_func))
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120)
        plt.close()
        buf.seek(0)
        return buf

    def generate_chart_bytes(self):
        stats = self._process_data()
        raw = stats['raw_data']
        buf = self._generate_nav_chart_io(stats, raw)
        return buf.getvalue()

    def get_telegram_report(self):
        stats = self._process_data()
        
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

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📈 Xem Biểu Đồ Tăng Trưởng NAV", callback_data="view_nav_chart"),
            InlineKeyboardButton("📊 Tải Báo Cáo Excel Chi Tiết", callback_data="export_excel_report")
        )
        
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
            df_dash.to_excel(writer, sheet_name="Dashboard", index=False, startrow=0)
            
            stock_val = stats['wallets']['STOCK']['assets'] + stats['wallets']['STOCK']['balance']
            crypto_val = stats['wallets']['CRYPTO']['assets'] + stats['wallets']['CRYPTO']['balance']
            alloc_data = {"Ví": ["STOCK", "CRYPTO"], "Tài Sản": [stock_val, crypto_val]}
            df_alloc = pd.DataFrame(alloc_data)
            df_alloc.to_excel(writer, sheet_name="Dashboard", index=False, startrow=len(df_dash) + 2)

            # 2. Portfolio 
            port_cols = ["Ví", "Mã", "Số Lượng", "Giá Vốn TB", "Giá Hiện Tại", "Vốn Gốc VNĐ", "Lãi/Lỗ Tạm Tính"]
            portfolio = []
            for h in raw['holdings']:
                pl = (h['quantity'] * h['current_price'] * (float(raw['settings'].get('crypto_rate', 25000)) if h['wallet_id'] == 'CRYPTO' else 1)) - h['cost_basis_vnd']
                portfolio.append([h['wallet_id'], h['symbol'], h['quantity'], h['average_price'], h['current_price'], h['cost_basis_vnd'], pl])
            df_port = pd.DataFrame(portfolio, columns=port_cols) if portfolio else pd.DataFrame([[""]*len(port_cols)], columns=port_cols)
            df_port.to_excel(writer, sheet_name="Portfolio", index=False)

            # 3. Performance
            perf_cols = ["Mã", "Số Lần Bán", "Tổng Lãi/Lỗ Thực Tế"]
            perf_dict = {}
            for t in raw['transactions']:
                if t['type'] == 'BAN' and t['realized_pl'] is not None and t['symbol']:
                    sym = t['symbol']
                    if sym not in perf_dict:
                        perf_dict[sym] = {"Số Lần Bán": 0, "Tổng Lãi/Lỗ Thực Tế": 0}
                    perf_dict[sym]["Số Lần Bán"] += 1
                    perf_dict[sym]["Tổng Lãi/Lỗ Thực Tế"] += t['realized_pl']
            perf_list = [[k, v["Số Lần Bán"], v["Tổng Lãi/Lỗ Thực Tế"]] for k, v in perf_dict.items()]
            df_perf = pd.DataFrame(perf_list, columns=perf_cols) if perf_list else pd.DataFrame([[""]*len(perf_cols)], columns=perf_cols)
            df_perf.to_excel(writer, sheet_name="Performance", index=False)

            # 4. Ledger
            ledger_cols = ["ID", "Loại", "Ví", "Mã", "Số Lượng", "Giá", "Thành Tiền", "Lãi Chốt", "Ghi Chú"]
            transactions = []
            for t in raw['transactions']:
                transactions.append([t['id'], t['type'], t['wallet_id'], t['symbol'], t['quantity'], t['price'], t['amount'], t['realized_pl'], t['note']])
            df_ledger = pd.DataFrame(transactions, columns=ledger_cols) if transactions else pd.DataFrame([[""]*len(ledger_cols)], columns=ledger_cols)
            df_ledger.to_excel(writer, sheet_name="Ledger", index=False)

            # ==========================================
            # FORMAT EXCEL TỰ ĐỘNG BẰNG OPENPYXL
            # ==========================================
            wb = writer.book
            ws_dash = wb["Dashboard"]
            
            # QUY HOẠCH LẠI TỌA ĐỘ TRÁNH ĐÈ NHAU
            try:
                # Ảnh Line Chart chèn hẳn sang cột I (I1)
                chart_io = self._generate_nav_chart_io(stats, raw)
                img = ExcelImage(chart_io)
                ws_dash.add_image(img, "I1") 
            except: pass

            try:
                # Biểu đồ Tròn chèn vào cột D (D1)
                pie = PieChart()
                pie.title = "Phân Bổ Tỷ Trọng Vốn"
                labels = Reference(ws_dash, min_col=1, min_row=10, max_row=11)
                data = Reference(ws_dash, min_col=2, min_row=9, max_row=11)
                pie.add_data(data, titles_from_data=True)
                pie.set_categories(labels)
                ws_dash.add_chart(pie, "D1") 
            except: pass

            # Format Số & Bảng
            for sheet_name, df in [("Dashboard", df_dash), ("Portfolio", df_port), ("Performance", df_perf), ("Ledger", df_ledger)]:
                ws = wb[sheet_name]
                
                for row in ws.iter_rows(min_row=2):
                    for cell in row:
                        if isinstance(cell.value, (int, float)):
                            cell.number_format = '#,##0' 

                for i, col in enumerate(df.columns):
                    col_letter = get_column_letter(i + 1)
                    ws.column_dimensions[col_letter].width = 18 
                
                try:
                    if sheet_name != "Dashboard":
                        max_row = 2 if df.empty or str(df.iloc[0,0]) == "" else df.shape[0] + 1
                        ref = f"A1:{get_column_letter(len(df.columns))}{max_row}"
                        tab = Table(displayName=f"Tbl_{sheet_name}", ref=ref)
                        tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
                        ws.add_table(tab)
                    else:
                        tab1 = Table(displayName="Tbl_Dash", ref=f"A1:B7")
                        tab1.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
                        ws.add_table(tab1)
                        
                        tab2 = Table(displayName="Tbl_Alloc", ref=f"A9:B11")
                        tab2.tableStyleInfo = TableStyleInfo(name="TableStyleMedium10", showRowStripes=True)
                        ws.add_table(tab2)
                except:
                    pass

        return output.getvalue()
