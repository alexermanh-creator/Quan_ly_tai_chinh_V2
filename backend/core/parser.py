# backend/core/parser.py
import re

def parse_currency(text_value):
    """Hỗ trợ gõ 500k, 5m, 1b... thành số"""
    text_value = str(text_value).lower().replace(',', '')
    if 'k' in text_value: return float(text_value.replace('k', '')) * 1000
    if 'm' in text_value: return float(text_value.replace('m', '')) * 1000000
    if 'b' in text_value: return float(text_value.replace('b', '')) * 1000000000
    return float(text_value)

def parse_trade_command(text):
    """Phân tích lệnh mua bán s/c"""
    parts = text.split()
    if len(parts) < 4: return None
    
    cmd_type = parts[0].lower()
    symbol = parts[1].upper()
    
    try:
        qty = float(parts[2].replace(',', ''))
        price = parse_currency(" ".join(parts[3:]))
    except ValueError:
        return None
        
    w_type = 'STOCK' if cmd_type == 's' else 'CRYPTO'
    return w_type, symbol, qty, price

def parse_dividend_command(text):
    """
    Phân tích lệnh cổ tức (Plug & Play)
    Cú pháp: ct tien [MÃ] [TIỀN] hoặc ct cp [MÃ] [SỐ LƯỢNG]
    """
    parts = text.lower().strip().split()
    if len(parts) < 4 or parts[0] != 'ct': 
        return None
        
    action_type = parts[1]
    if action_type not in ['tien', 'cp']: 
        return None
        
    symbol = parts[2].upper()
    
    try:
        # Tái sử dụng parse_currency để sếp gõ "ct tien VPB 500k" vẫn nhận diện được
        value = parse_currency(" ".join(parts[3:]))
        return action_type, symbol, value
    except ValueError:
        return None
