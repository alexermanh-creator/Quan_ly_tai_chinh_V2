# backend/modules/report.py
import io
from datetime import datetime
from backend.interface import BaseModule
from backend.database.repository import Repository

try:
    import pandas as pd
except ImportError:
    pd = None

class ReportModule(BaseModule):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.repo = Repository()

    def format_currency(self, value, is_pnl=False):
        if value == 0: return "0đ"
        sign = "+" if is_pnl and value > 0 else ""
        return f"{sign}{value:,.0f}đ".replace(',', '.')

    def create_progress_bar(self, percentage, color_emoji):
        if percentage <= 0: return f"[{'⚪' * 10}]"
        filled = round(percentage / 10)
        if filled == 0 and percentage > 0: filled = 1
        filled = min(10, filled)
        empty = 10 - filled
        return f"[{color_emoji * filled}{'⚪' * empty}]"

    def calculate_portfolio(self):
        transactions = self.repo.get_all_transactions_for_report(self.user_id)
        current_prices = self.repo.get_current_prices()

        data = {
            'cash_available': 0, 'total_in': 0, 'total_out': 0,
            'total_buy': 0, 'total_sell': 0,
            'assets': {'STOCK': 0, 'CRYPTO': 0, 'OTHER': 0},
            'cat_in': {'STOCK': 0, 'CRYPTO': 0, 'OTHER': 0},
            'cat_out': {'STOCK': 0, 'CRYPTO': 0, 'OTHER': 0},
            'tickers': {}
        }

        for trx in transactions:
            t = trx['ticker']
            a_type = trx['asset_type'] if trx['asset_type'] in ['STOCK', 'CRYPTO'] else 'OTHER'
            
            if t not in data['tickers']:
                data['tickers'][t] = {
                    'type': a_type, 'qty': 0, 'avg_cost': 0, 
                    'realized_pnl': 0, 'total_buy_vol': 0, 'total_sell_vol': 0, 
                    'dividends': 0
                }
            
            tkr = data['tickers'][t]

            if trx['type'] in ['IN', 'DEPOSIT']:
                data['total_in'] += trx['total_value']
                data['cash_available'] += trx['total_value']
                data['cat_in'][a_type] += trx['total_value']
            elif trx['type'] in ['OUT', 'WITHDRAW']:
                data['total_out'] += trx['total_value']
                data['cash_available'] -= trx['total_value']
                data['cat_out'][a_type] += trx['total_value']
            elif trx['type'] == 'BUY':
                data['cash_available'] -= trx['total_value']
                data['total_buy'] += trx['total_value']
                tkr['total_buy_vol'] += trx['qty']
                
                new_qty = tkr['qty'] + trx['qty']
                if new_qty > 0:
                    tkr['avg_cost'] = ((tkr['qty'] * tkr['avg_cost']) + trx['total_value']) / new_qty
                tkr['qty'] = new_qty
            elif trx['type'] == 'SELL':
                data['cash_available'] += trx['total_value']
                data['total_sell'] += trx['total_value']
                tkr['total_sell_vol'] += trx['qty']
                
                realized_profit = trx['total_value'] - (trx['qty'] * tkr['avg_cost'])
                trx['pnl_generated'] = realized_profit 
                tkr['realized_pnl'] += realized_profit
                
                tkr['qty'] -= trx['qty']
                if tkr['qty'] <= 0:
                    tkr['qty'] = 0
                    tkr['avg_cost'] = 0
            elif trx['type'] == 'CASH_DIVIDEND':
                data['cash_available'] += trx['total_value']
                tkr['dividends'] += trx['total_value']
                trx['pnl_generated'] = trx['total_value']

        total_market_value = 0
        total_realized = 0
        total_unrealized = 0

        for t, tkr in data['tickers'].items():
            curr_price = current_prices.get(t, tkr['avg_cost']) 
            tkr['current_price'] = curr_price
            
            market_val = tkr['qty'] * curr_price
            tkr['market_value'] = market_val
            tkr['unrealized_pnl'] = market_val - (tkr['qty'] * tkr['avg_cost'])
            tkr['total_pnl'] = tkr['realized_pnl'] + tkr['unrealized_pnl'] + tkr['dividends']
            
            data['assets'][tkr['type']] += market_val
            total_market_value += market_val
            total_realized += tkr['realized_pnl']
            total_unrealized += tkr['unrealized_pnl']

        data['total_market_value'] = total_market_value
        data['net_worth'] = data['cash_available'] + total_market_value
        data['net_invested'] = data['total_in'] - data['total_out']
        data['total_pnl'] = total_realized + total_unrealized + sum(t['dividends'] for t in data['tickers'].values())
        data['roi'] = (data['total_pnl'] / data['net_invested']) * 100 if data['net_invested'] > 0 else 0

        return data, transactions

    def get_overview_report(self):
        d, _ = self.calculate_portfolio()
        now = datetime.now().strftime("%d/%m/%Y | %H:%M")
        
        nw = d['net_worth'] if d['net_worth'] > 0 else 1
        pct_stock = (d['assets']['STOCK'] / nw) * 100
        pct_crypto = (d['assets']['CRYPTO'] / nw) * 100
        pct_other = (d['assets']['OTHER'] / nw) * 100

        sorted_tickers = sorted(d['tickers'].items(), key=lambda x: x[1]['total_pnl'], reverse=True)
        top_winners = [f"{k} (+{self.format_currency(v['total_pnl'])})" for k, v in sorted_tickers if v['total_pnl'] > 0][:2]
        top_losers = [f"{k} ({self.format_currency(v['total_pnl'])})" for k, v in sorted_tickers if v['total_pnl'] < 0][::-1][:2]

        win_str = " | ".join(top_winners) if top_winners else "Chưa có"
        lose_str = " | ".join(top_losers) if top_losers else "Chưa có"

        html = f"""📊 <b>BÁO CÁO TÀI CHÍNH TỔNG QUAN (Toàn thời gian)</b>
📅 {now}
━━━━━━━━━━━━━━━━━━━ 
💰 <b>TỔNG TÀI SẢN:</b>       <b>{self.format_currency(d['net_worth'])}</b> 
💵 Tiền mặt khả dụng:    {self.format_currency(d['cash_available'])} 
📈 Đang đầu tư:        {self.format_currency(d['total_market_value'])}

🥧 <b>PHÂN BỔ DANH MỤC:</b>
• 📊 Stock ({pct_stock:.1f}%) 
  {self.create_progress_bar(pct_stock, '🔵')}  {self.format_currency(d['assets']['STOCK'])} 
• 🪙 Crypto ({pct_crypto:.1f}%) 
  {self.create_progress_bar(pct_crypto, '🟡')}  {self.format_currency(d['assets']['CRYPTO'])} 
• 🥇 Tài sản khác ({pct_other:.1f}%) 
  {self.create_progress_bar(pct_other, '🟢')}  {self.format_currency(d['assets']['OTHER'])}

🚀 <b>HIỆU SUẤT (PERFORMANCE):</b> 
• 💼 Vốn ròng thực tế: {self.format_currency(d['net_invested'])} 
• 📈 Tổng Lãi/Lỗ:       <b>{self.format_currency(d['total_pnl'], True)}</b> 
• 🎯 ROI Toàn hệ thống:         <b>{'+' if d['roi']>0 else ''}{d['roi']:.1f}%</b>

🏆 Top Lãi: {win_str} 
⚠️ Top Lỗ:  {lose_str}

💸 <b>DÒNG TIỀN (ALL-TIME):</b> 
⬆️ Tổng nạp:           {self.format_currency(d['total_in'])} 
⬇️ Tổng rút:             {self.format_currency(d['total_out'])} 
━━━━━━━━━━━━━━━━━━━"""
        return html

    def get_category_report(self, asset_type, start_date=None, end_date=None, label_time="Toàn thời gian"):
        """TẦNG 2: Báo cáo theo Danh mục TÍCH HỢP BỘ LỌC THỜI GIAN (Có end_date)"""
        d, all_transactions = self.calculate_portfolio()
        
        period_txs = [t for t in all_transactions if t['asset_type'] == asset_type]
        if start_date:
            period_txs = [t for t in period_txs if t['date'] >= start_date]
        if end_date:
            period_txs = [t for t in period_txs if t['date'] <= end_date + " 23:59:59"]

        c_in = sum(t['total_value'] for t in period_txs if t['type'] in ['IN', 'DEPOSIT'])
        c_out = sum(t['total_value'] for t in period_txs if t['type'] in ['OUT', 'WITHDRAW'])
        cat_total_buy = sum(t['total_value'] for t in period_txs if t['type'] == 'BUY')
        cat_total_sell = sum(t['total_value'] for t in period_txs if t['type'] == 'SELL')
        realized_only = sum(t.get('pnl_generated', 0) for t in period_txs if t['type'] in ['SELL', 'CASH_DIVIDEND'])

        ticker_period_pnl = {}
        for t in period_txs:
            if t['type'] in ['SELL', 'CASH_DIVIDEND']:
                ticker_period_pnl[t['ticker']] = ticker_period_pnl.get(t['ticker'], 0) + t.get('pnl_generated', 0)
                
        sorted_period_tickers = sorted(ticker_period_pnl.items(), key=lambda x: x[1], reverse=True)
        win_list = [f"   {i+1}. {k}: {self.format_currency(v, True)}" for i, (k, v) in enumerate(sorted_period_tickers) if v > 0][:3]
        lose_list = [f"   {i+1}. {k}: {self.format_currency(v, True)}" for i, (k, v) in enumerate(sorted_period_tickers[::-1]) if v < 0][:3]

        win_str = "\n".join(win_list) if win_list else "   Không có dữ liệu chốt lời"
        lose_str = "\n".join(lose_list) if lose_list else "   Không có dữ liệu cắt lỗ"

        name = "CHỨNG KHOÁN" if asset_type == 'STOCK' else "CRYPTO" if asset_type == 'CRYPTO' else "TÀI SẢN KHÁC"

        html = f"""📊 <b>BÁO CÁO {name} ({label_time})</b> 
━━━━━━━━━━━━━━━━━━━ 
💸 <b>DÒNG TIỀN TRONG KỲ:</b> 
⬆️ Thực nạp:            {self.format_currency(c_in, True)} 
⬇️ Thực rút:             {self.format_currency(-c_out, True)} 
🌊 Dòng tiền ròng:      <b>{self.format_currency(c_in - c_out, True)}</b>

🔄 <b>HOẠT ĐỘNG GIAO DỊCH:</b> 
🛒 Tổng mua:             {self.format_currency(cat_total_buy)} 
💰 Tổng bán:             {self.format_currency(cat_total_sell)}

🚀 <b>HIỆU SUẤT TRONG KỲ (P&L):</b> 
📈 Lãi/Lỗ (Đã chốt):     <b>{self.format_currency(realized_only, True)}</b>

🏆 <b>Top Đóng Góp (Trong kỳ):</b> 
{win_str} 
⚠️ <b>Top Kéo Lùi (Trong kỳ):</b> 
{lose_str} 
━━━━━━━━━━━━━━━━━━━"""
        return html

    def get_ticker_detail_report(self, ticker):
        d, _ = self.calculate_portfolio()
        ticker = ticker.upper()
        
        if ticker not in d['tickers']:
            return f"❌ Không tìm thấy dữ liệu giao dịch cho mã <b>{ticker}</b>."
            
        t = d['tickers'][ticker]
        unrealized_pct = (t['unrealized_pnl'] / (t['qty'] * t['avg_cost']) * 100) if t['qty'] > 0 and t['avg_cost'] > 0 else 0

        html = f"""🔎 <b>PHÂN TÍCH CHI TIẾT MÃ: {ticker}</b> 
━━━━━━━━━━━━━━━━━━━ 
📦 <b>Trạng thái hiện tại:</b> 
• Đang nắm giữ: {t['qty']:,.0f} 
• Giá vốn TB: {t['avg_cost']:,.0f}đ 
• Giá hiện tại: {t['current_price']:,.0f}đ 
• Lãi/Lỗ chưa chốt: <b>{self.format_currency(t['unrealized_pnl'], True)} ({'+' if unrealized_pct>0 else ''}{unrealized_pct:.1f}%)</b>

📜 <b>Thống kê Lịch sử (All-time):</b> 
• Tổng KL đã Mua: {t['total_buy_vol']:,.0f} 
• Tổng KL đã Bán: {t['total_sell_vol']:,.0f} 
• Lãi/Lỗ đã chốt (Realized): {self.format_currency(t['realized_pnl'], True)} 
• Cổ tức/Airdrop: {self.format_currency(t['dividends'])}

💰 <b>TỔNG LỢI NHUẬN TỪ {ticker}: {self.format_currency(t['total_pnl'], True)}</b> 
━━━━━━━━━━━━━━━━━━━"""
        return html
