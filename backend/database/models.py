# backend/database/models.py

SCHEMA = """
-- Bảng ví tiền
CREATE TABLE IF NOT EXISTS wallets (
    id TEXT PRIMARY KEY,
    balance DOUBLE PRECISION DEFAULT 0,
    total_in DOUBLE PRECISION DEFAULT 0,
    total_out DOUBLE PRECISION DEFAULT 0
);

-- Bảng danh mục đầu tư
CREATE TABLE IF NOT EXISTS holdings (
    id SERIAL PRIMARY KEY,
    wallet_id TEXT,
    symbol TEXT,
    quantity DOUBLE PRECISION DEFAULT 0,
    average_price DOUBLE PRECISION DEFAULT 0,
    current_price DOUBLE PRECISION DEFAULT 0,
    cost_basis_vnd DOUBLE PRECISION DEFAULT 0,
    UNIQUE(wallet_id, symbol)
);

-- Bảng lịch sử giao dịch
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    wallet_id TEXT,
    type TEXT,
    symbol TEXT,
    quantity DOUBLE PRECISION DEFAULT 0,
    price DOUBLE PRECISION DEFAULT 0,
    amount DOUBLE PRECISION DEFAULT 0,
    realized_pl DOUBLE PRECISION DEFAULT 0,
    note TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng cài đặt
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""
