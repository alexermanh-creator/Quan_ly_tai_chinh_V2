# backend/core/parser.py
import re
from backend.core.registry import AssetResolver

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw = text.lower().strip()
            parts = raw.split()
            if not parts: return None

            # 1. Lệnh CHUYỂN TIỀN (Ví dụ: chuyen 2ty stock)
            tm = re.match(r'^chuyen\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?\s*(stock|crypto|cash)$', raw)
            if tm:
                val = float(tm.group(1).replace(',', '.'))
                u = tm.group(2)
                if u == 'ty': val *= 1e9
                elif u in ['tr', 'trieu', 'triệu']: val *= 1e6
                target = tm.group(3).upper()
                return {'ticker': f'MOVE_{target}', 'action': 'TRANSFER', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': target}

            # 2. Lệnh NẠP/RÚT VỐN GỐC (Chỉ tác động Ví Mẹ)
            cm = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw)
            if cm:
                val = float(cm.group(2).replace(',', '.'))
                u = cm.group(3)
                if u == 'ty': val *= 1e9
                elif u in ['tr', 'trieu', 'triệu']: val *= 1e6
                return {'ticker': 'CASH', 'action': 'IN' if cm.group(1) == 'nap' else 'OUT', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': 'CASH'}

            # 3. Lệnh GIAO DỊCH BỌC THÉP (s = Stock, c = Crypto)
            # Cấu trúc: s hpg 1000 30 hoặc c btc 0.1 50000
            if parts[0] in ['s', 'c']:
                asset_type = 'STOCK' if parts[0] == 's' else 'CRYPTO'
                ticker = parts[1].upper()
                qty = float(parts[2].replace(',', '.'))
                price = float(parts[3].replace(',', '.'))
                
                # Tỷ giá bọc thép
                if asset_type == 'STOCK':
                    multiplier = 1000 if price < 1000 else 1 # s vpb 1000 30 -> 30,000đ
                else:
                    multiplier = 25000 # Tỷ giá USD mặc định cho Crypto
                
                total_val = abs(qty) * price * multiplier
                return {
                    'ticker': ticker, 
                    'action': 'BUY' if qty > 0 else 'SELL', 
                    'qty': abs(qty), 
                    'price': price, 
                    'total_val': total_val, 
                    'asset_type': asset_type
                }
        except: return None
