# backend/database/repository.py
import os, sys
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from .models import SCHEMA

class DatabaseRepo:
    def __init__(self):
        # Chìa khóa két sắt Neon vĩnh viễn của Sếp
        self.db_url = "postgresql://neondb_owner:npg_P5O6eXTEiZJF@ep-billowing-unit-a1k9nbam-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
        self._init_db()

    def _init_db(self):
        conn = psycopg2.connect(self.db_url)
        try:
            with conn.cursor() as cursor:
                cursor.execute(SCHEMA)
                cursor.execute("INSERT INTO wallets (id) VALUES ('CASH'), ('STOCK'), ('CRYPTO'), ('OTHER') ON CONFLICT (id) DO NOTHING")
                cursor.execute("INSERT INTO settings (key, value) VALUES ('goal', '0'), ('crypto_rate', '25000') ON CONFLICT (key) DO NOTHING")
            conn.commit()
        finally:
            conn.close()

    def execute_query(self, query, params=(), fetch_one=False, fetch_all=False):
        conn = psycopg2.connect(self.db_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description: # Đây là lệnh SELECT có trả về dữ liệu
                    if fetch_one:
                        row = cursor.fetchone()
                        return dict(row) if row else None
                    if fetch_all:
                        return [dict(row) for row in cursor.fetchall()]
                conn.commit()
                return cursor.rowcount # Trả về số dòng bị ảnh hưởng nếu là INSERT/UPDATE
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_cash_balance(self, amount, tx_type):
        if amount < 0: # Rút tiền
            wallet = self.execute_query("SELECT balance FROM wallets WHERE id = 'CASH'", fetch_one=True)
            current_balance = wallet['balance'] if wallet else 0
            if current_balance < abs(amount):
                raise ValueError(f"Ví CASH không đủ tiền để rút! (Sức mua hiện tại: {current_balance:,.0f} đ)")
            self.execute_query("UPDATE wallets SET balance = balance + %s, total_out = total_out + %s WHERE id = 'CASH'", (amount, abs(amount)))
        else: # Nạp tiền
            self.execute_query("UPDATE wallets SET balance = balance + %s, total_in = total_in + %s WHERE id = 'CASH'", (amount, amount))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES ('CASH', %s, %s)", (tx_type, amount))

    def transfer_funds(self, from_wallet, to_wallet, amount):
        wallet = self.execute_query("SELECT balance FROM wallets WHERE id = %s", (from_wallet,), fetch_one=True)
        current_balance = wallet['balance'] if wallet else 0
        if current_balance < amount:
            raise ValueError(f"Ví {from_wallet} không đủ tiền để chuyển! (Sức mua hiện tại: {current_balance:,.0f} đ)")

        self.execute_query("UPDATE wallets SET balance = balance - %s WHERE id = %s", (amount, from_wallet))
        self.execute_query("UPDATE wallets SET balance = balance + %s, total_in = total_in + %s WHERE id = %s", (amount, amount, to_wallet))
        if from_wallet != 'CASH':
            self.execute_query("UPDATE wallets SET total_out = total_out + %s WHERE id = %s", (amount, from_wallet))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount) VALUES (%s, 'CHUYEN_IN', %s)", (to_wallet, amount))

    def execute_trade(self, wallet_id, symbol, quantity, price, total_value_vnd):
        symbol = symbol.upper()
        if quantity > 0:
            wallet = self.execute_query("SELECT balance FROM wallets WHERE id = %s", (wallet_id,), fetch_one=True)
            current_balance = wallet['balance'] if wallet else 0
            if current_balance < total_value_vnd:
                raise ValueError(f"Sức mua ví {wallet_id} không đủ! (Đang có: {current_balance:,.0f} đ, Cần: {total_value_vnd:,.0f} đ).")

        holding = self.execute_query("SELECT quantity, average_price, cost_basis_vnd FROM holdings WHERE wallet_id = %s AND symbol = %s", (wallet_id, symbol), fetch_one=True)
        if quantity > 0:
            self.execute_query("UPDATE wallets SET balance = balance - %s WHERE id = %s", (total_value_vnd, wallet_id))
            if holding:
                new_qty = holding['quantity'] + quantity
                new_cost = holding['cost_basis_vnd'] + total_value_vnd
                new_avg = (holding['quantity'] * holding['average_price'] + quantity * price) / new_qty
                self.execute_query("UPDATE holdings SET quantity = %s, average_price = %s, current_price = %s, cost_basis_vnd = %s WHERE wallet_id = %s AND symbol = %s", (new_qty, new_avg, price, new_cost, wallet_id, symbol))
            else:
                self.execute_query("INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price, cost_basis_vnd) VALUES (%s, %s, %s, %s, %s, %s)", (wallet_id, symbol, quantity, price, price, total_value_vnd))
            self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (%s, 'MUA', %s, %s, %s, %s, 0)", (wallet_id, symbol, quantity, price, -total_value_vnd))
        else:
            abs_qty = abs(quantity)
            if not holding or holding['quantity'] < abs_qty:
                raise ValueError(f"Không thể bán {abs_qty} {symbol}! Sếp chỉ đang có {holding['quantity'] if holding else 0} cổ phiếu.")

            self.execute_query("UPDATE wallets SET balance = balance + %s WHERE id = %s", (total_value_vnd, wallet_id))
            cost_per_unit = holding['cost_basis_vnd'] / holding['quantity']
            real_pl = total_value_vnd - (abs_qty * cost_per_unit)
            if holding['quantity'] == abs_qty:
                self.execute_query("DELETE FROM holdings WHERE wallet_id = %s AND symbol = %s", (wallet_id, symbol))
            else:
                new_cost = holding['cost_basis_vnd'] - (abs_qty * cost_per_unit)
                self.execute_query("UPDATE holdings SET quantity = quantity - %s, current_price = %s, cost_basis_vnd = %s WHERE wallet_id = %s AND symbol = %s", (abs_qty, price, new_cost, wallet_id, symbol))
            self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, realized_pl) VALUES (%s, 'BAN', %s, %s, %s, %s, %s)", (wallet_id, symbol, abs_qty, price, total_value_vnd, real_pl))
            return real_pl
        return 0

    def update_market_price(self, symbol, new_price):
        self.execute_query("UPDATE holdings SET current_price = %s WHERE symbol = %s", (new_price, symbol.upper()))

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
        
        self.execute_query("""
            INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price, cost_basis_vnd) 
            VALUES ('OTHER', %s, 1, %s, %s, %s)
            ON CONFLICT (wallet_id, symbol)
            DO UPDATE SET quantity = EXCLUDED.quantity, average_price = EXCLUDED.average_price, current_price = EXCLUDED.current_price, cost_basis_vnd = EXCLUDED.cost_basis_vnd
        """, (symbol, current_val, current_val, current_val))

    def get_dashboard_data(self):
        return {
            "wallets": self.execute_query("SELECT * FROM wallets", fetch_all=True),
            "holdings": self.execute_query("SELECT * FROM holdings", fetch_all=True),
            "realized": {r['wallet_id']: (r['total'] or 0) for r in self.execute_query("SELECT wallet_id, SUM(realized_pl) as total FROM transactions GROUP BY wallet_id", fetch_all=True)},
            "perf_symbols": self.execute_query("SELECT wallet_id, symbol, SUM(realized_pl) as realized, SUM(CASE WHEN type='MUA' THEN ABS(amount) ELSE 0 END) as total_invested FROM transactions WHERE symbol IS NOT NULL GROUP BY wallet_id, symbol", fetch_all=True),
            "goal": self.execute_query("SELECT value FROM settings WHERE key = 'goal'", fetch_one=True)['value'],
            "crypto_rate": self.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)['value']
        }

    def clear_all_data(self):
        conn = psycopg2.connect(self.db_url)
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM transactions")
                cursor.execute("DELETE FROM holdings")
                cursor.execute("UPDATE wallets SET balance = 0, total_in = 0, total_out = 0")
            conn.commit()
        finally:
            conn.close()

    def force_update_wallet(self, wallet_id, balance, total_in, total_out):
        self.execute_query("UPDATE wallets SET balance = %s, total_in = %s, total_out = %s WHERE id = %s", (balance, total_in, total_out, wallet_id))

    def insert_historical_pnl(self, wallet_id, amount, note):
        query = "INSERT INTO transactions (wallet_id, type, amount, realized_pl, symbol, note) VALUES (%s, 'CHOT_LICH_SU', 0, %s, NULL, %s)"
        self.execute_query(query, (wallet_id, amount, note))
        
    def insert_raw_transaction(self, wallet_id, tx_type, amount, date_str, note):
        query = "INSERT INTO transactions (wallet_id, type, amount, note) VALUES (%s, %s, %s, %s)"
        self.execute_query(query, (wallet_id, tx_type, amount, f"[{date_str}] {note}"))

    def get_transactions_paginated(self, limit=5, offset=0, filter_type='ALL', symbol=None):
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = %s"
            params.append(symbol.upper())
        elif filter_type in ['CASH', 'STOCK', 'CRYPTO', 'OTHER']:
            query += " AND wallet_id = %s"
            params.append(filter_type)
            
        query += " ORDER BY id DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        return self.execute_query(query, tuple(params), fetch_all=True)

    def get_transactions_count(self, filter_type='ALL', symbol=None):
        query = "SELECT COUNT(*) as total FROM transactions WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = %s"
            params.append(symbol.upper())
        elif filter_type in ['CASH', 'STOCK', 'CRYPTO', 'OTHER']:
            query += " AND wallet_id = %s"
            params.append(filter_type)
            
        res = self.execute_query(query, tuple(params), fetch_one=True)
        return res['total'] if res else 0

    def delete_holding_and_refund(self, symbol):
        symbol = symbol.upper()
        holding = self.execute_query("SELECT * FROM holdings WHERE symbol = %s", (symbol,), fetch_one=True)
        if not holding:
            return False, f"⚠️ Lỗi: Không tìm thấy mã **{symbol}** trong danh mục."
            
        wallet_id = holding['wallet_id']
        cost_basis = holding['cost_basis_vnd']
        
        self.execute_query("UPDATE wallets SET balance = balance + %s WHERE id = %s", (cost_basis, wallet_id))
        self.execute_query("DELETE FROM holdings WHERE wallet_id = %s AND symbol = %s", (wallet_id, symbol))
        self.execute_query("INSERT INTO transactions (wallet_id, type, amount, note) VALUES (%s, 'HOAN_TIEN', %s, %s)", 
                           (wallet_id, cost_basis, f"Đã xóa mã {symbol} do gõ nhầm và hoàn vốn gốc"))
                           
        return True, f"🗑️ **ĐÃ XÓA MÃ {symbol}**\n━━━━━━━━━━━━━━━━━━━\n✅ Hoàn trả lại Sức mua: **+ {cost_basis:,.0f} đ** vào ví {wallet_id}."

    def undo_transaction(self, tx_id):
        tx = self.execute_query("SELECT * FROM transactions WHERE id = %s", (tx_id,), fetch_one=True)
        if not tx:
            return False, f"⚠️ Lỗi: Không tìm thấy giao dịch ID #{tx_id}."
            
        tx_type = tx['type']
        wallet_id = tx['wallet_id']
        amount = tx['amount']
        symbol = tx['symbol']
        
        if tx_type == 'BAN':
            qty = tx['quantity']
            price = tx['price']
            realized_pl = tx['realized_pl'] or 0
            
            self.execute_query("UPDATE wallets SET balance = balance - %s WHERE id = %s", (amount, wallet_id))
            
            original_cost = amount - realized_pl
            holding = self.execute_query("SELECT * FROM holdings WHERE wallet_id = %s AND symbol = %s", (wallet_id, symbol), fetch_one=True)
            
            if holding:
                new_qty = holding['quantity'] + qty
                new_cost = holding['cost_basis_vnd'] + original_cost
                new_avg = new_cost / new_qty
                self.execute_query("UPDATE holdings SET quantity = %s, cost_basis_vnd = %s, average_price = %s WHERE wallet_id = %s AND symbol = %s", (new_qty, new_cost, new_avg, wallet_id, symbol))
            else:
                new_avg = original_cost / qty
                self.execute_query("INSERT INTO holdings (wallet_id, symbol, quantity, average_price, current_price, cost_basis_vnd) VALUES (%s, %s, %s, %s, %s, %s)", (wallet_id, symbol, qty, new_avg, price, original_cost))
                
            self.execute_query("DELETE FROM transactions WHERE id = %s", (tx_id,))
            return True, f"⏪ **ĐÃ HOÀN TÁC LỆNH BÁN #{tx_id}**\n✅ Phục hồi **{qty} {symbol}** vào danh mục.\n✅ Đã thu hồi **{amount:,.0f} đ** khỏi sức mua ví {wallet_id}."
            
        return False, "⚠️ Cỗ máy thời gian hiện tại chỉ hỗ trợ Hủy/Hoàn tác lệnh **BÁN (BAN)**."

    def add_cash_dividend(self, symbol, amount):
        symbol = symbol.upper()
        self.execute_query("UPDATE wallets SET balance = balance + %s WHERE id = 'STOCK'", (amount,))
        self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, amount, realized_pl, note) VALUES ('STOCK', 'CO_TUC_TIEN', %s, %s, %s, %s)", 
                           (symbol, amount, amount, f"Nhận cổ tức tiền mặt mã {symbol}"))
        return True, f"💸 **CỔ TỨC TIỀN MẶT: {symbol}**\n✅ Đã cộng **+ {amount:,.0f} đ** vào Sức mua."

    def add_stock_dividend(self, symbol, quantity):
        symbol = symbol.upper()
        holding = self.execute_query("SELECT quantity, cost_basis_vnd FROM holdings WHERE wallet_id = 'STOCK' AND symbol = %s", (symbol,), fetch_one=True)
        if not holding:
            return False, f"⚠️ Không có mã **{symbol}** để nhận cổ tức."
        new_qty = holding['quantity'] + quantity
        new_avg = holding['cost_basis_vnd'] / new_qty
        self.execute_query("UPDATE holdings SET quantity = %s, average_price = %s WHERE wallet_id = 'STOCK' AND symbol = %s", (new_qty, new_avg, symbol))
        self.execute_query("INSERT INTO transactions (wallet_id, type, symbol, quantity, price, amount, note) VALUES ('STOCK', 'CO_TUC_CP', %s, %s, 0, 0, %s)", 
                           (symbol, quantity, f"Nhận cổ tức cổ phiếu mã {symbol}"))
        return True, f"🎁 **CỔ TỨC CỔ PHIẾU: {symbol}**\n✅ Đã cộng **+ {quantity:,.0f} cổ phiếu** vào danh mục."

    def get_report_raw_data(self):
        return {
            "wallets": self.execute_query("SELECT * FROM wallets", fetch_all=True),
            "holdings": self.execute_query("SELECT * FROM holdings", fetch_all=True),
            "transactions": self.execute_query("SELECT * FROM transactions ORDER BY id DESC", fetch_all=True),
            "settings": {s['key']: s['value'] for s in self.execute_query("SELECT * FROM settings", fetch_all=True)}
        }
