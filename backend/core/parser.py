# backend/core/parser.py
import re
from backend.core.registry import AssetResolver

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw = text.lower().strip()
            parts = raw.split()
            # 1. Chuyển tiền
            tm = re.match(r'^chuyen\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?\s*(stock|crypto|cash)$', raw)
            if tm:
                val = float(tm.group(1).replace(',', '.'))
                u = tm.group(2)
                if u == 'ty': val *= 1e9
                elif u in ['tr', 'trieu', 'triệu']: val *= 1e6
                target = tm.group(3).upper()
                return {'ticker': f'MOVE_{target}', 'action': 'TRANSFER', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': target}
            # 2. Nạp rút
            cm = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw)
            if cm:
                val = float(cm.group(2).replace(',', '.'))
                u = cm.group(3)
                if u == 'ty': val *= 1e9
                elif u in ['tr', 'trieu', 'triệu']: val *= 1e6
                return {'ticker': 'CASH', 'action': 'IN' if cm.group(1) == 'nap' else 'OUT', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': 'CASH'}
            # 3. Mua bán
            asset_type, ticker = AssetResolver.resolve(raw)
            if ticker:
                qty, price = float(parts[1]), float(parts[2])
                m = 1000 if asset_type == 'STOCK' and price < 1000 else 1
                return {'ticker': ticker, 'action': 'BUY' if qty > 0 else 'SELL', 'qty': abs(qty), 'price': price, 'total_val': abs(qty)*price*m, 'asset_type': asset_type}
        except: return None
