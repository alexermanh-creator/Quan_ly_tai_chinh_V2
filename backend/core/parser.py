# backend/core/parser.py
import re
from backend.database.db_manager import db
from backend.core.registry import AssetResolver, ASSET_REGISTRY

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw = text.lower().strip()
            parts = raw.split()
            if not parts: return None

            # 1. LỆNH ĐIỀU CHUYỂN VỐN (Thêm CASH vào đích đến)
            transfer_match = re.match(r'^chuyen\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?\s*(stock|crypto|other|cash)$', raw)
            if transfer_match:
                val = float(transfer_match.group(1).replace(',', '.'))
                unit = transfer_match.group(2)
                if unit == 'ty': val *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1_000_000
                
                target = transfer_match.group(3).upper()
                return {
                    'ticker': f'MOVE_{target}', 
                    'action': 'TRANSFER', 
                    'qty': 1.0, 'price': val, 'total_val': val, 
                    'asset_type': target
                }

            # ... (Giữ nguyên logic NAP/RUT và GIA EX_RATE cũ) ...
            cash_match = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw)
            if cash_match:
                action = cash_match.group(1)
                val = float(cash_match.group(2).replace(',', '.'))
                unit = cash_match.group(3)
                if unit == 'ty': val *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1_000_000
                return {'ticker': 'CASH', 'action': 'IN' if action == 'nap' else 'OUT', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': 'CASH'}

            # 4. GIAO DỊCH TÀI SẢN
            asset_type, ticker = AssetResolver.resolve(raw)
            if not ticker: return None
            qty_idx = 2 if parts[0] in ['s', 'c'] else 1
            price_idx = qty_idx + 1
            qty = float(parts[qty_idx].replace(',', '.'))
            price = float(parts[price_idx].replace(',', '.'))
            
            # Tính multiplier: Stock VN luôn x1000
            m = 1000 if asset_type == 'STOCK' else 1
            return {'ticker': ticker, 'action': 'BUY' if qty > 0 else 'SELL', 'qty': abs(qty), 'price': price, 'total_val': abs(qty) * price * m, 'asset_type': asset_type}
        except: return None
