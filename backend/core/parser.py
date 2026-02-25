# backend/core/parser.py
import re
from backend.core.registry import ASSET_REGISTRY, COMMAND_MAP

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        """
        Cú pháp: [mã] [lệnh] [số lượng] [giá]
        Ví dụ: vpb buy 100 22.5 hoặc btc buy 0.01 95000
        """
        try:
            # Loại bỏ khoảng trắng thừa và tách từ
            parts = text.lower().strip().split()
            
            # Kiểm tra xem có đủ tối thiểu 4 phần tử không
            if len(parts) < 4:
                return None
            
            ticker = parts[0]
            action = parts[1].upper() # BUY, SELL, DIVIDEND, IN, OUT
            
            # Xử lý số lượng và giá (chuyển về số thực)
            try:
                qty = float(parts[2])
                price = float(parts[3])
            except ValueError:
                return None
            
            # Tự động nhận diện loại tài sản (Asset Type)
            # Nếu mã nằm trong COMMAND_MAP thì lấy loại đó, nếu không mặc định là STOCK
            asset_type = COMMAND_MAP.get(ticker, 'STOCK')
            
            # Kiểm tra xem loại tài sản này có được hỗ trợ trong Registry không
            if asset_type not in ASSET_REGISTRY:
                return None
                
            return {
                'ticker': ticker.upper(),
                'action': action,
                'qty': qty,
                'price': price,
                'total_val': qty * price,
                'asset_type': asset_type
            }
        except Exception:
            return None

    @staticmethod
    def is_transaction_command(text):
        """Kiểm tra nhanh xem tin nhắn có dạng một lệnh giao dịch hay không"""
        # Kiểm tra nếu bắt đầu bằng một từ và theo sau là buy/sell/in/out/div
        pattern = r'^\w+\s+(buy|sell|in|out|div|dividend)\s+'
        return bool(re.match(pattern, text.lower().strip()))
