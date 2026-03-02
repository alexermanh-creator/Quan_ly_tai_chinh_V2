# backend/database/repository.py
import sqlite3
import os
import sys

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
            # Khởi tạo 3 ví cơ bản và bảng settings
            cursor.execute("INSERT OR IGNORE INTO wallets (id) VALUES ('CASH'), ('STOCK'), ('CRYPTO'), ('OTHER')")
            cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('goal', 'lai 10%')")
            
            cursor.execute("PRAGMA table_info(holdings)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'current_price' not in columns:
                cursor.execute("ALTER TABLE holdings ADD COLUMN current_price REAL")
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

    def set_goal(self, goal_str):
        self.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('goal', ?)", (goal_str,))

    def get_goal(self):
        res = self.execute_query("SELECT value FROM settings WHERE key = 'goal'", fetch_one=True)
        return res['value'] if res else "lai 10%"

    def update_cash_balance(self, amount, tx_type):
        if amount > 0:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = 'CASH'", (amount, amount))
        else:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_out = total_out + ? WHERE id = 'CASH'", (amount, abs(amount)))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES ('CASH', ?, ?)", (tx_type, amount))

    def transfer_funds(self, from_wallet, to_wallet, amount):
        # Chuyen/Thu nội bộ: Cập nhật total_in/out của ví con
        self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (amount, from_wallet))
        self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (amount, to_wallet))
        
        if from_wallet == 'CASH': # Nạp vào ví con
            self.execute_query("UPDATE wallets SET total_in = total_in + ? WHERE id = ?", (amount, to_wallet))
        elif to_wallet == 'CASH': # Rút về ví mẹ
            self.execute_query("UPDATE wallets SET total_out = total_out + ? WHERE id = ?", (amount, from_wallet))
            
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_OUT', ?)", (from_wallet, -amount))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_IN', ?)", (to_wallet, amount))

    def update_other_asset(self, symbol, value):
        # Cập nhật tài sản khác bằng cách lưu vào holdings
        symbol = symbol.upper()
        self.execute_query("INSERT OR REPLACE INTO holdings (wallet_id, symbol, quantity, average_price, current_price) VALUES ('OTHER', ?, 1, ?, ?)", (symbol, value, value))

    def execute_trade(self, wallet_id, symbol, quantity, price, total_value):
        symbol = symbol.upper()
        is_buy = quantity > 0
        abs_qty = abs(quantity)
        wallet = self.execute_query("SELECT balance FROM wallets WHERE id = ?", (wallet_id,), fetch_one=True)
        holding = self.execute_query("SELECT quantity, average_price FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol), fetch_one=True)
        
        if is_buy:
            if not wallet or wallet['balance'] < total_value: raise ValueError(f"Ví {wallet_id} không đủ tiền!")
            self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (total_value, wallet_id))
            if holding:
                new_qty = holding['quantity'] + abs_qty
                new_avg = ((holding['quantity'] * holding['average_price']) + total_value) / new_qty
                self.execute_query("UPDATE holdings SET quantity = ?, average_price = ?, current_price = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, new_avg, price, wallet_id, symbol))
            else:
                self.execute_query("INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price) VALUES (?, ?, ?, ?, ?)", (wallet_id, symbol, abs_qty, price, price))
        else:
            if not holding or holding['quantity'] < abs_qty: raise ValueError(f"Không đủ {symbol} để bán!")
            self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (total_value, wallet_id))
            realized_pl = total_value - (abs_qty * holding['average_price'])
            new_qty = holding['quantity'] - abs_qty
            if new_qty <= 0: self.execute_query("DELETE FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol))
            else: self.execute_query("UPDATE holdings SET quantity = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, wallet_id, symbol))
            return realized_pl
        return 0

    def get_dashboard_data(self):
        wallets = self.execute_query("SELECT * FROM wallets", fetch_all=True)
        holdings = self.execute_query("SELECT * FROM holdings", fetch_all=True)
        goal = self.get_goal()
        return {"wallets": wallets, "holdings": holdings, "goal": goal}
