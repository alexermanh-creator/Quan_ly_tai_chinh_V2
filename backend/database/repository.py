# backend/database/repository.py
import sqlite3, os, sys
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
            cursor.execute("INSERT OR IGNORE INTO wallets (id) VALUES ('CASH'), ('STOCK'), ('CRYPTO'), ('OTHER')")
            cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('goal', 'lai 10%'), ('crypto_rate', '25000')")
            try: cursor.execute("ALTER TABLE holdings ADD COLUMN current_price REAL DEFAULT 0")
            except: pass
            try: cursor.execute("ALTER TABLE holdings ADD COLUMN cost_basis_vnd REAL DEFAULT 0")
            except: pass
            conn.commit()

    def execute_query(self, query, params=(), fetch_one=False, fetch_all=False):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch_one:
                row = cursor.fetchone()
                return dict(row) if row else None
            return [dict(row) for row in cursor.fetchall()] if fetch_all else cursor.lastrowid

    def update_cash_balance(self, amount, tx_type):
        if amount > 0:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = 'CASH'", (amount, amount))
        else:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_out = total_out + ? WHERE id = 'CASH'", (amount, abs(amount)))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES ('CASH', ?, ?)", (tx_type, amount))

    def transfer_funds(self, from_wallet, to_wallet, amount):
        """Chuyển vốn: total_in/out của ví con dùng để tính vốn gốc đứng im"""
        self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (amount, from_wallet))
        self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = ?", (amount, amount, to_wallet))
        if from_wallet != 'CASH': # Nếu thu hồi tiền về ví mẹ
            self.execute_query("UPDATE wallets SET total_out = total_out + ? WHERE id = ?", (amount, from_wallet))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_IN', ?)", (to_wallet, amount))

    def execute_trade(self, wallet_id, symbol, quantity, price, total_value_vnd):
        symbol = symbol.upper()
        holding = self.execute_query("SELECT quantity, average_price, cost_basis_vnd FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol), fetch_one=True)
        if quantity > 0: # MUA
            self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (total_value_vnd, wallet_id))
            if holding:
                new_qty = holding['quantity'] + quantity
                new_cost = holding['cost_basis_vnd'] + total_value_vnd
                new_avg = (holding['quantity'] * holding['average_price'] + quantity * price) / new_qty
                self.execute_query("UPDATE holdings SET quantity = ?, average_price = ?, current_price = ?, cost_basis_vnd = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, new_avg, price, new_cost, wallet_id, symbol))
            else:
                self.execute_query("INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price, cost_basis_vnd) VALUES (?, ?, ?, ?, ?, ?)", (wallet_id, symbol, quantity, price, price, total_value_vnd))
            self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (?, 'MUA', ?, ?, ?, ?, 0)", (wallet_id, symbol, quantity, price, -total_value_vnd))
        else: # BÁN
            abs_qty = abs(quantity)
            self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (total_value_vnd, wallet_id))
            cost_per_unit = holding['cost_basis_vnd'] / holding['quantity']
            real_pl = total_value_vnd - (abs_qty * cost_per_unit)
            if holding['quantity'] == abs_qty:
                self.execute_query("DELETE FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol))
            else:
                new_cost = holding['cost_basis_vnd'] - (abs_qty * cost_per_unit)
                self.execute_query("UPDATE holdings SET quantity = quantity - ?, current_price = ?, cost_basis_vnd = ? WHERE wallet_id = ? AND symbol = ?", (abs_qty, price, new_cost, wallet_id, symbol))
            self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (?, 'BAN', ?, ?, ?, ?, ?)", (wallet_id, symbol, abs_qty, price, total_value_vnd, real_pl))
            return real_pl
        return 0

    def update_market_price(self, symbol, new_price):
        self.execute_query("UPDATE holdings SET current_price = ? WHERE symbol = ?", (new_price, symbol.upper()))

    def update_other_asset(self, symbol, current_val):
        """Hàm thần thánh mua Vàng/BĐS tự trích vốn"""
        symbol = symbol.upper()
        wallet_cash = self.execute_query("SELECT balance FROM wallets WHERE id = 'CASH'", fetch_one=True)
        if wallet_cash and wallet_cash['balance'] >= current_val:
            self.transfer_funds('CASH', 'OTHER', current_val)
        else:
            diff = current_val - (wallet_cash['balance'] if wallet_cash else 0)
            self.update_cash_balance(diff, 'NAP')
            self.transfer_funds('CASH', 'OTHER', current_val)
        self.execute_query("UPDATE wallets SET balance = 0 WHERE id = 'OTHER'")
        self.execute_query("INSERT OR REPLACE INTO holdings (wallet_id, symbol, quantity, average_price, current_price, cost_basis_vnd) VALUES ('OTHER', ?, 1, ?, ?, ?)", (symbol, current_val, current_val, current_val))

    def get_dashboard_data(self):
        return {
            "wallets": self.execute_query("SELECT * FROM wallets", fetch_all=True),
            "holdings": self.execute_query("SELECT * FROM holdings", fetch_all=True),
            "realized": {r['wallet_id']: (r['total'] or 0) for r in self.execute_query("SELECT wallet_id, SUM(realized_pl) as total FROM transactions GROUP BY wallet_id", fetch_all=True)},
            "perf_symbols": self.execute_query("SELECT wallet_id, symbol, SUM(realized_pl) as realized, SUM(CASE WHEN type='MUA' THEN ABS(amount) ELSE 0 END) as total_invested FROM transactions WHERE symbol IS NOT NULL GROUP BY wallet_id, symbol", fetch_all=True),
            "goal": self.execute_query("SELECT value FROM settings WHERE key = 'goal'", fetch_one=True)['value']
        }
