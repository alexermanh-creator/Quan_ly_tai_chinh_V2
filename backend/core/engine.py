# backend/core/engine.py
from backend.database.db_manager import db
from backend.core.registry import ASSET_REGISTRY

class UniversalEngine:
    def __init__(self, user_id):
        self.user_id = user_id

    def get_portfolio(self, asset_type):
        """
        Hệ thống tính toán vạn năng - Đạt chuẩn CTO Level:
        - Xử lý không phân biệt hoa thường (Case-insensitive)
        - Tính toán giá vốn sau cổ tức (Stock Dividend)
        - Ghi nhận lợi nhuận tiền mặt (Cash Dividend)
        - Chống sai số dấu phẩy động (Float Precision)
        """
        asset_type = asset_type.upper()
        meta = ASSET_REGISTRY.get(asset_type)
        if not meta: 
            return None

        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Lấy giá thị trường: Dùng UPPER để đồng bộ mã
            cursor.execute(f"SELECT UPPER({meta['id_column']}), {meta['price_column']} FROM {meta['price_table']}")
            market_prices = dict(cursor.fetchall())

            # 2. Lấy giao dịch: Lọc theo user và loại tài sản
            cursor.execute('''
                SELECT UPPER(ticker), amount, price, total_value, UPPER(type)
                FROM transactions 
                WHERE user_id = ? AND UPPER(asset_type) = ?
                ORDER BY date ASC
            ''', (self.user_id, asset_type))
            records = cursor.fetchall()

        # 3. Kho lưu trữ tính toán
        portfolio = {}
        
        for row in records:
            ticker, qty, price, total_val, t_type = row[0], row[1], row[2], row[3], row[4]
            
            if ticker not in portfolio:
                portfolio[ticker] = {'qty': 0, 'cost': 0, 'realized_pnl': 0}
            
            # --- NGHIỆP VỤ MUA (BUY) ---
            if t_type == 'BUY':
                portfolio[ticker]['qty'] += abs(qty)
                portfolio[ticker]['cost'] += abs(total_val)
            
            # --- NGHIỆP VỤ BÁN (SELL) ---
            elif t_type == 'SELL' and portfolio[ticker]['qty'] > 0:
                # Tính giá vốn trung bình tại thời điểm bán
                avg_cost_basis = portfolio[ticker]['cost'] / portfolio[ticker]['qty']
                
                # Doanh thu thực tế - Vốn gốc của số lượng bán
                actual_revenue = abs(qty) * price
                cost_of_goods_sold = abs(qty) * avg_cost_basis
                
                # Cộng lợi nhuận vào túi (Realized) và trừ kho
                portfolio[ticker]['realized_pnl'] += (actual_revenue - cost_of_goods_sold)
                portfolio[ticker]['cost'] -= cost_of_goods_sold
                portfolio[ticker]['qty'] -= abs(qty)

            # --- CỔ TỨC CỔ PHIẾU / THƯỞNG (STOCK DIVIDEND) ---
            elif t_type in ['DIVIDEND_STOCK', 'BONUS']:
                # Tăng số lượng nhưng KHÔNG tăng vốn -> Giá vốn bình quân tự giảm
                portfolio[ticker]['qty'] += abs(qty)

            # --- CỔ TỨC TIỀN MẶT (CASH_DIVIDEND) ---
            elif t_type == 'CASH_DIVIDEND':
                # Cộng thẳng tiền vào lợi nhuận thực tế
                portfolio[ticker]['realized_pnl'] += abs(total_val)

        # 4. Quy đổi tỷ giá và Tổng hợp kết quả
        positions = []
        total_mkt_vnd = 0
        total_cost_vnd = 0
        
        # Mặc định lấy từ Registry, sau này Setting sẽ ghi đè vào đây
        rate = meta.get('default_rate', 1)

        for ticker, data in portfolio.items():
            # Chỉ xử lý các mã còn số dư (Bỏ qua số rác < 0.000001)
            if data['qty'] > 1e-6:
                curr_price = market_prices.get(ticker, 0)
                
                # Giá vốn bình quân sau mọi điều chỉnh
                avg_price = data['cost'] / data['qty']
                
                # Quy đổi ra VND cho Dashboard chung
                mkt_val_vnd = (data['qty'] * curr_price) * rate
                cst_val_vnd = data['cost'] * rate
                
                unrealized_profit_vnd = mkt_val_vnd - cst_val_vnd
                
                positions.append({
                    'ticker': ticker,
                    'qty': data['qty'],
                    'avg_price': avg_price,
                    'current_price': curr_price,
                    'market_value_vnd': mkt_val_vnd,
                    'unrealized_profit_vnd': unrealized_profit_vnd,
                    'realized_pnl_vnd': data['realized_pnl'] * rate,
                    'roi': (unrealized_profit_vnd / cst_val_vnd * 100) if cst_val_vnd != 0 else 0,
                    'unit': meta['unit']
                })
                total_mkt_vnd += mkt_val_vnd
                total_cost_vnd += cst_val_vnd

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
