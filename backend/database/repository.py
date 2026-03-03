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
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('goal', 'lai 10%')")
            # Thiết lập tỷ giá mặc định cho Crypto nếu chưa có
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('crypto_rate', '25000')")
            try: cursor.execute("ALTER TABLE holdings ADD COLUMN current_price REAL DEFAULT 0")
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

    def set_goal(self, goal_str):
        self.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('goal', ?)", (goal_str,))

    def get_goal(self):
        res = self.execute_query("SELECT value FROM settings WHERE key = 'goal'", fetch_one=True)
        return res['value'] if res else "lai 10%"

    def update_cash_balance(self, amount, tx_type):
        """Xử lý nạp/rút tiền tại Ví Mẹ - Có chặn rút khống"""
        if amount < 0: # Lệnh rút (rut)
            wallet = self.execute_query("SELECT balance FROM wallets WHERE id = 'CASH'", fetch_one=True)
            if not wallet or wallet['balance'] < abs(amount):
                raise ValueError(f"Ví Mẹ không đủ tiền mặt! Hiện có: {wallet['balance']:,.0f} đ")
        
        if amount > 0:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = 'CASH'", (amount, amount))
        else:
            self.execute_query("UPDATE wallets SET balance = balance + ?, total_out = total_out + ? WHERE id = 'CASH'", (amount, abs(amount)))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES ('CASH', ?, ?)", (tx_type, amount))

    def transfer_funds(self, from_wallet, to_wallet, amount):
        """Luân chuyển tiền nội bộ (chuyen/thu) - Có chặn chuyển khống"""
        wallet_from = self.execute_query("SELECT balance FROM wallets WHERE id = ?", (from_wallet,), fetch_one=True)
        if not wallet_from or wallet_from['balance'] < amount:
            raise ValueError(f"Ví {from_wallet} không đủ tiền mặt! Hiện có: {wallet_from['balance']:,.0f} đ")

        self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (amount, from_wallet))
        self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (amount, to_wallet))
        
        if from_wallet == 'CASH': 
            self.execute_query("UPDATE wallets SET total_in = total_in + ? WHERE id = ?", (amount, to_wallet))
        elif to_wallet == 'CASH': 
            self.execute_query("UPDATE wallets SET total_out = total_out + ? WHERE id = ?", (amount, from_wallet))
            
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (?, 'CHUYEN_IN', ?)", (to_wallet, amount))

    def update_other_asset(self, symbol, current_val):
        """Ghi nhận tài sản lẻ - Tự động trích vốn để tránh lỗi tính trùng lãi"""
        symbol = symbol.upper()
        
        # 1. Kiểm tra vốn trong ví OTHER
        wallet_other = self.execute_query("SELECT (total_in - total_out) as net_inv FROM wallets WHERE id = 'OTHER'", fetch_one=True)
        
        if wallet_other and wallet_other['net_inv'] > 0:
            cost = wallet_other['net_inv']
            self.execute_query("UPDATE wallets SET balance = 0 WHERE id = 'OTHER'")
        else:
            wallet_cash = self.execute_query("SELECT balance FROM wallets WHERE id = 'CASH'", fetch_one=True)
            if wallet_cash and wallet_cash['balance'] >= current_val:
                cost = current_val
                self.transfer_funds('CASH', 'OTHER', current_val)
                self.execute_query("UPDATE wallets SET balance = 0 WHERE id = 'OTHER'")
            else:
                cost = current_val
                self.execute_query("UPDATE wallets SET balance = balance + ?, total_in = total_in + ? WHERE id = 'CASH'", (current_val, current_val))
                self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES ('CASH', 'NAP', ?)", (current_val,))
                self.transfer_funds('CASH', 'OTHER', current_val)
                self.execute_query("UPDATE wallets SET balance = 0 WHERE id = 'OTHER'")

        self.execute_query("""
            INSERT OR REPLACE INTO holdings (wallet_id, symbol, quantity, average_price, current_price) 
            VALUES ('OTHER', ?, 1, ?, ?)
        """, (symbol, cost, current_val))

    def execute_trade(self, wallet_id, symbol, quantity, price, total_value):
        symbol = symbol.upper()
        wallet = self.execute_query("SELECT balance FROM wallets WHERE id = ?", (wallet_id,), fetch_one=True)
        holding = self.execute_query("SELECT quantity, average_price FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol), fetch_one=True)
        if quantity > 0: # MUA
            if not wallet or wallet['balance'] < total_value: raise ValueError("Ví không đủ tiền mặt để mua!")
            self.execute_query("UPDATE wallets SET balance = balance - ? WHERE id = ?", (total_value, wallet_id))
            if holding:
                new_qty = holding['quantity'] + quantity
                new_avg = ((holding['quantity'] * holding['average_price']) + total_value) / new_qty
                self.execute_query("UPDATE holdings SET quantity = ?, average_price = ?, current_price = ? WHERE wallet_id = ? AND symbol = ?", (new_qty, new_avg, price, wallet_id, symbol))
            else:
                self.execute_query("INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price) VALUES (?, ?, ?, ?, ?)", (wallet_id, symbol, quantity, price, price))
            self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (?, 'MUA', ?, ?, ?, ?, 0)", (wallet_id, symbol, quantity, price, -total_value))
        else: # BÁN
            abs_qty = abs(quantity)
            if not holding or holding['quantity'] < abs_qty: raise ValueError("Không đủ số lượng để bán!")
            self.execute_query("UPDATE wallets SET balance = balance + ? WHERE id = ?", (total_value, wallet_id))
            real_pl = total_value - (abs_qty * holding['average_price'])
            if holding['quantity'] == abs_qty:
                self.execute_query("DELETE FROM holdings WHERE wallet_id = ? AND symbol = ?", (wallet_id, symbol))
            else:
                self.execute_query("UPDATE holdings SET quantity = quantity - ?, current_price = ? WHERE wallet_id = ? AND symbol = ?", (abs_qty, price, wallet_id, symbol))
            self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (?, 'BAN', ?, ?, ?, ?, ?)", (wallet_id, symbol, abs_qty, price, total_value, real_pl))
            return real_pl
        return 0

    def update_market_price(self, symbol, new_price):
        self.execute_query("UPDATE holdings SET current_price = ? WHERE symbol = ?", (new_price, symbol.upper()))

    def get_dashboard_data(self):
        wallets = self.execute_query("SELECT * FROM wallets", fetch_all=True)
        holdings = self.execute_query("SELECT * FROM holdings", fetch_all=True)
        realized_rows = self.execute_query("SELECT wallet_id, SUM(realized_pl) as total FROM transactions GROUP BY wallet_id", fetch_all=True)
        realized_map = {r['wallet_id']: (r['total'] or 0) for r in realized_rows}
        # Sửa ở đây: Bỏ cứng 'STOCK', lấy lịch sử trade cho mọi ví để tái sử dụng ở nhiều Module
        perf_symbols = self.execute_query("""
            SELECT wallet_id, symbol, SUM(realized_pl) as realized, 
                   SUM(CASE WHEN type='MUA' THEN ABS(amount) ELSE 0 END) as total_invested 
            FROM transactions 
            WHERE symbol IS NOT NULL 
            GROUP BY wallet_id, symbol
        """, fetch_all=True)
        return {"wallets": wallets, "holdings": holdings, "realized": realized_map, "perf_symbols": perf_symbols, "goal": self.get_goal()}
