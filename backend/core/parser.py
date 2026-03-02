import re

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw = text.lower().strip(); parts = raw.split()
            if not parts: return None

            # 1. Chuyển tiền (Mẹ <-> Con)
            tm = re.match(r'^chuyen\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?\s*(stock|crypto|cash)$', raw)
            if tm:
                val = float(tm.group(1).replace(',', '.')); u = tm.group(2)
                if u == 'ty': val *= 1e9
                elif u in ['tr', 'trieu', 'triệu']: val *= 1e6
                target = tm.group(3).upper()
                return {'ticker': f'MOVE_{target}', 'action': 'TRANSFER', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': target}

            # 2. Lệnh s/c (Rà soát đúng s=Stock, c=Crypto)
            if parts[0] in ['s', 'c']:
                asset_type = 'STOCK' if parts[0] == 's' else 'CRYPTO'
                ticker, qty, price = parts[1].upper(), float(parts[2]), float(parts[3])
                # Quy tắc nhân sếp yêu cầu: Stock x1000, Crypto x25000
                multiplier = 1000 if asset_type == 'STOCK' else 25000
                return {'ticker': ticker, 'action': 'BUY' if qty > 0 else 'SELL', 'qty': abs(qty), 'price': price, 'total_val': abs(qty)*price*multiplier, 'asset_type': asset_type}

            # 3. Nạp/Rút vốn gốc (Chỉ Ví Mẹ)
            cm = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw)
            if cm:
                val = float(cm.group(2).replace(',', '.')); u = cm.group(3)
                if u == 'ty': val *= 1e9
                elif u in ['tr', 'trieu', 'triệu']: val *= 1e6
                return {'ticker': 'CASH', 'action': 'IN' if cm.group(1) == 'nap' else 'OUT', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': 'CASH'}
        except: return None
