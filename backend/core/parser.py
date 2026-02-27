# backend/core/parser.py
import re
from backend.core.registry import AssetResolver, ASSET_REGISTRY

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        try:
            raw_text = text.lower().strip()
            parts = raw_text.split()
            if not parts: return None

            # 1. LỆNH CÀI ĐẶT TỶ GIÁ (Ưu tiên số 1)
            # Cú pháp: gia ex_rate 25500
            if len(parts) == 3 and parts[0] == 'gia' and parts[1] == 'ex_rate':
                return {
                    'action': 'SET_SETTING',
                    'key': 'EX_RATE',
                    'value': float(parts[2].replace(',', '.'))
                }

            # 2. LỆNH NẠP/RÚT TIỀN
            cash_match = re.match(r'^(nap|rut)\s*([\d\.,]+)\s*(ty|tr|trieu|triệu)?$', raw_text)
            if cash_match:
                action_raw = cash_match.group(1)
                amount_str = cash_match.group(2).replace(',', '.')
                unit = cash_match.group(3)
                amount = float(amount_str)
                if unit == 'ty': amount *= 1_000_000_000
                elif unit in ['tr', 'trieu', 'triệu']: amount *= 1_000_000
                
                return {
                    'ticker': 'CASH', 'action': 'IN' if action_raw == 'nap' else 'OUT',
                    'qty': 1.0, 'price': amount, 'total_val': amount, 'asset_type': 'CASH'
                }

            # ... logic xử lý S/C và giao dịch giữ nguyên ...
