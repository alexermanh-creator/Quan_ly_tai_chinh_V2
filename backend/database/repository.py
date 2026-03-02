import sqlite3
import os
from .models import SCHEMA
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config import DB_PATH

class DatabaseRepo:
    def __init__(self):
        self.db_path = DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            cursor = conn.cursor()
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
        self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = 'CASH'", (amount,))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES ('CASH', ?, ?)", (tx_type, amount))

    def transfer_funds(self, from_wallet, to_wallet, amount):
        self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (amount, from_wallet))
        if from_wallet == 'CASH':
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = ?", (amount, amount, to_wallet))
        elif to_wallet == 'CASH':
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_out = total_out + ? WHERE id = ?", (amount, amount, from_wallet))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_OUT', ?)", (from_wallet, -amount))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_IN', ?)", (to_wallet, amount))

    def execute_trade(self, wallet_id, symbol, quantity, price, total_value):
        symbol = symbol.upper()
        is_buy = quantity > 0
        abs_qty = abs(quantity)
        
        # FIX LỖI: Kiểm tra an toàn kết quả trả về
        holding = self.execute_query("SELECT quantity, average_price FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol), fetch_one=True)
        realized_pl = 0

        if is_buy:
            self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (total_value, wallet_id))
            
            # Nếu đã có hàng (holding không phải None)
            if holding:
                old_qty = holding['quantity']
                old_avg = holding['average_price']
                new_qty = old_qty + abs_qty
                new_avg = ((old_qty * old_avg) + total_value) / new_qty
                self.execute_query("UPDATE holdings SET quantity = ?, average_price = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, new_avg, wallet_id, symbol))
            else:
                # Nếu mua mã mới hoàn toàn
                self.execute_query("INSERT INTO holdings (wallet_id, symbol, quantity, average_price) VALUES (?, ?, ?, ?)", (wallet_id, symbol, abs_qty, price))
            
            tx_type = 'MUA'
            amount_log = -total_value
            
        else: # BÁN
            if not holding or holding['quantity'] < abs_qty:
                raise ValueError(f"Không đủ số lượng {symbol} để bán!")
            
            self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (total_value, wallet_id))
            cost_basis = abs_qty * holding['average_price']
            realized_pl = total_value - cost_basis
            new_qty = holding['quantity'] - abs_qty
            
            if new_qty <= 0:
                self.execute_query("DELETE FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol))
            else:
                self.execute_query("UPDATE holdings SET quantity = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, wallet_id, symbol))
            
            tx_type = 'BAN'
            amount_log = total_value

        self.execute_query(
            "INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (wallet_id, tx_type, symbol, abs_qty, price, amount_log, realized_pl)
        )
        return realized_pl

    def get_dashboard_data(self):
        wallets = self.execute_query("SELECT * FROM wallets", fetch_all=True)
        holdings = self.execute_query("SELECT * FROM holdings", fetch_all=True)
        return {"wallets": wallets, "holdings": holdings}
