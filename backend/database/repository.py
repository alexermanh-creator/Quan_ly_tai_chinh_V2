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
            cursor.execute("INSERT OR IGNORE INTO wallets (id) VALUES ('CASH'), ('STOCK'), ('CRYPTO')")
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
            total_realized = (pl_data['total_pl'] or 0) if pl_data else 0
            current_out_row = self.execute_query("SELECT total_out FROM wallets WHERE id = ?", (from_wallet,), fetch_one=True)
            current_out = current_out_row['total_out'] if current_out_row else 0
            available_profit = max(0, total_realized - current_out)
            if amount > available_profit:
                capital_reduction = amount - available_profit
                self.execute_query("UPDATE wallets SET total_out = total_out + ? WHERE id = ?", (capital_reduction, from_wallet))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_OUT', ?)", (from_wallet, -amount))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_IN', ?)", (to_wallet, amount))

    def execute_trade(self, wallet_id, symbol, quantity, price, total_value):
        symbol = symbol.upper()
        is_buy = quantity > 0
        abs_qty = abs(quantity)
        wallet = self.execute_query("SELECT balance FROM wallets WHERE id = ?", (wallet_id,), fetch_one=True)
        holding = self.execute_query("SELECT quantity, average_price FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol), fetch_one=True)
        
        if is_buy:
            if not wallet or wallet['balance'] < total_value:
                raise ValueError(f"Ví {wallet_id} không đủ tiền!")
            self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (total_value, wallet_id))
            if holding:
                new_qty = holding['quantity'] + abs_qty
                new_avg = ((holding['quantity'] * holding['average_price']) + total_value) / new_qty
                self.execute_query("UPDATE holdings SET quantity = ?, average_price = ?, current_price = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, new_avg, price, wallet_id, symbol))
            else:
                self.execute_query("INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price) VALUES (?, ?, ?, ?, ?)", (wallet_id, symbol, abs_qty, price, price))
            realized_pl = 0
        else:
            if not holding or holding['quantity'] < abs_qty: raise ValueError(f"Không đủ {symbol} để bán!")
            self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (total_value, wallet_id))
            realized_pl = total_value - (abs_qty * holding['average_price'])
            new_qty = holding['quantity'] - abs_qty
            if new_qty <= 0: self.execute_query("DELETE FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol))
            else: self.execute_query("UPDATE holdings SET quantity = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, wallet_id, symbol))
        
        self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (wallet_id, 'MUA' if is_buy else 'BAN', symbol, abs_qty, price, -total_value if is_buy else total_value, realized_pl))
        return realized_pl

    def update_market_price(self, symbol, new_price):
        return self.execute_query("UPDATE holdings SET current_price = ? WHERE symbol = ?", (new_price, symbol.upper()))

    def get_dashboard_data(self):
        wallets = self.execute_query("SELECT * FROM wallets", fetch_all=True)
        holdings = self.execute_query("SELECT * FROM holdings", fetch_all=True)
        
        realized_rows = self.execute_query("SELECT wallet_id, SUM(realized_pl) as total FROM transactions GROUP BY wallet_id", fetch_all=True)
        realized_map = {r['wallet_id']: (r['total'] or 0) for r in realized_rows}

        stats = self.execute_query("""
            SELECT 
                SUM(CASE WHEN type='MUA' THEN ABS(amount) ELSE 0 END) as total_buy,
                SUM(CASE WHEN type='BAN' THEN amount ELSE 0 END) as total_sell
            FROM transactions WHERE wallet_id = 'STOCK'
        """, fetch_one=True)
        
        pl_by_symbol = self.execute_query("""
            SELECT symbol, SUM(realized_pl) as pl FROM transactions 
            WHERE wallet_id = 'STOCK' AND symbol IS NOT NULL 
            GROUP BY symbol HAVING pl != 0 ORDER BY pl DESC
        """, fetch_all=True)

        return {
            "wallets": wallets, "holdings": holdings, "realized": realized_map,
            "stats": stats if stats else {'total_buy': 0, 'total_sell': 0},
            "pl_symbols": pl_by_symbol if pl_by_symbol else []
        }
