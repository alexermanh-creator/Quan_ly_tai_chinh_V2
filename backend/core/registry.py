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
        'rate': 1,           # Tỷ giá so với VND
        'precision': 0       # Số chữ số sau dấu phẩy (Cổ phiếu thường là số nguyên)
    },
    'CRYPTO': {
        'display_name': '🪙 Crypto',
        'currency': 'USD',
        'unit': 'Coin',
        'icon': '🪙',
        'price_table': 'crypto_prices',
        'id_column': 'symbol',
        'price_column': 'price_usd',
        'rate': 26300,       # Tỷ giá USD/VND tạm tính (Sẽ cập nhật sau)
        'precision': 4       # Số chữ số sau dấu phẩy (Ví dụ: 0.1234 BTC)
    }
}

# Danh mục lệnh để hệ thống tự điều hướng mã nào vào nhóm nào
# Giúp bạn không cần phải gõ "mua_c" hay "mua_s" nữa
COMMAND_MAP = {
    'vpb': 'STOCK', 'hpg': 'STOCK', 'vnm': 'STOCK', 'tcbs': 'STOCK',
    'btc': 'CRYPTO', 'eth': 'CRYPTO', 'sol': 'CRYPTO', 'usdt': 'CRYPTO'
}
