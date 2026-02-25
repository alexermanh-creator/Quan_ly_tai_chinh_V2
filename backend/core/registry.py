# backend/core/registry.py
from backend.database.db_manager import db

ASSET_REGISTRY = {
    'STOCK': {
        'display_name': '📊 Cổ phiếu',
        'currency': 'VND',
        'unit': 'CP',
        'icon': '📊',
        'price_table': 'stock_prices',
        'id_column': 'ticker',
        'price_column': 'current_price',
        'rate_key': 'VND_RATE', # Key để tra cứu trong bảng Setting sau này
        'default_rate': 1,
        'precision': 0
    },
    'CRYPTO': {
        'display_name': '🪙 Crypto',
        'currency': 'USD',
        'unit': 'Coin',
        'icon': '🪙',
        'price_table': 'crypto_prices',
        'id_column': 'symbol',
        'price_column': 'price_usd',
        'rate_key': 'USD_RATE', # Key để tra cứu trong bảng Setting
        'default_rate': 26300,
        'precision': 4
    }
}

class AssetResolver:
    """Hệ thống nhận diện tài sản hỗ trợ Tiền tố (Prefix) và Tra cứu thông minh"""

    @staticmethod
    def resolve(input_text):
        """
        Trả về: (asset_type, clean_ticker)
        Ví dụ: "s vpb" -> ("STOCK", "VPB")
               "btc" -> ("CRYPTO", "BTC")
        """
        parts = input_text.upper().strip().split()
        
        # Trường hợp 1: Có tiền tố (S vpb, C btc)
        if len(parts) > 1:
            prefix = parts[0]
            ticker = parts[1]
            if prefix == 'S': return 'STOCK', ticker
            if prefix == 'C': return 'CRYPTO', ticker
        
        # Trường hợp 2: Không có tiền tố, tự nhận diện
        ticker = parts[0]

        # 1. Tra cứu lịch sử Database
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT asset_type FROM transactions WHERE ticker = ? LIMIT 1", (ticker,))
                result = cursor.fetchone()
                if result:
                    return result['asset_type'], ticker
        except:
            pass

        # 2. Quy tắc độ dài & từ khóa
        crypto_keywords = ['USDT', 'USDC', 'BTC', 'ETH', 'SOL', 'BNB']
        if any(key in ticker for key in crypto_keywords) or len(ticker) > 4:
            return 'CRYPTO', ticker

        # 3. Mặc định
        return 'STOCK', ticker
