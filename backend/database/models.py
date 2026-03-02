SCHEMA = """
-- Bảng ví tiền
CREATE TABLE IF NOT EXISTS wallets (
    id TEXT PRIMARY KEY,
    balance REAL DEFAULT 0,
    total_in REAL DEFAULT 0,
    total_out REAL DEFAULT 0
);

-- Bảng danh mục đầu tư
CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id TEXT,
    symbol TEXT,
    quantity REAL DEFAULT 0,
    average_price REAL DEFAULT 0,
    UNIQUE(wallet_id, symbol)
);

-- Bảng lịch sử giao dịch
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id TEXT,
    type TEXT,
    symbol TEXT,
    quantity REAL DEFAULT 0,
    price REAL DEFAULT 0,
    amount REAL DEFAULT 0,
    realized_pl REAL DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""
