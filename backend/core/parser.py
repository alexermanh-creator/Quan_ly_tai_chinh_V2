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

            # 1. CẬP NHẬT GIÁ (Giữ nguyên logic cập nhật)
            gm = re.match(r'^gia\s+([a-z0-9]+)\s+([\d\.,]+)$', raw)
            if gm:
                return {'ticker': gm.group(1).upper(), 'action': 'UPDATE_PRICE', 'price': float(gm.group(2).replace(',', '.')), 'asset_type': 'PRICE'}

            # 2. CHUYỂN TIỀN (Ví Mẹ <-> Ví Con)
            tm = re.match(r'^chuyen\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?\s*(stock|crypto|cash)$', raw)
            if tm:
                val = float(tm.group(1).replace(',', '.'))
                u = tm.group(2)
                if u == 'ty': val *= 1e9
                elif u in ['tr', 'trieu', 'triệu']: val *= 1e6
                target = tm.group(3).upper()
                return {'ticker': f'MOVE_{target}', 'action': 'TRANSFER', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': target}

            # 3. LỆNH MUA/BÁN (s = Stock, c = Crypto)
            # FIX: Đảm bảo multiplier chuẩn VNĐ để repository trừ tiền đúng
            if parts[0] in ['s', 'c']:
                asset_type = 'STOCK' if parts[0] == 's' else 'CRYPTO'
                ticker, qty, price = parts[1].upper(), float(parts[2]), float(parts[3])
                # Stock mặc định giá sàn x1000, Crypto mặc định tỷ giá x25000
                multiplier = 1000 if asset_type == 'STOCK' else (25000 if asset_type == 'CRYPTO' else 1)
                return {'ticker': ticker, 'action': 'BUY' if qty > 0 else 'SELL', 'qty': abs(qty), 'price': price, 'total_val': abs(qty)*price*multiplier, 'asset_type': asset_type}

            # 4. NẠP/RÚT VỐN GỐC (Chỉ tại Ví Mẹ)
            cm = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw)
            if cm:
                val = float(cm.group(2).replace(',', '.'))
                u = cm.group(3)
                if u == 'ty': val *= 1e9
                elif u in ['tr', 'trieu', 'triệu']: val *= 1e6
                return {'ticker': 'CASH', 'action': 'IN' if cm.group(1) == 'nap' else 'OUT', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': 'CASH'}
        except: return None
