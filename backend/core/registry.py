# backend/core/registry.py
from backend.database.db_manager import db

ASSET_REGISTRY = {
    'STOCK': {
        'display_name': '📊 Cổ phiếu', 'currency': 'VND', 'icon': '📊',
        'price_table': 'stock_prices', 'id_column': 'ticker', 'price_column': 'current_price',
        'rate_key': 'VND_RATE', 'default_rate': 1, 'precision': 0
    },
    'CRYPTO': {
        'display_name': '🪙 Crypto', 'currency': 'USD', 'icon': '🪙',
        'price_table': 'crypto_prices', 'id_column': 'symbol', 'price_column': 'price_usd',
        'rate_key': 'USD_RATE', 'default_rate': 26300, 'precision': 4
    }
}

class AssetResolver:
    @staticmethod
    def resolve(input_text):
        parts = input_text.upper().strip().split()
        
        # 1. Xử lý Prefix
        if len(parts) > 1:
            prefix, ticker = parts[0], parts[1]
            if prefix == 'S': return 'STOCK', ticker
            if prefix == 'C': return 'CRYPTO', ticker
        
        ticker = parts[0]

        # 2. Tra cứu DB (Dùng kết nối an toàn từ db_manager)
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT asset_type FROM transactions WHERE ticker = ? LIMIT 1", (ticker,))
                result = cursor.fetchone()
                if result: return result['asset_type'], ticker
        except:
            pass

        # 3. Nhận diện thông minh
        crypto_keys = ['USDT', 'USDC', 'BTC', 'ETH', 'SOL', 'BNB']
        if any(k in ticker for k in crypto_keys) or len(ticker) > 4:
            return 'CRYPTO', ticker

        return 'STOCK', ticker
