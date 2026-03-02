# backend/database/repository.py
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
        if amount > 0:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = 'CASH'", (amount, amount))
        else:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_out = total_out + ? WHERE id = 'CASH'", (amount, abs(amount)))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES ('CASH', ?, ?)", (tx_type, amount))

    def transfer_funds(self, from_wallet, to_wallet, amount):
        self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (amount, from_wallet))
        self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (amount, to_wallet))
        
        if from_wallet == 'CASH':
            self.execute_query("UPDATE wallets SET total_in = total_in + ? WHERE id = ?", (amount, to_wallet))
        elif to_wallet == 'CASH':
            pl_data = self.execute_query("SELECT SUM(realized_pl) as total_pl FROM transactions WHERE wallet_id = ?", (from_wallet,), fetch_one=True)
            total_realized = pl_data['total_pl'] or 0
            current_out = self.execute_query("SELECT total_out FROM wallets WHERE id = ?", (from_wallet,), fetch_one=True)['total_out']
            available_profit = max(0, total_realized - current_out)
            if amount > available_profit:
                capital_reduction = amount - available_profit
                self.execute_query("UPDATE wallets SET total_out = total_out + ? WHERE id = ?", (capital_reduction, from_wallet))

        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_OUT', ?)", (from_wallet, -amount))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_IN', ?)", (to_wallet, amount))

    def update_market_price(self, symbol, new_price):
        """Hàm cập nhật giá thị trường nhanh cho 1 mã"""
        symbol = symbol.upper()
        self.execute_query("UPDATE holdings SET current_price = ? WHERE symbol = ?", (new_price, symbol))
        return True

    def execute_trade(self, wallet_id, symbol, quantity, price, total_value):
        symbol = symbol.upper()
        is_buy = quantity > 0
        abs_qty = abs(quantity)
        wallet = self.execute_query("SELECT balance FROM wallets WHERE id = ?", (wallet_id,), fetch_one=True)
        holding = self.execute_query("SELECT quantity, average_price FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol), fetch_one=True)
        
        if is_buy:
            if not wallet or wallet['balance'] < total_value:
                raise ValueError(f"Ví {wallet_id} không đủ tiền! Sức mua hiện tại chỉ có {wallet['balance']:,.0f} đ.")
            self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (total_value, wallet_id))
            if holding:
                new_qty = holding['quantity'] + abs_qty
                new_avg = ((holding['quantity'] * holding['average_price']) + total_value) / new_qty
                # Cập nhật cả current_price bằng giá mua mới nhất khi MUA thêm
                self.execute_query("UPDATE holdings SET quantity = ?, average_price = ?, current_price = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, new_avg, price, wallet_id, symbol))
            else:
                # INSERT đầy đủ cột current_price khi MUA mã mới
                self.execute_query("INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price) VALUES (?, ?, ?, ?, ?)", (wallet_id, symbol, abs_qty, price, price))
            tx_type, amount_log, realized_pl = 'MUA', -total_value, 0
        else:
            if not holding or holding['quantity'] < abs_qty: raise ValueError(f"Không đủ {symbol} để bán!")
            self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (total_value, wallet_id))
            cost_basis = abs_qty * holding['average_price']
            realized_pl = total_value - cost_basis
            new_qty = holding['quantity'] - abs_qty
            if new_qty <= 0: self.execute_query("DELETE FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol))
            else: self.execute_query("UPDATE holdings SET quantity = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, wallet_id, symbol))
            tx_type, amount_log = 'BAN', total_value

        self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (wallet_id, tx_type, symbol, abs_qty, price, amount_log, realized_pl))
        return realized_pl

    def get_dashboard_data(self):
        wallets = self.execute_query("SELECT * FROM wallets", fetch_all=True)
        holdings = self.execute_query("SELECT * FROM holdings", fetch_all=True)
        # Lấy thêm lãi đã chốt của từng ví
        realized = self.execute_query("SELECT wallet_id, SUM(realized_pl) as total FROM transactions GROUP BY wallet_id", fetch_all=True)
        realized_map = {r['wallet_id']: r['total'] for r in realized}
        return {"wallets": wallets, "holdings": holdings, "realized": realized_map}
