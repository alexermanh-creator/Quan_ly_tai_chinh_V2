# backend/modules/wallet.py
from backend.database.repository import DatabaseRepo

class WalletModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def parse_amount(self, amount_str):
        """Chuyển đổi văn bản '10 ty' hoặc '500 trieu' thành con số thực"""
        try:
            amount_str = amount_str.lower().replace(',', '').strip()
            multiplier = 1
            if 'ty' in amount_str or 'tỷ' in amount_str:
                multiplier = 1_000_000_000
                val = amount_str.replace('ty', '').replace('tỷ', '').strip()
            elif 'tr' in amount_str or 'trieu' in amount_str or 'triệu' in amount_str:
                multiplier = 1_000_000
                val = amount_str.replace('trieu', '').replace('triệu', '').replace('tr', '').strip()
            else:
                val = amount_str
            
            return float(val) * multiplier
        except:
            return None

    def handle_fund_command(self, command_text):
        """
        Xử lý các lệnh:
        - nap [số tiền]
        - rut [số tiền]
        - chuyen [ví] [số tiền]
        - thu [ví] [số tiền]
        """
        parts = command_text.lower().split()
        if len(parts) < 2:
            return "❌ Cú pháp không đủ thông tin."

        action = parts[0]
        
        try:
            if action in ['nap', 'rut']:
                # nap 10 ty / rut 500 trieu
                amount = self.parse_amount(" ".join(parts[1:]))
                if amount is None: return "❌ Số tiền không hợp lệ."
                
                final_amount = amount if action == 'nap' else -amount
                self.db.update_cash_balance(final_amount, action.upper())
                return f"✅ Đã {action} {amount:,.0f} đ vào Ví Mẹ (CASH)."

            elif action in ['chuyen', 'thu']:
                # chuyen stock 1 ty / thu crypto 500 trieu
                if len(parts) < 3: return "❌ Vui lòng chỉ định ví (stock/crypto) và số tiền."
                
                target_wallet = parts[1].upper()
                if target_wallet not in ['STOCK', 'CRYPTO']:
                    return "❌ Chỉ hỗ trợ ví STOCK hoặc CRYPTO."
                
                amount = self.parse_amount(" ".join(parts[2:]))
                if amount is None: return "❌ Số tiền không hợp lệ."

                if action == 'chuyen':
                    # Mẹ -> Con
                    self.db.transfer_funds('CASH', target_wallet, amount)
                    return f"✅ Đã cấp vốn {amount:,.0f} đ từ Ví Mẹ -> Ví {target_wallet}."
                else:
                    # Con -> Mẹ (Thu hồi vốn + lãi)
                    self.db.transfer_funds(target_wallet, 'CASH', amount)
                    return f"✅ Đã thu hồi {amount:,.0f} đ từ Ví {target_wallet} -> Ví Mẹ."

        except Exception as e:
            return f"❌ Lỗi xử lý dòng tiền: {str(e)}"
        
        return None
