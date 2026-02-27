# backend/core/parser.py
import re
from backend.core.registry import AssetResolver, ASSET_REGISTRY

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw = text.lower().strip()
            parts = raw.split()
            if not parts: return None

            if len(parts) == 3 and parts[0] == 'gia' and parts[1] == 'ex_rate':
                return {'action': 'SET_SETTING', 'key': 'EX_RATE', 'value': float(parts[2].replace(',', '.'))}

            tm = re.match(r'^chuyen\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?\s*(stock|crypto|other)$', raw)
            if tm:
                val = float(tm.group(1).replace(',', '.'))
                unit = tm.group(2)
                if unit == 'ty': val *= 1e9
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1e6
                return {'ticker': f'CAP_VON_{tm.group(3).upper()}', 'action': 'TRANSFER', 'qty': 1, 'price': val, 'total_val': val, 'asset_type': tm.group(3).upper()}

            cm = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw)
            if cm:
                val = float(cm.group(2).replace(',', '.'))
                unit = cm.group(3)
                if unit == 'ty': val *= 1e9
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1e6
                return {'ticker': 'CASH', 'action': 'IN' if cm.group(1) == 'nap' else 'OUT', 'qty': 1, 'price': val, 'total_val': val, 'asset_type': 'CASH'}

            # Mặc định xử lý Stock/Crypto mua bán
            asset_type, ticker = AssetResolver.resolve(raw)
            multiplier = 1000 if asset_type == 'STOCK' else 1
            qty = float(parts[2] if len(parts) > 2 else parts[1])
            price = float(parts[3] if len(parts) > 3 else parts[2])
            return {'ticker': ticker, 'action': 'BUY' if qty > 0 else 'SELL', 'qty': abs(qty), 'price': price, 'total_val': abs(qty) * price * multiplier, 'asset_type': asset_type}
        except: return None
