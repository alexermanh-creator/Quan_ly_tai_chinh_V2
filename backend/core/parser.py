# backend/core/parser.py
import re
from backend.core.registry import AssetResolver

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw_text = text.lower().strip()
            
            # --- 1. XỬ LÝ LỆNH NẠP/RÚT TIỀN TỶ ---
            # Regex hỗ trợ cả viết liền và viết cách: nap 10ty, nap10ty, nap 10 ty
            cash_match = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw_text)
            
            if cash_match:
                action_raw = cash_match.group(1)
                amount_str = cash_match.group(2).replace(',', '.')
                unit = cash_match.group(3)
                
                amount = float(amount_str)
                if unit == 'ty': 
                    amount *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: 
                    amount *= 1_000_000
                
                return {
                    'ticker': 'CASH',
                    'action': 'IN' if action_raw == 'nap' else 'OUT',
                    'qty': 1.0,
                    'price': amount,
                    'total_val': amount,
                    'asset_type': 'CASH'
                }

            # --- 2. XỬ LÝ LỆNH GIAO DỊCH TÀI SẢN (S HPG 1000 25) ---
            parts = raw_text.split()
            if len(parts) < 3: return None
            
            if parts[0] in ['s', 'c']:
                input_resolver = f"{parts[0]} {parts[1]}"
                val_1 = parts[2]
                val_2 = parts[3] if len(parts) > 3 else None
            else:
                input_resolver = parts[0]
                val_1 = parts[1]
                val_2 = parts[2] if len(parts) > 2 else None

            asset_type, ticker = AssetResolver.resolve(input_resolver)

            # Phân loại lệnh
            if val_2 == 'cash':
                return {'ticker': ticker, 'action': 'CASH_DIVIDEND', 'qty': 0, 'price': 0, 'total_val': abs(float(val_1)), 'asset_type': asset_type}
            
            if val_2 == 'div':
                return {'ticker': ticker, 'action': 'DIVIDEND_STOCK', 'qty': abs(float(val_1)), 'price': 0, 'total_val': 0, 'asset_type': asset_type}

            qty = float(val_1)
            price = float(val_2) if val_2 else 0
            multiplier = 1000 if asset_type == 'STOCK' else 1
            
            return {
                'ticker': ticker, 
                'action': 'BUY' if qty > 0 else 'SELL',
                'qty': abs(qty), 
                'price': price, 
                'total_val': abs(qty) * price * multiplier,
                'asset_type': asset_type
            }

        except Exception:
            return None
