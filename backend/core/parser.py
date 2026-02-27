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

            # 1. CÀI ĐẶT TỶ GIÁ
            if len(parts) == 3 and parts[0] == 'gia' and parts[1] == 'ex_rate':
                return {'action': 'SET_SETTING', 'key': 'EX_RATE', 'value': float(parts[2].replace(',', '.'))}

            # 2. ĐIỀU CHUYỂN VỐN
            transfer_match = re.match(r'^chuyen\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?\s*(stock|crypto|other)$', raw)
            if transfer_match:
                val = float(transfer_match.group(1).replace(',', '.'))
                unit = transfer_match.group(2)
                if unit == 'ty': val *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1_000_000
                return {'ticker': f'CAP_VON_{transfer_match.group(3).upper()}', 'action': 'TRANSFER', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': transfer_match.group(3).upper()}

            # 3. NẠP/RÚT TIỀN (Ví Mẹ)
            cash_match = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw)
            if cash_match:
                val = float(cash_match.group(2).replace(',', '.'))
                unit = cash_match.group(3)
                if unit == 'ty': val *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1_000_000
                return {'ticker': 'CASH', 'action': 'IN' if cash_match.group(1) == 'nap' else 'OUT', 'qty': 1.0, 'price': val, 'total_val': val, 'asset_type': 'CASH'}

            # 4. GIAO DỊCH TÀI SẢN (Sửa lỗi nhân khống)
            asset_type, ticker = AssetResolver.resolve(raw)
            if not ticker: return None

            qty_idx = 2 if parts[0] in ['s', 'c'] else 1
            price_idx = qty_idx + 1
            if len(parts) <= price_idx: return None

            qty = float(parts[qty_idx].replace(',', '.'))
            price = float(parts[price_idx].replace(',', '.'))
            
            # TÍNH TOÁN GIÁ TRỊ THỰC TẾ TRƯỚC KHI LƯU
            if asset_type == 'STOCK':
                # Nếu giá sếp nhập > 1000 (ví dụ 28500), không nhân 1000 nữa
                multiplier = 1000 if price < 1000 else 1
                total_val = abs(qty) * price * multiplier
            elif asset_type == 'CRYPTO':
                # Crypto: SL * Giá USD * Tỷ giá VNĐ
                ex_rate = CommandParser.get_ex_rate()
                total_val = abs(qty) * price * ex_rate
            else:
                total_val = abs(qty) * price

            return {'ticker': ticker, 'action': 'BUY' if qty > 0 else 'SELL', 'qty': abs(qty), 'price': price, 'total_val': total_val, 'asset_type': asset_type}
        except Exception as e:
            print(f"⚠️ Lỗi Parser: {e}")
            return None
