import re

def parse_trade_command(text):
    """
    Bóc tách lệnh mua bán cổ phiếu/crypto.
    Hỗ trợ: s HAH 400 80 (Mua) hoặc s HAH -400 80 (Bán)
    Trả về: (loại_ví, mã, số_lượng, giá) hoặc None nếu sai cú pháp
    """
    text = text.strip().lower()
    
    # Regex bắt cú pháp: chữ s/c + khoảng trắng + chữ/số (mã) + khoảng trắng + số (âm/dương) + khoảng trắng + số
    pattern = r'^(s|c)\s+([a-zA-Z0-9]+)\s+(-?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)$'
    match = re.match(pattern, text)
    
    if not match:
        return None
        
    wallet_type = 'STOCK' if match.group(1) == 's' else 'CRYPTO'
    symbol = match.group(2).upper()
    quantity = float(match.group(3))
    price = float(match.group(4))
    
    return wallet_type, symbol, quantity, price

def parse_fund_command(text):
    """
    Bóc tách lệnh nạp/rút tiền mẹ, hoặc chuyển tiền ví con.
    Ví dụ: nap 10 ty, rut 500 trieu, chuyen stock 1 ty
    """
    # Xử lý quy đổi chữ thành số (ty -> * 1_000_000_000, trieu -> * 1_000_000)
    # Phần này sẽ được nâng cấp logic chi tiết ở các module xử lý sau
    return text.strip().lower().split()
