# backend/core/parser.py
import re
from backend.core.registry import AssetResolver, ASSET_REGISTRY

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw_text = text.lower().strip()
            
            # --- 1. XỬ LÝ LỆNH NẠP/RÚT TIỀN (CASH) ---
            cash_match = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw_text)
            if cash_match:
                action_raw = cash_match.group(1)
                amount_str = cash_match.group(2).replace(',', '.')
                unit = cash_match.group(3)
                amount = float(amount_str)
                if unit == 'ty': amount *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: amount *= 1_000_000
                
                return {
                    'ticker': 'CASH', 'action': 'IN' if action_raw == 'nap' else 'OUT',
                    'qty': 1.0, 'price': amount, 'total_val': amount, 'asset_type': 'CASH'
                }

            # --- 2. XỬ LÝ GIAO DỊCH TÀI SẢN (DÙNG REGISTRY ĐỘNG) ---
            parts = raw_text.split()
            if len(parts) < 2: return None
            
            # Sử dụng AssetResolver thông minh từ Registry của CEO
            if parts[0] in ['s', 'c']:
                input_resolver = f"{parts[0]} {parts[1]}"
                val_1 = parts[2]
                val_2 = parts[3] if len(parts) > 3 else None
            else:
                # Giữ nguyên logic mặc định cho Ticker 3 chữ cái là Stock
                input_resolver = f"s {parts[0]}" if len(parts[0]) == 3 and parts[0].isalpha() else parts[0]
                val_1 = parts[1]
                val_2 = parts[2] if len(parts) > 2 else None

            asset_type, ticker = AssetResolver.resolve(input_resolver)

            # Phân loại lệnh đặc biệt (Cổ tức) - Chỉ áp dụng cho STOCK
            if asset_type == 'STOCK':
                if val_2 == 'cash':
                    return {'ticker': ticker, 'action': 'CASH_DIVIDEND', 'qty': 0, 'price': 0, 'total_val': abs(float(val_1)), 'asset_type': asset_type}
                if val_2 == 'div':
                    return {'ticker': ticker, 'action': 'DIVIDEND_STOCK', 'qty': abs(float(val_1)), 'price': 0, 'total_val': 0, 'asset_type': asset_type}

            # Xử lý Mua/Bán thông thường
            qty = float(val_1)
            price = float(val_2) if val_2 else 0
            
            # Lấy Multiplier từ Registry (Tự động thích ứng với STOCK/CRYPTO/...)
            config = ASSET_REGISTRY.get(asset_type, {'multiplier': 1})
            multiplier = config.get('multiplier', 1)
            
            # Đặc thù Crypto: Nếu mua bằng USD, cần nhân thêm tỷ giá để lưu VNĐ vào Database (Theo logic Dashboard V1)
            # Nếu CEO muốn lưu DB bằng VNĐ để Dashboard tính toán nhanh:
            current_rate = config.get('default_rate', 1)
            total_val = abs(qty) * price * multiplier
            
            # Nếu là Crypto, quy đổi total_val sang VNĐ ngay tại bước Parser để đồng bộ Database
            if asset_type == 'CRYPTO':
                total_val *= current_rate

            return {
                'ticker': ticker, 
                'action': 'BUY' if qty > 0 else 'SELL',
                'qty': abs(qty), 'price': price, 
                'total_val': total_val, 'asset_type': asset_type
            }
        except Exception: return None
