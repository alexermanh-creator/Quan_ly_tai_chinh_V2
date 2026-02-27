# backend/core/engine.py
from backend.database.db_manager import db
from backend.core.registry import ASSET_REGISTRY, AssetResolver

class UniversalEngine:
    def __init__(self, user_id):
        self.user_id = user_id

    def get_portfolio(self, asset_type):
        """
        Hệ thống truy xuất Portfolio siêu tốc:
        - Lấy số dư đã tính toán sẵn từ bảng portfolio.
        - Tự động áp dụng tỷ giá CEO nhập tay (EX_RATE).
        - Đồng bộ hóa giá thị trường từ manual_prices.
        """
        asset_type = asset_type.upper()
        meta = ASSET_REGISTRY.get(asset_type)
        if not meta: 
            return None

        # Lấy tỷ giá CEO nhập tay
        custom_rate = AssetResolver.get_custom_exchange_rate()
        rate = custom_rate if asset_type == 'CRYPTO' else 1
        
        # Hệ số nhân (1000 cho Stock VN, 1 cho Crypto)
        multiplier = meta.get('multiplier', 1)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Lấy giá thị trường hiện tại
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            market_prices = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            # 2. Lấy số dư từ bảng Portfolio (Kết quả đã tính toán từ Repository)
            cursor.execute('''
                SELECT ticker, total_qty, avg_price 
                FROM portfolio 
                WHERE user_id = ? AND asset_type = ? AND total_qty > 1e-6
            ''', (self.user_id, asset_type))
            rows = cursor.fetchall()

        positions = []
        total_mkt_vnd = 0
        total_cost_vnd = 0

        for row in rows:
            ticker = row['ticker']
            qty = row['total_qty']
            avg_p = row['avg_price']
            
            # Lấy giá hiện tại (ưu tiên manual, không có dùng giá vốn)
            curr_p = market_prices.get(ticker, avg_p)
            
            # Tính toán giá trị quy đổi VND
            mkt_val_vnd = (qty * curr_p * multiplier) * rate
            cost_val_vnd = (qty * avg_p * multiplier) * rate
            
            unrealized_pnl_vnd = mkt_val_vnd - cost_val_vnd
            
            positions.append({
                'ticker': ticker,
                'qty': qty,
                'avg_price': avg_p,
                'current_price': curr_p,
                'market_value_vnd': mkt_val_vnd,
                'unrealized_profit_vnd': unrealized_pnl_vnd,
                'roi': (unrealized_pnl_vnd / cost_val_vnd * 100) if cost_val_vnd != 0 else 0
            })
            
            total_mkt_vnd += mkt_val_vnd
            total_cost_vnd += cost_val_vnd

        return {
            'positions': sorted(positions, key=lambda x: x['market_value_vnd'], reverse=True),
            'summary': {
                'total_value': total_mkt_vnd,
                'total_cost': total_cost_vnd,
                'total_profit': total_mkt_vnd - total_cost_vnd,
                'total_roi': ((total_mkt_vnd - total_cost_vnd) / total_cost_vnd * 100) if total_cost_vnd != 0 else 0,
                'icon': meta['icon'],
                'name': meta['display_name']
            }
        }
