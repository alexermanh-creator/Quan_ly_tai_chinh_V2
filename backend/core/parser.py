# backend/core/parser.py
from backend.core.registry import AssetResolver

class CommandParser:
    @staticmethod
    def parse_transaction(text):
        """
        Cú pháp tối giản: [Prefix] [Ticker] [Qty] [Price]
        Ví dụ: 
        S VPB 100 22.5  -> Mua 100 VPB giá 22.5
        S VPB -50 23.0  -> Bán 50 VPB giá 23.0
        C BTC 0.01 95000 -> Mua 0.01 BTC giá 95000
        """
        try:
            parts = text.strip().split()
            
            # Kiểm tra tối thiểu phải có 3 phần (Nếu ko dùng prefix) hoặc 4 phần (Có prefix)
            if len(parts) < 3:
                return None
            
            # 1. Xác định Tiền tố và Ticker
            first_part = parts[0].upper()
            if first_part in ['S', 'C']:
                # Có tiền tố: S VPB 100 50
                prefix_and_ticker = f"{parts[0]} {parts[1]}"
                qty_idx = 2
                price_idx = 3
            else:
                # Không tiền tố: VPB 100 50
                prefix_and_ticker = parts[0]
                qty_idx = 1
                price_idx = 2

            # Gọi Resolver để lấy loại tài sản và mã sạch
            asset_type, ticker = AssetResolver.resolve(prefix_and_ticker)
            
            # 2. Lấy Số lượng và Giá
            qty = float(parts[qty_idx])
            price = float(parts[price_idx])
            
            # 3. Định nghĩa hành động dựa trên dấu của Số lượng
            # Dương là BUY, Âm là SELL
            action = 'BUY' if qty > 0 else 'SELL'
            
            # Luôn lưu số lượng vào DB là số dương để Engine tính toán thống nhất
            final_qty = abs(qty)
            
            return {
                'ticker': ticker,
                'action': action,
                'qty': final_qty,
                'price': price,
                'total_val': final_qty * price,
                'asset_type': asset_type
            }
        except Exception:
            return None

    @staticmethod
    def is_transaction_command(text):
        """
        Kiểm tra xem tin nhắn có phải lệnh giao dịch không.
        Cấu trúc: Có ít nhất 2 khoảng trắng (tương đương 3 phần dữ liệu)
        """
        parts = text.strip().split()
        return len(parts) >= 3 and any(char.isdigit() for char in text)
