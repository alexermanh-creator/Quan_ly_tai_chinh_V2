# backend/core/parser.py
import re
from backend.core.registry import AssetResolver, ASSET_REGISTRY

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw = text.lower().strip()
            parts = raw.split()
            if not parts: 
                return None

            # 1. LỆNH CÀI ĐẶT TỶ GIÁ (Cú pháp: gia ex_rate 25500)
            if len(parts) == 3 and parts[0] == 'gia' and parts[1] == 'ex_rate':
                return {
                    'action': 'SET_SETTING', 
                    'key': 'EX_RATE', 
                    'value': float(parts[2].replace(',', '.'))
                }

            # 2. LỆNH ĐIỀU CHUYỂN VỐN (Ví dụ: chuyen 500tr stock)
            transfer_match = re.match(r'^chuyen\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?\s*(stock|crypto|other)$', raw)
            if transfer_match:
                val = float(transfer_match.group(1).replace(',', '.'))
                unit = transfer_match.group(2)
                if unit == 'ty': val *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1_000_000
                
                target_wallet = transfer_match.group(3).upper()
                return {
                    'ticker': f'CAP_VON_{target_wallet}', 
                    'action': 'TRANSFER', 
                    'qty': 1.0, 
                    'price': val, 
                    'total_val': val, 
                    'asset_type': target_wallet
                }

            # 3. LỆNH NẠP/RÚT TIỀN (Vào Ví Mẹ - CASH)
            cash_match = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw)
            if cash_match:
                action_raw = cash_match.group(1)
                val = float(cash_match.group(2).replace(',', '.'))
                unit = cash_match.group(3)
                if unit == 'ty': val *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: val *= 1_000_000
                
                return {
                    'ticker': 'CASH', 
                    'action': 'IN' if action_raw == 'nap' else 'OUT', 
                    'qty': 1.0, 
                    'price': val, 
                    'total_val': val, 
                    'asset_type': 'CASH'
                }

            # 4. LỆNH GIAO DỊCH TÀI SẢN (Stock/Crypto)
            # Cú pháp: [Ticker] [Số lượng] [Giá] hoặc [S/C] [Ticker] [SL] [Giá]
            asset_type, ticker = AssetResolver.resolve(raw)
            if not ticker:
                return None

            # Xác định hệ số nhân (Stock VN nhân 1000)
            config = ASSET_REGISTRY.get(asset_type, {'multiplier': 1})
            multiplier = config.get('multiplier', 1)

            # Lấy SL và Giá từ các phần tử cuối của lệnh
            # HPG 1000 28.5 -> parts[1]=1000, parts[2]=28.5
            # S HPG 1000 28.5 -> parts[2]=1000, parts[3]=28.5
            qty_idx = 2 if parts[0] in ['s', 'c'] else 1
            price_idx = qty_idx + 1

            if len(parts) <= price_idx:
                return None

            qty = float(parts[qty_idx].replace(',', '.'))
            price = float(parts[price_idx].replace(',', '.'))
            
            return {
                'ticker': ticker, 
                'action': 'BUY' if qty > 0 else 'SELL', 
                'qty': abs(qty), 
                'price': price, 
                'total_val': abs(qty) * price * multiplier, 
                'asset_type': asset_type
            }

        except Exception as e:
            # Đây là khối lệnh quan trọng bị thiếu dẫn đến lỗi Syntax
            print(f"⚠️ Lỗi Parser: {e}")
            return None
