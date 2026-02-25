# backend/core/engine.py
from backend.database.db_manager import db
from backend.core.registry import ASSET_REGISTRY

class UniversalEngine:
    def __init__(self, user_id):
        self.user_id = user_id

    def get_portfolio(self, asset_type):
        asset_type = asset_type.upper()
        meta = ASSET_REGISTRY.get(asset_type)
        if not meta: return None

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT UPPER({meta['id_column']}), {meta['price_column']} FROM {meta['price_table']}")
            market_prices = dict(cursor.fetchall())

            cursor.execute('''
                SELECT UPPER(ticker), amount, price, total_value, UPPER(type)
                FROM transactions 
                WHERE user_id = ? AND UPPER(asset_type) = ?
                ORDER BY date ASC
            ''', (self.user_id, asset_type))
            records = cursor.fetchall()

        portfolio = {}
        for row in records:
            ticker, qty, price, total_val, t_type = row[0], row[1], row[2], row[3], row[4]
            
            if ticker not in portfolio:
                portfolio[ticker] = {'qty': 0, 'cost': 0, 'realized_pnl': 0}
            
            # --- 1. MUA (BUY) ---
            if t_type == 'BUY':
                portfolio[ticker]['qty'] += abs(qty)
                portfolio[ticker]['cost'] += abs(total_val)
            
            # --- 2. BÁN (SELL) ---
            elif t_type == 'SELL' and portfolio[ticker]['qty'] > 0:
                avg_cost = portfolio[ticker]['cost'] / portfolio[ticker]['qty']
                sale_revenue = abs(qty) * price
                sale_cost_basis = abs(qty) * avg_cost
                
                portfolio[ticker]['realized_pnl'] += (sale_revenue - sale_cost_basis)
                portfolio[ticker]['cost'] -= sale_cost_basis
                portfolio[ticker]['qty'] -= abs(qty)

            # --- 3. CỔ TỨC CỔ PHIẾU (DIVIDEND_STOCK / BONUS) ---
            # Ví dụ: Nhận 1000 CP VPB từ cổ tức. Qty tăng, vốn giữ nguyên.
            elif t_type in ['DIVIDEND_STOCK', 'BONUS']:
                portfolio[ticker]['qty'] += abs(qty)

            # --- 4. CỔ TỨC TIỀN MẶT (CASH_DIVIDEND) ---
            # Ví dụ: Nhận 2tr tiền mặt từ HPG. Qty/Cost giữ nguyên, cộng thẳng vào PnL.
            elif t_type == 'CASH_DIVIDEND':
                portfolio[ticker]['realized_pnl'] += abs(total_val)

        # Quy đổi và Tổng hợp
        positions = []
        total_mkt_value_vnd = 0
        total_cost_basis_vnd = 0
        rate = meta.get('default_rate', 1)

        for ticker, data in portfolio.items():
            if data['qty'] > 0.000001:
                curr_price = market_prices.get(ticker, 0)
                # Giá vốn bình quân sau khi đã trừ cổ tức cổ phiếu
                avg_price = data['cost'] / data['qty'] 
                
                mkt_val_vnd = (data['qty'] * curr_price) * rate
                cst_val_vnd = data['cost'] * rate
                
                # Lãi chưa thực hiện = (Giá hiện tại - Giá vốn đã giảm nhờ cổ tức) * Số lượng
                unrealized_profit_vnd = mkt_val_vnd - cst_val_vnd
                
                positions.append({
                    'ticker': ticker,
                    'qty': data['qty'],
                    'avg_price': avg_price,
                    'current_price': curr_price,
                    'market_value_vnd': mkt_val_vnd,
                    'unrealized_profit_vnd': unrealized_profit_vnd,
                    'realized_pnl_vnd': data['realized_pnl'] * rate, # Gồm lãi bán + Cổ tức tiền mặt
                    'roi': (unrealized_profit_vnd / cst_val_vnd * 100) if cst_val_vnd != 0 else 0,
                    'unit': meta['unit']
                })
                total_mkt_value_vnd += mkt_val_vnd
                total_cost_basis_vnd += cst_val_vnd

        return {
            'positions': positions,
            'summary': {
                'total_value': total_mkt_value_vnd,
                'total_cost': total_cost_basis_vnd,
                'total_profit': (total_mkt_value_vnd - total_cost_basis_vnd),
                'total_roi': ((total_mkt_value_vnd - total_cost_basis_vnd) / total_cost_basis_vnd * 100) if total_cost_basis_vnd != 0 else 0,
                'icon': meta['icon'],
                'name': meta['display_name']
            }
        }
