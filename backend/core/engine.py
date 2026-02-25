# backend/core/engine.py
from backend.database.db_manager import db
from backend.core.registry import ASSET_REGISTRY

class UniversalEngine:
    def __init__(self, user_id):
        self.user_id = user_id

    def get_portfolio(self, asset_type):
        """Tính toán lãi lỗ cho bất kỳ loại tài sản nào dựa trên Metadata trong Registry"""
        asset_type = asset_type.upper()
        meta = ASSET_REGISTRY.get(asset_type)
        if not meta:
            return None

        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Lấy giá thị trường từ bảng tương ứng trong Registry
            # Dùng f-string vì tên bảng và cột đã được quy định cứng trong Registry an toàn
            cursor.execute(f"SELECT UPPER({meta['id_column']}), {meta['price_column']} FROM {meta['price_table']}")
            market_prices = dict(cursor.fetchall())

            # 2. Lấy toàn bộ lịch sử giao dịch của loại tài sản này
            cursor.execute('''
                SELECT UPPER(ticker), amount, price, total_value, COALESCE(UPPER(type), 'BUY')
                FROM transactions 
                WHERE user_id = ? AND UPPER(asset_type) = ?
                ORDER BY date ASC
            ''', (self.user_id, asset_type))
            records = cursor.fetchall()

        # 3. Logic tính vốn bình quân (Weighted Average Cost)
        portfolio = {}
        for row in records:
            ticker, qty, price, total_val, t_type = row[0], row[1], row[2], row[3], row[4]
            
            if ticker not in portfolio:
                portfolio[ticker] = {'qty': 0, 'cost': 0, 'last_price': abs(price)}
            
            # Xử lý Mua hoặc Nạp tài sản
            if t_type in ['BUY', 'IN']:
                portfolio[ticker]['qty'] += abs(qty)
                portfolio[ticker]['cost'] += abs(total_val)
            
            # Xử lý Bán hoặc Rút tài sản
            elif t_type in ['SELL', 'OUT'] and portfolio[ticker]['qty'] > 0:
                avg_cost = portfolio[ticker]['cost'] / portfolio[ticker]['qty']
                portfolio[ticker]['cost'] -= abs(qty) * avg_cost
                portfolio[ticker]['qty'] -= abs(qty)

        # 4. Tổng hợp dữ liệu hiển thị và quy đổi tiền tệ
        positions = []
        total_value_vnd = 0
        total_cost_vnd = 0

        for ticker, data in portfolio.items():
            if data['qty'] > 0.000001:
                # Lấy giá hiện tại, nếu không có thì dùng giá giao dịch cuối cùng
                curr_price = market_prices.get(ticker, data['last_price'])
                
                # Quy đổi giá trị về VND dựa trên 'rate' (ví dụ USD -> VND)
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
                'total_roi': ((total_value_vnd - total_cost_vnd) / total_cost_vnd * 100) if total_cost_vnd != 0 else 0,
                'icon': meta['icon'],
                'name': meta['display_name']
            }
        }
