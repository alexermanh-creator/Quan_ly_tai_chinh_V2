# backend/core/parser.py
import re
# Đảm bảo bạn đã có file registry.py để import
try:
    from backend.core.registry import AssetResolver, ASSET_REGISTRY
except ImportError:
    # Fallback nếu registry chưa sẵn sàng (để debug giai đoạn 1)
    class AssetResolver:
        @staticmethod
        def resolve(text): 
            parts = text.split()
            return ('STOCK' if parts[0] == 's' else 'CRYPTO', parts[1].upper())
    ASSET_REGISTRY = {'STOCK': {'multiplier': 1000}, 'CRYPTO': {'multiplier': 1, 'default_rate': 25000}}

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw_text = text.lower().strip()
            
            # 1. XỬ LÝ LỆNH NẠP/RÚT TIỀN (Giữ nguyên logic của CEO)
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

            # 2. XỬ LÝ GIAO DỊCH TÀI SẢN
            parts = raw_text.split()
            if len(parts) < 2: return None
            
            if parts[0] in ['s', 'c']:
                input_resolver = f"{parts[0]} {parts[1]}"
                val_1 = parts[2]
                val_2 = parts[3] if len(parts) > 3 else None
            else:
                input_resolver = f"s {parts[0]}" if len(parts[0]) == 3 and parts[0].isalpha() else parts[0]
                val_1 = parts[1]
                val_2 = parts[2] if len(parts) > 2 else None

            asset_type, ticker = AssetResolver.resolve(input_resolver)

            # Xử lý Cổ tức
            if asset_type == 'STOCK':
                if val_2 == 'cash':
                    return {'ticker': ticker, 'action': 'CASH_DIVIDEND', 'qty': 0, 'price': 0, 'total_val': abs(float(val_1)), 'asset_type': asset_type}
                if val_2 == 'div':
                    return {'ticker': ticker, 'action': 'DIVIDEND_STOCK', 'qty': abs(float(val_1)), 'price': 0, 'total_val': 0, 'asset_type': asset_type}

            # Mua/Bán thông thường
            qty = float(val_1.replace(',', '.'))
            price = float(val_2.replace(',', '.')) if val_2 else 0
            
            config = ASSET_REGISTRY.get(asset_type, {'multiplier': 1})
            multiplier = config.get('multiplier', 1)
            total_val = abs(qty) * price * multiplier
            
            # Quy đổi VNĐ cho Crypto
            if asset_type == 'CRYPTO':
                total_val *= config.get('default_rate', 25000)

            return {
                'ticker': ticker, 
                'action': 'BUY' if qty > 0 else 'SELL',
                'qty': abs(qty), 'price': price, 
                'total_val': total_val, 'asset_type': asset_type
            }
        except Exception: return None
