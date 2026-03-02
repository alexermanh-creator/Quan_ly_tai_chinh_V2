# backend/core/parser.py
import re

def parse_currency(text):
    text = text.lower().replace(',', '').strip()
    # Quy đổi đơn vị
    multiplier = 1
    if 'ty' in text: multiplier = 1_000_000_000
    elif 'trieu' in text or 'tr' in text: multiplier = 1_000_000
    
    # Trích xuất số
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    if not numbers: return 0
    return float(numbers[0]) * multiplier

def parse_trade_command(text):
    text = text.strip().lower()
    pattern = r'^(s|c|k)\s+([a-zA-Z0-9]+)\s+(-?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)$'
    match = re.match(pattern, text)
    if not match: return None
    
    w_map = {'s': 'STOCK', 'c': 'CRYPTO', 'k': 'OTHER'}
    wallet_type = w_map[match.group(1)]
    symbol = match.group(2).upper()
    quantity = float(match.group(3))
    price = float(match.group(4))
    return wallet_type, symbol, quantity, price
