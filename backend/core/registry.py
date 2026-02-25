# backend/core/registry.py
from backend.database.db_manager import db

# Từ điển cấu hình tài sản - Nơi duy nhất cần thêm khi có loại tài sản mới
ASSET_REGISTRY = {
    'STOCK': {
        'display_name': '📊 Cổ phiếu', 
        'currency': 'VND', 
        'icon': '📊',
        'module_class': 'StockModule', # Tên Class trong Module
        'module_path': 'backend.modules.stock',
        'default_rate': 1,
        'multiplier': 1000  # Đặc thù chứng khoán VN
    },
    'CRYPTO': {
        'display_name': '🪙 Crypto', 
        'currency': 'USD', 
        'icon': '🪙',
        'module_class': 'CryptoModule',
        'module_path': 'backend.modules.crypto',
        'default_rate': 26300,
        'multiplier': 1     # Crypto tính theo đơn vị đơn lẻ
    }
}

class AssetResolver:
    @staticmethod
    def resolve(input_text):
        """
        Xác định loại tài sản và Ticker từ câu lệnh.
        Giữ nguyên logic thông minh của CEO.
        """
        parts = input_text.upper().strip().split()
        if not parts: return None, None
        
        # 1. Xử lý Prefix (Ưu tiên cao nhất)
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
                if result: 
                    # Chuyển đổi result từ Row sang dict nếu cần
                    atype = result[0] if isinstance(result, tuple) else result['asset_type']
                    return atype, ticker
        except:
            pass

        # 3. Nhận diện thông minh (Dựa trên bộ từ khóa của CEO)
        crypto_keys = ['USDT', 'USDC', 'BTC', 'ETH', 'SOL', 'BNB']
        if any(k in ticker for k in crypto_keys) or len(ticker) > 4:
            return 'CRYPTO', ticker

        # Mặc định là STOCK
        return 'STOCK', ticker

    @staticmethod
    def get_module(asset_type):
        """Hàm bổ sung để lấy cấu hình Module nhanh chóng"""
        return ASSET_REGISTRY.get(asset_type)
