# backend/services/import_service.py
import json
from backend.database.repository import DatabaseRepo

class ImportService:
    def __init__(self):
        self.db = DatabaseRepo()

    def process_import_file(self, json_data):
        try:
            # 1. Dọn sạch DB cũ
            self.db.clear_all_data()

            # Lấy tỷ giá để tính toán giá trị Crypto
            r_row = self.db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
            rate = float(r_row['value']) if r_row else 25000.0

            # 2. Xử lý Lịch sử (Nếu có)
            for tx in json_data.get('history', []):
                self.db.insert_raw_transaction(tx['wallet_id'], tx['type'], tx['amount'], tx['date'], tx.get('note', ''))

            # 3. Phục hồi Ví & Danh mục
            for w_id, w_data in json_data.get('wallets', {}).items():
                net_capital = w_data['total_in'] - w_data['total_out']
                current_cash = w_data['current_cash']
                
                asset_value_vnd = 0
                total_cost_basis_vnd = 0 # Đã thêm biến lưu Tổng Giá Vốn

                # Duyệt qua các tài sản đang cầm thuộc ví này
                for h in json_data.get('holdings', []):
                    if h['wallet_id'] == w_id:
                        market_price = h['market_price']
                        avg_price = h.get('average_price', market_price)
                        
                        if w_id == 'STOCK' and market_price < 1000: 
                            market_price *= 1000
                            if avg_price < 1000: avg_price *= 1000
                        
                        val_vnd = h['qty'] * market_price * (rate if w_id == 'CRYPTO' else 1)
                        cost_basis_vnd = h['qty'] * avg_price * (rate if w_id == 'CRYPTO' else 1)
                        
                        asset_value_vnd += val_vnd
                        total_cost_basis_vnd += cost_basis_vnd # Cộng dồn Giá Vốn
                        
                        # Nạp danh mục
                        self.db.execute_query(
                            "INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price, cost_basis_vnd) VALUES (?, ?, ?, ?, ?, ?)",
                            (w_id, h['symbol'].upper(), h['qty'], avg_price, market_price, cost_basis_vnd)
                        )

                # Cập nhật Ví gốc
                self.db.force_update_wallet(w_id, current_cash, w_data['total_in'], w_data['total_out'])

                # 4. Thuật toán bù trừ: Ghi Lãi/Lỗ Quá Khứ
                if w_id in ['STOCK', 'CRYPTO']:
                    # ✅ FIX LỖI TÍNH ĐÚP: Dùng tổng Giá Vốn (cost_basis) thay vì Giá Thị Trường (asset_value)
                    historical_pnl = (current_cash + total_cost_basis_vnd) - net_capital
                    if historical_pnl != 0:
                        self.db.insert_historical_pnl(w_id, historical_pnl, f"Lãi/Lỗ dồn tích trước {json_data.get('version', '3.4')}")

            return True, "✅ Khôi phục thành công! Toàn bộ sổ sách Excel đã được tích hợp."
        except Exception as e:
            return False, f"❌ Lỗi cấu trúc file Import: {str(e)}"
