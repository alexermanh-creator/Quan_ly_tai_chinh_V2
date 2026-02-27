# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def format_smart_currency(value):
        abs_val = abs(value)
        sign = "-" if value < 0 else ""
        if abs_val >= 1_000_000_000:
            return f"{sign}{abs_val / 1_000_000_000:.2f} tỷ"
        elif abs_val >= 1_000_000:
            return f"{sign}{abs_val / 1_000_000:.1f}tr"
        return f"{sign}{abs_val:,.0f}đ"

    @staticmethod
    def save_transaction(user_id, ticker, asset_type, qty, price, total_value, type):
        ticker = ticker.upper()
        asset_type = asset_type.upper()
        type = type.upper()

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # --- LOGIC QUẢN TRỊ DÒNG TIỀN ĐA LỚP ---

            # A. Nếu là lệnh CHUYỂN VỐN (Ví Mẹ -> Ví Con)
            if type == 'TRANSFER':
                mom_cash = Repository.get_available_cash(user_id, 'CASH')
                if mom_cash < total_value:
                    return False, f"❌ Ví Mẹ không đủ tiền để cấp vốn! (Hiện có: {Repository.format_smart_currency(mom_cash)})"
                
                # 1. Ghi nhận lệnh RÚT từ Ví Mẹ
                cursor.execute('''
                    INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date)
                    VALUES (?, ?, 'CASH', 1, ?, ?, 'TRANSFER_OUT', datetime('now', 'localtime'))
                ''', (user_id, f"SANG_{asset_type}", total_value, total_value))
                
                # 2. Ghi nhận lệnh NẠP vào Ví Con
                cursor.execute('''
                    INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date)
                    VALUES (?, ?, ?, 1, ?, ?, 'TRANSFER_IN', datetime('now', 'localtime'))
                ''', (user_id, ticker, asset_type, total_value, total_value))

            # B. Nếu là lệnh MUA (Kiểm tra sức mua của Ví Con)
            elif type == 'BUY':
                buying_power = Repository.get_available_cash(user_id, asset_type)
                if buying_power < total_value:
                    return False, f"❌ Ví {asset_type} không đủ hạn mức! Sếp hãy 'chuyen' thêm vốn từ Ví Mẹ."
                
                cursor.execute('''
                    INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                ''', (user_id, ticker, asset_type, qty, price, total_value, type))

            # C. Các lệnh khác (Nạp/Rút trực tiếp vào Ví Mẹ hoặc ví cụ thể)
            else:
                cursor.execute('''
                    INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                ''', (user_id, ticker, asset_type, qty, price, total_value, type))

            # --- CẬP NHẬT PORTFOLIO (Giữ nguyên logic cũ) ---
            if asset_type != 'CASH' and type not in ['TRANSFER']:
                # ... (Logic cập nhật số dư/giá vốn portfolio như sếp đã gửi) ...
                pass 

            conn.commit()
            return True, "✅ Ghi nhận thành công."

    @staticmethod
    def get_available_cash(user_id, asset_type):
        """Tính tiền mặt khả dụng riêng biệt cho từng Ví"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Logic: Tiền khả dụng = (Nạp + Bán + Nhận Chuyển) - (Rút + Mua + Chuyển Đi)
            cursor.execute('''
                SELECT SUM(CASE 
                    WHEN type IN ('IN', 'DEPOSIT', 'SELL', 'CASH_DIVIDEND', 'TRANSFER_IN') THEN total_value
                    WHEN type IN ('OUT', 'WITHDRAW', 'BUY', 'TRANSFER_OUT') THEN -total_value
                    ELSE 0 END) as balance
                FROM transactions WHERE user_id = ? AND asset_type = ?
            ''', (user_id, asset_type))
            result = cursor.fetchone()
            return result['balance'] if result and result['balance'] else 0
