# backend/core/registry.py

ASSET_REGISTRY = {
    'STOCK': {
        'display_name': '📊 Cổ phiếu',
        'currency': 'VND',
        'unit': 'CP',
        'icon': '📊',
        'price_table': 'stock_prices',
        'id_column': 'ticker',
        'price_column': 'current_price',
        'rate': 1,  # Tỷ giá so với VND
        'precision': 0 # Số chữ số sau dấu phẩy
    },
    'CRYPTO': {
        'display_name': '🪙 Crypto',
        'currency': 'USD',
        'unit': 'Coin',
        'icon': '🪙',
        'price_table': 'crypto_prices',
        'id_column': 'symbol',
        'price_column': 'price_usd',
        'rate': 26300, # Tỷ giá USD/VND (Sẽ update từ fetcher sau)
        'precision': 4
    },
    # Sau này muốn thêm GOLD chỉ cần thêm 1 block ở đây
}

# Danh mục lệnh để Parser tự điều hướng
COMMAND_MAP = {
    'vpb': 'STOCK', 'hpg': 'STOCK', 'vnm': 'STOCK', 'tcbs': 'STOCK',
    'btc': 'CRYPTO', 'eth': 'CRYPTO', 'sol': 'CRYPTO', 'usdt': 'CRYPTO'
}