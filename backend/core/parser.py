# backend/core/parser.py
import re
from backend.database.db_manager import db
from backend.core.registry import AssetResolver, ASSET_REGISTRY

class CommandParser:
    @staticmethod
    def get_ex_rate():
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'EX_RATE'")
            res = cursor.fetchone()
            return float(res[0]) if res else 25000.0

    @staticmethod
    def parse_transaction(text):
        try:
            raw = text.lower().strip()
            parts = raw.split()
            if not parts: return None

            # 1. ĐIỀU CHUYỂN VỐN (Mẹ <-> Con)
            tm = re.match(r'^chuyen\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?\s*(stock|crypto|other|cash)$', raw)
            if tm:
                val = float(tm.group(1).replace(',', '.'))
                unit = tm.group(2)
                if unit == 'ty': val *= 1e9
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1e6
                target = tm.group(3).upper()
                return {'ticker': f'MOVE_{target}', 'action': 'TRANSFER', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': target}

            # 2. LỆNH NẠP/RÚT NGOẠI BIÊN (Nạp tiền vào hệ thống)
            cm = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw)
            if cm:
                val = float(cm.group(2).replace(',', '.'))
                unit = cm.group(3)
                if unit == 'ty': val *= 1e9
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1e6
                return {'ticker': 'CASH', 'action': 'IN' if cm.group(1) == 'nap' else 'OUT', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': 'CASH'}

            # 3. GIAO DỊCH TÀI SẢN (Stock/Crypto)
            asset_type, ticker = AssetResolver.resolve(raw)
            if not ticker: return None
            qty_idx = 2 if parts[0] in ['s', 'c'] else 1
            price_idx = qty_idx + 1
            qty = float(parts[qty_idx].replace(',', '.'))
            price = float(parts[price_idx].replace(',', '.'))
            
            # Logic Chuyên gia: Lưu giá trị thực tế VNĐ vào DB
            if asset_type == 'STOCK':
                m = 1000 if price < 1000 else 1
                total_val = abs(qty) * price * m
            elif asset_type == 'CRYPTO':
                total_val = abs(qty) * price * CommandParser.get_ex_rate()
            else:
                total_val = abs(qty) * price

            return {'ticker': ticker, 'action': 'BUY' if qty > 0 else 'SELL', 'qty': abs(qty), 'price': price, 'total_val': total_val, 'asset_type': asset_type}
        except: return None
