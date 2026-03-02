# backend/core/engine.py
from backend.database.db_manager import db
from backend.core.registry import ASSET_REGISTRY

class UniversalEngine:
    def __init__(self, user_id):
        self.user_id = user_id

    def get_portfolio(self, asset_type):
        """Tính toán mọi loại tài sản dựa trên Metadata trong Registry"""
        meta = ASSET_REGISTRY.get(asset_type.upper())
        if not meta:
            return None

        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Lấy giá thị trường hiện tại (Dynamic Table/Column)
            cursor.execute(f"SELECT UPPER({meta['id_column']}), {meta['price_column']} FROM {meta['price_table']}")
            market_prices = dict(cursor.fetchall())

            # 2. Lấy toàn bộ giao dịch của loại tài sản này
            cursor.execute('''
                SELECT UPPER(ticker), amount, price, total_value, COALESCE(UPPER(type), 'BUY')
                FROM transactions 
                WHERE user_id = ? AND UPPER(asset_type) = ?
                ORDER BY date ASC
            ''', (self.user_id, asset_type.upper()))
            records = cursor.fetchall()

        # Logic tính vốn bình quân (Vạn năng)
        portfolio = {}
        for ticker, qty, price, total_val, t_type in records:
            if ticker not in portfolio:
                portfolio[ticker] = {'qty': 0, 'cost': 0, 'last_price': abs(price)}
            
            if t_type in ['BUY', 'IN', 'DIVIDEND_STOCK']:
                portfolio[ticker]['qty'] += abs(qty)
                # Dividend stock (Cổ tức cp) không làm tăng vốn (cost)
                if t_type != 'DIVIDEND_STOCK':
                    portfolio[ticker]['cost'] += abs(total_val)
            
            elif t_type in ['SELL', 'OUT'] and portfolio[ticker]['qty'] > 0:
                avg_cost = portfolio[ticker]['cost'] / portfolio[ticker]['qty']
                portfolio[ticker]['cost'] -= abs(qty) * avg_cost
                portfolio[ticker]['qty'] -= abs(qty)

        # 3. Tổng hợp và quy đổi tiền tệ
        positions = []
        total_value_vnd = 0
        total_cost_vnd = 0

        for ticker, data in portfolio.items():
            if data['qty'] > 0.000001:
                curr_price = market_prices.get(ticker, data['last_price'])
                
                # Quy đổi về VND dựa trên 'rate' trong Registry
                mkt_val_vnd = data['qty'] * curr_price * meta['rate']
                cst_val_vnd = data['cost'] * meta['rate']
                
                profit_vnd = mkt_val_vnd - cst_val_vnd
                roi = (profit_vnd / cst_val_vnd * 100) if cst_val_vnd != 0 else 0

                positions.append({
                    'ticker': ticker,
                    'qty': data['qty'],
                    'avg_price': data['cost'] / data['qty'],
                    'current_price': curr_price,
                    'market_value': mkt_val_vnd,
                    'profit': profit_vnd,
                    'roi': roi,
                    'unit': meta['unit']
                })
                total_value_vnd += mkt_val_vnd
                total_cost_vnd += cst_val_vnd

        return {
            'positions': positions,
            'summary': {
                'total_value': total_value_vnd,
                'total_cost': total_cost_vnd,
                'total_profit': total_value_vnd - total_cost_vnd,
                'total_roi': ( (total_value_vnd - total_cost_vnd) / total_cost_vnd * 100) if total_cost_vnd != 0 else 0,
                'icon': meta['icon'],
                'name': meta['display_name']
            }
        }