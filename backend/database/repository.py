import sqlite3
import os
import sys

# Đảm bảo import được config từ thư mục gốc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config import DB_PATH
from .models import SCHEMA

class DatabaseRepo:
    def __init__(self):
        self.db_path = DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            cursor = conn.cursor()
            # Khởi tạo 3 ví mặc định
            cursor.execute("INSERT OR IGNORE INTO wallets (id) VALUES ('CASH'), ('STOCK'), ('CRYPTO')")
            conn.commit()

    def execute_query(self, query, params=(), fetch_one=False, fetch_all=False):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch_one:
                row = cursor.fetchone()
                return dict(row) if row else None
            if fetch_all:
                return [dict(row) for row in cursor.fetchall()]
            conn.commit()
            return cursor.lastrowid

    def update_cash_balance(self, amount, tx_type):
        """Nạp/Rút tiền GỐC từ bên ngoài vào Ví Mẹ (CASH)"""
        if amount > 0:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = 'CASH'", (amount, amount))
        else:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_out = total_out + ? WHERE id = 'CASH'", (amount, abs(amount)))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES ('CASH', ?, ?)", (tx_type, amount))

    def transfer_funds(self, from_wallet, to_wallet, amount):
        """Luân chuyển nội bộ giữa Ví Mẹ và Ví Con. Logic phân biệt Rút Lãi / Rút Vốn"""
        # 1. Cập nhật số dư tiền mặt thực tế
        self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (amount, from_wallet))
        self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (amount, to_wallet))
        
        # 2. Xử lý Logic Vốn ròng (Book Value)
        if from_wallet == 'CASH':
            # Mẹ cấp tiền cho Con -> Tăng vốn cấp vào (total_in) của ví con
            self.execute_query("UPDATE wallets SET total_in = total_in + ? WHERE id = ?", (amount, to_wallet))
        
        elif to_wallet == 'CASH':
            # Con trả tiền về cho Mẹ -> Kiểm tra xem là trả Lãi hay rút Vốn
            pl_data = self.execute_query("SELECT SUM(realized_pl) as total_pl FROM transactions WHERE wallet_id = ?", (from_wallet,), fetch_one=True)
            total_realized = pl_data['total_pl'] or 0
            
            # Vốn đã rút về trước đó
            current_out = self.execute_query("SELECT total_out FROM wallets WHERE id = ?", (from_wallet,), fetch_one=True)['total_out']
            
            # Lãi còn dư có thể rút (Lãi đã chốt - vốn đã rút về trước đó)
            available_profit = max(0, total_realized - current_out)
            
            # Nếu số tiền thu hồi > lãi đang có -> Phần chênh lệch mới bị tính là rút Vốn gốc
            if amount > available_profit:
                capital_reduction = amount - available_profit
                self.execute_query("UPDATE wallets SET total_out = total_out + ? WHERE id = ?", (capital_reduction, from_wallet))

        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_OUT', ?)", (from_wallet, -amount))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_IN', ?)", (to_wallet, amount))

    def execute_trade(self, wallet_id, symbol, quantity, price, total_value):
        """Giao dịch Mua/Bán với kiểm tra số dư và hỗ trợ giá thị trường"""
        symbol = symbol.upper()
        is_buy = quantity > 0
        abs_qty = abs(quantity)
        
        wallet = self.execute_query("SELECT balance FROM wallets WHERE id = ?", (wallet_id,), fetch_one=True)
        holding = self.execute_query("SELECT quantity, average_price FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol), fetch_one=True)
        
        realized_pl = 0
