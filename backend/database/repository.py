# backend/database/repository.py
from backend.database.db_manager import db

class Repository:
    @staticmethod
    def format_smart_currency(value):
        """Định dạng tiền tệ: Tỷ, tr, đ đúng chuẩn CEO"""
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

        # KIỂM TRA DÒNG TIỀN (Rule: Chỉ được mua nếu đủ tiền)
        if type in ['BUY', 'OUT', 'WITHDRAW']:
            available = Repository.get_available_cash(user_id)
            if available < total_value:
                # Trả về lỗi để Bot phản hồi cho người dùng
                return False, f"❌ Không đủ tiền! Số dư hiện tại: {Repository.format_smart_currency(available)}"

        with db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Lưu lịch sử
            cursor.execute('''
                INSERT INTO transactions (user_id, ticker, asset_type, qty, price, total_value, type, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ''', (user_id, ticker, asset_type, qty, price, total_value, type))

            # 2. Cập nhật Portfolio
            if asset_type != 'CASH':
                cursor.execute("SELECT total_qty, avg_price FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, ticker))
                row = cursor.fetchone()
                
                current_qty = row['total_qty'] if row else 0
                current_avg_price = row['avg_price'] if row else 0
                
                new_qty = current_qty
                if type == 'BUY' or type == 'DIVIDEND_STOCK':
                    new_qty = current_qty + qty
                elif type == 'SELL':
                    new_qty = current_qty - qty

                # Tính lại giá vốn bình quân
                new_avg_price = current_avg_price
                if type == 'BUY' and new_qty > 0:
                    new_avg_price = ((current_qty * current_avg_price) + total_value) / new_qty
                elif type == 'DIVIDEND_STOCK' and new_qty > 0:
                    new_avg_price = (current_qty * current_avg_price) / new_qty

                cursor.execute('''
                    INSERT INTO portfolio (user_id, ticker, asset_type, total_qty, avg_price, last_updated)
                    VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
                    ON CONFLICT(user_id, ticker) DO UPDATE SET 
                        total_qty = excluded.total_qty,
                        avg_price = excluded.avg_price,
                        last_updated = excluded.last_updated
                ''', (user_id, ticker, asset_type, new_qty, new_avg_price))

            conn.commit()
            return True, "✅ Ghi nhận thành công."

    # ... các hàm khác giữ nguyên ...
