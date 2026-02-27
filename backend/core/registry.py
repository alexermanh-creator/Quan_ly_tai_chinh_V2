# backend/core/registry.py
from backend.database.db_manager import db

# Cấu hình định nghĩa loại tài sản
ASSET_REGISTRY = {
    'STOCK': {
        'display_name': '📊 Cổ phiếu', 
        'currency': 'VND', 
        'icon': '📊',
        'multiplier': 1000  # Đặc thù chứng khoán VN (giá 28.5 hiểu là 28,500đ)
    },
    'CRYPTO': {
        'display_name': '🪙 Crypto', 
        'currency': 'USD', 
        'icon': '🪙',
        'multiplier': 1     # Crypto tính theo đơn vị đơn lẻ
    },
    'CASH': {
        'display_name': '💵 Tiền mặt',
        'currency': 'VND',
        'icon': '🏦',
        'multiplier': 1
    }
}

class AssetResolver:
    @staticmethod
    def get_custom_exchange_rate():
        """
        Lấy tỷ giá USD/VND do CEO tự nhập từ bảng settings.
        Nếu chưa nhập, mặc định trả về 26300.
        """
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = 'EX_RATE' LIMIT 1")
                result = cursor.fetchone()
                if result:
                    return float(result['value'])
        except:
            pass
        return 26300 # Giá trị dự phòng

    @staticmethod
    def resolve(input_text):
        """
        Xác định loại tài sản và Ticker.
        Ưu tiên: Prefix -> Lịch sử DB -> Quy tắc thông minh.
        """
        parts = input_text.upper().strip().split()
        if not parts: return None, None
        
        # 1. Xử lý Prefix (S = Stock, C = Crypto)
        if len(parts) > 1:
            prefix, ticker = parts[0], parts[1]
            if prefix == 'S': return 'STOCK', ticker
            if prefix == 'C': return 'CRYPTO', ticker
        
        ticker = parts[0]

        # 2. Tra cứu lịch sử trong DB để đảm bảo tính nhất quán
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT asset_type FROM transactions WHERE ticker = ? LIMIT 1", (ticker,))
                result = cursor.fetchone()
                if result: 
                    return result['asset_type'], ticker
        except:
            pass

        # 3. Nhận diện thông minh
        crypto_keys = ['USDT', 'USDC', 'BTC', 'ETH', 'SOL', 'BNB', 'DOGE']
        # Nếu ticker có trong list hoặc dài hơn 4 ký tự (thường là Crypto)
        if any(k in ticker for k in crypto_keys) or len(ticker) > 4:
            return 'CRYPTO', ticker

        # Mặc định là STOCK (Ticker 3 chữ cái)
        return 'STOCK', ticker
