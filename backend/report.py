# backend/modules/report.py
import io
from datetime import datetime
from backend.interface import BaseModule
from backend.database.repository import Repository

try:
    import pandas as pd
except ImportError:
    pd = None  # Sẽ yêu cầu cài đặt pandas và openpyxl để xuất Excel

class ReportModule(BaseModule):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.repo = Repository()

    def format_currency(self, value, is_pnl=False):
        """Định dạng tiền tệ chuẩn VNĐ"""
        if value == 0: return "0đ"
        sign = "+" if is_pnl and value > 0 else ""
        return f"{sign}{value:,.0f}đ".replace(',', '.')

    def create_progress_bar(self, percentage, color_emoji):
        """Vẽ thanh Progress Bar bằng Emoji"""
        filled = int(percentage / 10) if percentage > 0 else 0
        filled = min(10, max(0, filled)) # Đảm bảo nằm trong khoảng 0-10
        empty = 10 - filled
        return f"[{color_emoji * filled}{'⚪' * empty}]"

    def calculate_portfolio(self, start_date=None, end_date=None, asset_filter=None):
        """CỖ MÁY TÍNH TOÁN LÕI: Quét toàn bộ giao dịch và tính PnL"""
        transactions = self.repo.get_transactions_in_period(self.user_id, start_date, end_date, asset_filter)
        current_prices = self.repo.get_current_prices()

        data = {
            'cash_available': 0, 'total_in': 0, 'total_out': 0,
            'total_buy': 0, 'total_sell': 0,
            'assets': {'STOCK': 0, 'CRYPTO': 0, 'OTHER': 0},
            'tickers': {}
        }

        # Thuật toán tính Giá vốn trung bình và Realized PnL
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
            elif trx['type'] in ['OUT', 'WITHDRAW']:
                data['total_out'] += trx['total_value']
                data['cash_available'] -= trx['total_value']
            elif trx['type'] == 'BUY':
                data['cash_available'] -= trx['total_value']
                data['total_buy'] += trx['total_value']
                tkr['total_buy_vol'] += trx['qty']
                
                # Tính lại giá vốn trung bình (Average Cost)
                new_qty = tkr['qty'] + trx['qty']
                if new_qty > 0:
                    tkr['avg_cost'] = ((tkr['qty'] * tkr['avg_cost']) + trx['total_value']) / new_qty
                tkr['qty'] = new_qty
            elif trx['type'] == 'SELL':
                data['cash_available'] += trx['total_value']
                data['total_sell'] += trx['total_value']
                tkr['total_sell_vol'] += trx['qty']
                
                # Tính lãi chốt (Realized PnL)
                realized_profit = trx['total_value'] - (trx['qty'] * tkr['avg_cost'])
                tkr['realized_pnl'] += realized_profit
                tkr['qty'] -= trx['qty']
                if tkr['qty'] <= 0:
                    tkr['qty'] = 0
                    tkr['avg_cost'] = 0
            elif trx['type'] == 'CASH_DIVIDEND':
                data['cash_available'] += trx['total_value']
                tkr['dividends'] += trx['total_value']

        # Tính toán Giá trị thị trường (Market Value) và Unrealized PnL
        total_market_value = 0
        total_realized = 0
        total_unrealized = 0

        for t, tkr in data['tickers'].items():
            curr_price = current_prices.get(t, tkr['avg_cost']) # Nếu chưa cập nhật giá, dùng giá vốn
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
        
        if data['net_invested'] > 0:
            data['roi'] = (data['total_pnl'] / data['net_invested']) * 100
        else:
            data['roi'] = 0

        return data

    def get_overview_report(self):
        """TẦNG 1: Báo cáo Tổng quan Toàn thời gian"""
        d = self.calculate_portfolio()
        now = datetime.now().strftime("%d/%m/%Y | %H:%M")
        
        # Tính phần trăm phân bổ
        nw = d['net_worth'] if d['net_worth'] > 0 else 1
        pct_stock = (d['assets']['STOCK'] / nw) * 100
        pct_crypto = (d['assets']['CRYPTO'] / nw) * 100
        pct_other = (d['assets']['OTHER'] / nw) * 100

        # Lọc Top Lãi / Top Lỗ
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
        """TẦNG 2: Báo cáo theo Danh mục (Stock/Crypto)"""
        d = self.calculate_portfolio(start_date, end_date, asset_filter=asset_type)
        
        # Chỉ lấy các mã thuộc danh mục này
        cat_tickers = {k: v for k, v in d['tickers'].items() if v['type'] == asset_type}
        sorted_tickers = sorted(cat_tickers.items(), key=lambda x: x[1]['realized_pnl'], reverse=True)
        
        win_list = [f"   {i+1}. {k}: {self.format_currency(v['realized_pnl'], True)}" for i, (k, v) in enumerate(sorted_tickers) if v['realized_pnl'] > 0][:3]
        lose_list = [f"   {i+1}. {k}: {self.format_currency(v['realized_pnl'], True)}" for i, (k, v) in enumerate(sorted_tickers[::-1]) if v['realized_pnl'] < 0][:3]

        win_str = "\n".join(win_list) if win_list else "   Không có dữ liệu"
        lose_str = "\n".join(lose_list) if lose_list else "   Không có dữ liệu"

        net_flow = d['total_in'] - d['total_out']
        realized_only = sum(v['realized_pnl'] for v in cat_tickers.values())

        name = "CHỨNG KHOÁN" if asset_type == 'STOCK' else "CRYPTO" if asset_type == 'CRYPTO' else "TÀI SẢN KHÁC"

        html = f"""📊 <b>BÁO CÁO {name} ({label_time})</b> 
━━━━━━━━━━━━━━━━━━━ 
💸 <b>DÒNG TIỀN TRONG KỲ:</b> 
⬆️ Thực nạp:            {self.format_currency(d['total_in'], True)} 
⬇️ Thực rút:             {self.format_currency(-d['total_out'], True)} 
🌊 Dòng tiền ròng:      <b>{self.format_currency(net_flow, True)}</b>

🔄 <b>HOẠT ĐỘNG GIAO DỊCH:</b> 
🛒 Tổng mua:             {self.format_currency(d['total_buy'])} 
💰 Tổng bán:             {self.format_currency(d['total_sell'])}

🚀 <b>HIỆU SUẤT TRONG KỲ (P&L):</b> 
📈 Lãi/Lỗ (Đã chốt):     <b>{self.format_currency(realized_only, True)}</b>

🏆 <b>Top Đóng Góp:</b> 
{win_str} 
⚠️ <b>Top Kéo Lùi:</b> 
{lose_str} 
━━━━━━━━━━━━━━━━━━━"""
        return html

    def get_ticker_detail_report(self, ticker):
        """TẦNG 3: Báo cáo Chi tiết 1 mã (Drill-down)"""
        d = self.calculate_portfolio()
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

    def export_excel_report(self):
        """Tạo file Excel Báo Cáo Tài Chính (Cần thư viện pandas)"""
        if pd is None:
            return None, "❌ Cần cài đặt pandas để xuất Excel (pip install pandas openpyxl)"
            
        d = self.calculate_portfolio()
        
        # Tạo DataFrame cho Tổng quan
        overview_data = {
            'Chỉ số': ['Tổng Tài Sản', 'Tiền mặt', 'Đang đầu tư', 'Tổng Nạp', 'Tổng Rút', 'Vốn Ròng', 'Tổng Lãi/Lỗ'],
            'Giá trị (VNĐ)': [d['net_worth'], d['cash_available'], d['total_market_value'], d['total_in'], d['total_out'], d['net_invested'], d['total_pnl']]
        }
        df_overview = pd.DataFrame(overview_data)

        # Tạo DataFrame cho Chi tiết Từng mã
        tickers_list = []
        for k, v in d['tickers'].items():
            tickers_list.append({
                'Mã': k,
                'Phân loại': v['type'],
                'Số lượng đang giữ': v['qty'],
                'Giá vốn TB': v['avg_cost'],
                'Giá hiện tại': v['current_price'],
                'Lãi/Lỗ đã chốt': v['realized_pnl'],
                'Lãi/Lỗ đang gồng': v['unrealized_pnl'],
                'Tổng Lợi Nhuận': v['total_pnl']
            })
        df_tickers = pd.DataFrame(tickers_list) if tickers_list else pd.DataFrame(columns=['Mã', 'Phân loại', 'Số lượng đang giữ'])

        # Ghi ra BytesIO để gửi thẳng qua Telegram không cần lưu ổ cứng
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_overview.to_excel(writer, sheet_name='Tổng Quan', index=False)
            df_tickers.to_excel(writer, sheet_name='Chi Tiết Danh Mục', index=False)
        
        output.seek(0)
        filename = f"Bao_Cao_Tai_Chinh_{datetime.now().strftime('%d%m%Y')}.xlsx"
        return output, filename
