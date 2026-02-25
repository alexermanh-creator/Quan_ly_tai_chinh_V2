# backend/core/parser.py
import re
from backend.core.registry import AssetResolver

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        """
        Nâng cấp CTO: Xử lý linh hoạt nap/rut, tỷ/tr và lệnh giao dịch tài sản.
        """
        try:
            raw_text = text.lower().strip()
            
            # --- 1. XỬ LÝ LỆNH NẠP/RÚT (nap 10ty, nap 100 tr, rut 500tr...) ---
            # Regex bóc tách: [nap/rut] [số] [đơn vị tỷ/tr/trieu]
            cash_match = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw_text)
            
            if cash_match:
                action_raw = cash_match.group(1)
                # Thay dấu phẩy bằng dấu chấm để chuyển đổi float chuẩn
                amount_str = cash_match.group(2).replace(',', '.')
                unit = cash_match.group(3)
                
                amount = float(amount_str)
                
                # Quy đổi đơn vị thông minh
                if unit == 'ty': 
                    amount *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: 
                    amount *= 1_000_000
                
                return {
                    'ticker': 'CASH',
                    'action': 'IN' if action_raw == 'nap' else 'OUT',
                    'qty': 1,
                    'price': amount,
                    'total_val': amount,
                    'asset_type': 'CASH'
                }

            # --- 2. XỬ LÝ LỆNH GIAO DỊCH TÀI SẢN (S VPB 100 22.5, S VPB 100 div...) ---
            parts = raw_text.split()
            if len(parts) < 3: return None
            
            # Xử lý Prefix (s vpb... hoặc vpb...)
            if parts[0] in ['s', 'c']:
                input_resolver = f"{parts[0]} {parts[1]}"
                val_1 = parts[2]
                val_2 = parts[3] if len(parts) > 3 else None
            else:
                input_resolver = parts[0]
                val_1 = parts[1]
                val_2 = parts[2] if len(parts) > 2 else None

            asset_type, ticker = AssetResolver.resolve(input_resolver)

            # A. Cổ tức tiền (S VPB 2000000 cash)
            if val_2 == 'cash':
                return {
                    'ticker': ticker, 'action': 'CASH_DIVIDEND',
                    'qty': 0, 'price': 0, 'total_val': abs(float(val_1)),
                    'asset_type': asset_type
                }
            
            # B. Cổ tức cổ phiếu (S VPB 100 div)
            if val_2 == 'div':
                return {
                    'ticker': ticker, 'action': 'DIVIDEND_STOCK',
                    'qty': abs(float(val_1)), 'price': 0, 'total_val': 0,
                    'asset_type': asset_type
                }

            # C. Lệnh Mua/Bán thông thường (S VPB 100 22.5)
            qty = float(val_1)
            price = float(val_2) if val_2 else 0
            
            # Hệ số nhân cho Chứng khoán VN (thường nhập giá 22.5 cho 22,500đ)
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

    @staticmethod
    def is_transaction_command(text):
        # Trả về True nếu khớp lệnh nạp tiền hoặc lệnh giao dịch tài sản
        raw_text = text.lower().strip()
        if re.match(r'^(nap|rut)', raw_text): return True
        return len(raw_text.split()) >= 3
