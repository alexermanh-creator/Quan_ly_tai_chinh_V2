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
        """THUẬT TOÁN ĐỊNH DẠNG TÀI CHÍNH THÔNG MINH (Tỷ, Tr, đ)"""
        if value == 0: return "0đ"
        sign = "+" if is_pnl and value > 0 else ""
        abs_val = abs(value)
        
        if abs_val >= 1_000_000_000:
            formatted = f"{abs_val / 1_000_000_000:.2f}".rstrip('0').rstrip('.')
            formatted = formatted.replace('.', ',') + " Tỷ"
        elif abs_val >= 1_000_000:
            formatted = f"{abs_val / 1_000_000:.2f}".rstrip('0').rstrip('.')
            formatted = formatted.replace('.', ',') + " Tr"
        else:
            formatted = f"{abs_val:,.0f}".replace(',', '.')
            
        prefix = "-" if value < 0 else sign
        return f"{prefix}{formatted}đ"

    def create_progress_bar(self, percentage, color_emoji):
        if percentage <= 0: return f"[{'⚪' * 10}]"
        filled = round(percentage / 10)
        if filled == 0 and percentage > 0: filled = 1
        filled = min(10, filled)
        empty = 10 - filled
        return f"[{color_emoji * filled}{'⚪' * empty}]"

    def calculate_portfolio(self):
        """Cỗ máy tính toán lõi trả về (data_summary, all_transactions)"""
        # Sử dụng đúng hàm bọc thép từ Repository (Static Method)
        transactions = Repository.get_all_transactions_for_report(self.user_id)
        current_prices = Repository.get_current_prices()

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
        try:
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

            return f"""📊 <b>BÁO CÁO TÀI CHÍNH TỔNG QUAN</b>\n📅 {now}\n━━━━━━━━━━━━━━━━━━━\n💰 <b>TỔNG TÀI SẢN: {self.format_currency(d['net_worth'])}</b>\n💵 Tiền mặt: {self.format_currency(d['cash_available'])}\n📈 Đang đầu tư: {self.format_currency(d['total_market_value'])}\n\n🥧 <b>PHÂN BỔ DANH MỤC:</b>\n• 📊 Stock ({pct_stock:.1f}%) {self.create_progress_bar(pct_stock, '🔵')}\n• 🪙 Crypto ({pct_crypto:.1f}%) {self.create_progress_bar(pct_crypto, '🟡')}\n• 🥇 Khác ({pct_other:.1f}%) {self.create_progress_bar(pct_other, '🟢')}\n\n🚀 <b>HIỆU SUẤT (PERFORMANCE):</b>\n• 💼 Vốn ròng: {self.format_currency(d['net_invested'])}\n• 📈 Tổng Lãi/Lỗ: <b>{self.format_currency(d['total_pnl'], True)}</b>\n• 🎯 ROI: <b>{d['roi']:.1f}%</b>\n\n🏆 Top Lãi: {win_str}\n⚠️ Top Lỗ: {lose_str}\n━━━━━━━━━━━━━━━━━━━"""
        except Exception as e:
            return f"❌ Lỗi báo cáo tổng quan: {str(e)}"

    def get_category_report(self, asset_type, start_date=None, end_date=None, label_time="Toàn thời gian"):
        try:
            d, all_transactions = self.calculate_portfolio()
            period_txs = [t for t in all_transactions if t['asset_type'] == asset_type]
            if start_date:
                period_txs = [t for t in period_txs if t['date'] >= start_date]
            if end_date:
                period_txs = [t for t in period_txs if t['date'] <= end_date + " 23:59:59"]

            c_in = sum(t['total_value'] for t in period_txs if t['type'] in ['IN', 'DEPOSIT'])
            c_out = sum(t['total_value'] for t in period_txs if t['type'] in ['OUT', 'WITHDRAW'])
            realized_only = sum(t.get('pnl_generated', 0) for t in period_txs if t['type'] in ['SELL', 'CASH_DIVIDEND'])

            name = "CHỨNG KHOÁN" if asset_type == 'STOCK' else "CRYPTO" if asset_type == 'CRYPTO' else "TÀI SẢN KHÁC"
            return f"""📊 <b>BÁO CÁO {name} ({label_time})</b>\n━━━━━━━━━━━━━━━━━━━\n🌊 Dòng tiền ròng: {self.format_currency(c_in - c_out, True)}\n📈 Lãi/Lỗ đã chốt: <b>{self.format_currency(realized_only, True)}</b>\n━━━━━━━━━━━━━━━━━━━"""
        except Exception as e:
            return f"❌ Lỗi báo cáo danh mục: {str(e)}"

    def get_ticker_detail_report(self, ticker):
        try:
            d, _ = self.calculate_portfolio()
            ticker = ticker.upper()
            if ticker not in d['tickers']:
                return f"❌ Không tìm thấy dữ liệu cho mã <b>{ticker}</b>."
            t = d['tickers'][ticker]
            unrealized_pct = (t['unrealized_pnl'] / (t['qty'] * t['avg_cost']) * 100) if t['qty'] > 0 and t['avg_cost'] > 0 else 0
            return f"""🔎 <b>CHI TIẾT MÃ: {ticker}</b>\n━━━━━━━━━━━━━━━━━━━\n📦 Đang giữ: {t['qty']:,.0f}\n💰 Vốn TB: {t['avg_cost']:,.0f}đ\n📈 Lãi chưa chốt: <b>{self.format_currency(t['unrealized_pnl'], True)} ({unrealized_pct:.1f}%)</b>\n🏆 Tổng lợi nhuận: {self.format_currency(t['total_pnl'], True)}\n━━━━━━━━━━━━━━━━━━━"""
        except Exception as e:
            return f"❌ Lỗi báo cáo chi tiết: {str(e)}"

    def export_excel_report(self):
        """Vui lòng sử dụng tính năng 'Xuất Excel' từ Menu chính."""
        return None, "Sử dụng Menu chính."
