# backend/database/repository.py
import sqlite3, os, sys, shutil
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
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('goal', '0'), ('crypto_rate', '25000')")
            
            try: cursor.execute("ALTER TABLE holdings ADD COLUMN current_price REAL DEFAULT 0")
            except: pass
            try: cursor.execute("ALTER TABLE holdings ADD COLUMN cost_basis_vnd REAL DEFAULT 0")
            except: pass
            try: cursor.execute("ALTER TABLE transactions ADD COLUMN note TEXT")
            except: pass
            
            conn.commit()

    def replace_db(self, new_db_path):
        """Khôi phục Database từ file backup"""
        shutil.copy2(new_db_path, self.db_path)
        return True

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
        if amount < 0: # Rút tiền
            wallet = self.execute_query("SELECT balance FROM wallets WHERE id = 'CASH'", fetch_one=True)
            current_balance = wallet['balance'] if wallet else 0
            if current_balance < abs(amount):
                raise ValueError(f"Ví CASH không đủ tiền để rút! (Sức mua hiện tại: {current_balance:,.0f} đ)")
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_out = total_out + ? WHERE id = 'CASH'", (amount, abs(amount)))
        else: # Nạp tiền
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = 'CASH'", (amount, amount))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES ('CASH', ?, ?)", (tx_type, amount))

    def transfer_funds(self, from_wallet, to_wallet, amount):
        wallet = self.execute_query("SELECT balance FROM wallets WHERE id = ?", (from_wallet,), fetch_one=True)
        current_balance = wallet['balance'] if wallet else 0
        if current_balance < amount:
            raise ValueError(f"Ví {from_wallet} không đủ tiền để chuyển! (Sức mua hiện tại: {current_balance:,.0f} đ)")

        self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (amount, from_wallet))
        self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = ?", (amount, amount, to_wallet))
        if from_wallet != 'CASH':
            self.execute_query("UPDATE wallets SET total_out = total_out + ? WHERE id = ?", (amount, from_wallet))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_IN', ?)", (to_wallet, amount))

    def execute_trade(self, wallet_id, symbol, quantity, price, total_value_vnd):
        symbol = symbol.upper()
        if quantity > 0:
            wallet = self.execute_query("SELECT balance FROM wallets WHERE id = ?", (wallet_id,), fetch_one=True)
            current_balance = wallet['balance'] if wallet else 0
            if current_balance < total_value_vnd:
                raise ValueError(f"Sức mua ví {wallet_id} không đủ! (Đang có: {current_balance:,.0f} đ, Cần: {total_value_vnd:,.0f} đ).")

        holding = self.execute_query("SELECT quantity, average_price, cost_basis_vnd FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol), fetch_one=True)
        if quantity > 0:
            self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (total_value_vnd, wallet_id))
            if holding:
                new_qty = holding['quantity'] + quantity
                new_cost = holding['cost_basis_vnd'] + total_value_vnd
                new_avg = (holding['quantity'] * holding['average_price'] + quantity * price) / new_qty
                self.execute_query("UPDATE holdings SET quantity = ?, average_price = ?, current_price = ?, cost_basis_vnd = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, new_avg, price, new_cost, wallet_id, symbol))
            else:
                self.execute_query("INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price, cost_basis_vnd) VALUES (?, ?, ?, ?, ?, ?)", (wallet_id, symbol, quantity, price, price, total_value_vnd))
            self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (?, 'MUA', ?, ?, ?, ?, 0)", (wallet_id, symbol, quantity, price, -total_value_vnd))
        else:
            abs_qty = abs(quantity)
            if not holding or holding['quantity'] < abs_qty:
                raise ValueError(f"Không thể bán {abs_qty} {symbol}! Sếp chỉ đang có {holding['quantity'] if holding else 0} cổ phiếu.")

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
            "goal": self.execute_query("SELECT value FROM settings WHERE key = 'goal'", fetch_one=True)['value'],
            "crypto_rate": self.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)['value']
        }

    def clear_all_data(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transactions")
            cursor.execute("DELETE FROM holdings")
            cursor.execute("UPDATE wallets SET balance = 0, total_in = 0, total_out = 0")
            conn.commit()

    def get_transactions_paginated(self, limit=5, offset=0, filter_type='ALL', symbol=None):
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        elif filter_type in ['CASH', 'STOCK', 'CRYPTO', 'OTHER']:
            query += " AND wallet_id = ?"
            params.append(filter_type)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return self.execute_query(query, tuple(params), fetch_all=True)

    def get_transactions_count(self, filter_type='ALL', symbol=None):
        query = "SELECT COUNT(*) as total FROM transactions WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        elif filter_type in ['CASH', 'STOCK', 'CRYPTO', 'OTHER']:
            query += " AND wallet_id = ?"
            params.append(filter_type)
        res = self.execute_query(query, tuple(params), fetch_one=True)
        return res['total'] if res else 0

    def delete_holding_and_refund(self, symbol):
        symbol = symbol.upper()
        holding = self.execute_query("SELECT * FROM holdings WHERE symbol = ?", (symbol,), fetch_one=True)
        if not holding: return False, f"⚠️ Không thấy mã {symbol}."
        cost_basis = holding['cost_basis_vnd']
        self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (cost_basis, holding['wallet_id']))
        self.execute_query("DELETE FROM holdings WHERE wallet_id = ? AND symbol = ?", (holding['wallet_id'], symbol))
        return True, f"✅ Đã xóa {symbol}, hoàn {cost_basis:,.0f} đ."

    def undo_transaction(self, tx_id):
        tx = self.execute_query("SELECT * FROM transactions WHERE id = ?", (tx_id,), fetch_one=True)
        if not tx: return False, "⚠️ Không thấy giao dịch."
        if tx['type'] == 'BAN':
            self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (tx['amount'], tx['wallet_id']))
            self.execute_query("DELETE FROM transactions WHERE id = ?", (tx_id,))
            return True, "✅ Đã hoàn tác."
        return False, "⚠️ Chỉ hỗ trợ hoàn tác lệnh BÁN."

    def add_cash_dividend(self, symbol, amount):
        self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = 'STOCK'", (amount,))
        self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, amount, realized_pl, note) VALUES ('STOCK', 'CO_TUC_TIEN', ?, ?, ?, ?)", (symbol.upper(), amount, amount, f"Cổ tức tiền mặt {symbol.upper()}"))
        return True, "✅ Đã nhận cổ tức tiền."

    def add_stock_dividend(self, symbol, quantity):
        holding = self.execute_query("SELECT quantity, cost_basis_vnd FROM holdings WHERE wallet_id = 'STOCK' AND symbol = ?", (symbol.upper(),), fetch_one=True)
        if not holding: return False, "⚠️ Không nắm giữ mã này."
        new_qty = holding['quantity'] + quantity
        self.execute_query("UPDATE holdings SET quantity = ? WHERE wallet_id = 'STOCK' AND symbol = ?", (new_qty, symbol.upper()))
        return True, "✅ Đã nhận cổ tức cổ phiếu."
    def replace_db(self, new_db_path):
        """Khôi phục Database từ file backup"""
        shutil.copy2(new_db_path, self.db_path)
        return True

    def get_report_raw_data(self):
        return {
            "wallets": self.execute_query("SELECT * FROM wallets", fetch_all=True),
            "holdings": self.execute_query("SELECT * FROM holdings", fetch_all=True),
            "transactions": self.execute_query("SELECT * FROM transactions ORDER BY id DESC", fetch_all=True),
            "settings": {s['key']: s['value'] for s in self.execute_query("SELECT * FROM settings", fetch_all=True)}
        }