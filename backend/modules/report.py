# backend/modules/report.py
from datetime import datetime
from backend.interface import BaseModule
from backend.database.repository import repo
from backend.database.db_manager import db

class ReportModule(BaseModule):
    def format_currency(self, value, is_pnl=False):
        """Giữ nguyên thuật toán định dạng thông minh của CEO"""
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
        filled = max(0, min(10, filled))
        empty = 10 - filled
        return f"[{color_emoji * filled}{'⚪' * empty}]"

    def calculate_portfolio(self):
        """Cỗ máy tính toán lõi - Hợp nhất để lấy giá từ manual_prices"""
        transactions = repo.get_all_transactions_for_report(self.user_id)
        current_prices = repo.get_current_prices()

        data = {
            'cash_available': 0, 'total_in': 0, 'total_out': 0,
            'total_buy': 0, 'total_sell': 0,
            'assets': {'STOCK': 0, 'CRYPTO': 0, 'OTHER': 0},
            'tickers': {}
        }

        for trx in transactions:
            t = trx['ticker']
            a_type = trx['asset_type'] if trx['asset_type'] in ['STOCK', 'CRYPTO'] else 'OTHER'
            
            if t not in data['tickers']:
                data['tickers'][t] = {
                    'type': a_type, 'qty': 0, 'avg_cost': 0, 
                    'realized_pnl': 0, 'dividends': 0
                }
            
            tkr = data['tickers'][t]
            val = trx['total_value']

            if trx['type'] in ['IN', 'DEPOSIT']:
                data['total_in'] += val
                data['cash_available'] += val
            elif trx['type'] in ['OUT', 'WITHDRAW']:
                data['total_out'] += val
                data['cash_available'] -= val
            elif trx['type'] == 'BUY':
                data['cash_available'] -= val
                data['total_buy'] += val
                new_qty = tkr['qty'] + trx['qty']
                if new_qty > 0:
                    tkr['avg_cost'] = ((tkr['qty'] * tkr['avg_cost']) + val) / new_qty
                tkr['qty'] = new_qty
            elif trx['type'] == 'SELL':
                data['cash_available'] += val
                data['total_sell'] += val
                realized_profit = val - (trx['qty'] * tkr['avg_cost'])
                tkr['realized_pnl'] += realized_profit
                tkr['qty'] -= trx['qty']
            elif trx['type'] == 'CASH_DIVIDEND':
                data['cash_available'] += val
                tkr['dividends'] += val

        # Tính toán UnRealized PnL (Lãi chưa chốt)
        total_market_value = 0
        for t, tkr in data['tickers'].items():
            if tkr['qty'] > 0:
                curr_price = current_prices.get(t, tkr['avg_cost'])
                # Xử lý hệ số 1000 cho Stock nếu cần (theo logic Parser của bạn)
                multiplier = 1000 if tkr['type'] == 'STOCK' else 1
                market_val = tkr['qty'] * curr_price * multiplier
                
                tkr['market_value'] = market_val
                tkr['unrealized_pnl'] = market_val - (tkr['qty'] * tkr['avg_cost'] * multiplier)
                tkr['total_pnl'] = tkr['realized_pnl'] + tkr['unrealized_pnl'] + tkr['dividends']
                
                data['assets'][tkr['type']] += market_val
                total_market_value += market_val

        data['total_market_value'] = total_market_value
        data['net_worth'] = data['cash_available'] + total_market_value
        data['net_invested'] = data['total_in'] - data['total_out']
        data['total_pnl'] = data['net_worth'] - data['net_invested']
        data['roi'] = (data['total_pnl'] / data['net_invested'] * 100) if data['net_invested'] > 0 else 0

        return data, transactions

    def get_overview_report(self):
        """Layout Báo cáo tổng quan"""
        try:
            d, _ = self.calculate_portfolio()
            now = datetime.now().strftime("%d/%m/%Y | %H:%M")
            nw = d['net_worth'] if d['net_worth'] > 0 else 1
            
            # Tính phần trăm phân bổ
            p_stock = (d['assets']['STOCK'] / nw) * 100
            p_crypto = (d['assets']['CRYPTO'] / nw) * 100
            p_other = (d['assets']['OTHER'] / nw) * 100

            return (
                f"📊 <b>BÁO CÁO TÀI CHÍNH TỔNG QUAN</b>\n📅 {now}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>TỔNG TÀI SẢN: {self.format_currency(d['net_worth'])}</b>\n"
                f"💵 Tiền mặt: {self.format_currency(d['cash_available'])}\n"
                f"📈 Đang đầu tư: {self.format_currency(d['total_market_value'])}\n\n"
                f"🥧 <b>PHÂN BỔ DANH MỤC:</b>\n"
                f"• 📊 Stock ({p_stock:.1f}%) {self.create_progress_bar(p_stock, '🔵')}\n"
                f"• 🪙 Crypto ({p_crypto:.1f}%) {self.create_progress_bar(p_crypto, '🟡')}\n"
                f"• 🥇 Khác ({p_other:.1f}%) {self.create_progress_bar(p_other, '🟢')}\n\n"
                f"🚀 <b>HIỆU SUẤT:</b>\n"
                f"• 💼 Vốn ròng: {self.format_currency(d['net_invested'])}\n"
                f"• 📈 Lãi/Lỗ: <b>{self.format_currency(d['total_pnl'], True)}</b>\n"
                f"• 🎯 ROI: <b>{d['roi']:.1f}%</b>\n"
                f"━━━━━━━━━━━━━━━━━━━"
            )
        except Exception as e:
            return f"❌ Lỗi báo cáo: {str(e)}"
    
    # ... Các hàm get_category_report và get_ticker_detail_report giữ nguyên logic cũ của bạn ...
