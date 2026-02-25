# backend/core/parser.py
from backend.core.registry import AssetResolver

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        """
        Cú pháp tối giản & Nâng cấp CTO:
        1. Mua/Bán: [Prefix] [Ticker] [Qty] [Price] -> S VPB 100 22.5
        2. Cổ tức cổ phiếu: [Prefix] [Ticker] [Qty] div -> S VPB 100 div
        3. Cổ tức tiền: [Prefix] [Ticker] [Amount] cash -> S VPB 2000000 cash
        """
        try:
            parts = text.lower().strip().split()
            if len(parts) < 3: return None
            
            # 1. Xử lý Prefix và Ticker
            if parts[0] in ['s', 'c']:
                input_resolver = f"{parts[0]} {parts[1]}"
                val_1 = parts[2]
                val_2 = parts[3] if len(parts) > 3 else None
            else:
                input_resolver = parts[0]
                val_1 = parts[1]
                val_2 = parts[2] if len(parts) > 2 else None

            asset_type, ticker = AssetResolver.resolve(input_resolver)

            # 2. Nhận diện loại lệnh đặc biệt
            # Cổ tức tiền: S VPB 2000000 cash
            if val_2 == 'cash':
                return {
                    'ticker': ticker, 'action': 'CASH_DIVIDEND',
                    'qty': 0, 'price': 0, 'total_val': abs(float(val_1)),
                    'asset_type': asset_type
                }
            
            # Cổ tức cổ phiếu: S VPB 100 div
            if val_2 == 'div':
                return {
                    'ticker': ticker, 'action': 'DIVIDEND_STOCK',
                    'qty': abs(float(val_1)), 'price': 0, 'total_val': 0,
                    'asset_type': asset_type
                }

            # 3. Lệnh Mua/Bán thông thường (S VPB 100 22.5)
            qty = float(val_1)
            price = float(val_2)
            action = 'BUY' if qty > 0 else 'SELL'
            
            return {
                'ticker': ticker, 'action': action,
                'qty': abs(qty), 'price': price, 
                'total_val': abs(qty) * price,
                'asset_type': asset_type
            }
        except Exception:
            return None

    @staticmethod
    def is_transaction_command(text):
        parts = text.strip().split()
        return len(parts) >= 3
