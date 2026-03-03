# backend/telegram/keyboards.py
from telebot import types

def get_home_keyboard():
    """Bàn phím (Menu HOME)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("💼 Tài sản của bạn"))
    markup.row(types.KeyboardButton("📊 Chứng Khoán"), types.KeyboardButton("🪙 Crypto"))
    markup.row(types.KeyboardButton("🥇 Tài sản khác"), types.KeyboardButton("📜 Lịch sử"))
    markup.row(types.KeyboardButton("📊 Báo cáo"), types.KeyboardButton("🤖 AI Chat"))
    markup.row(types.KeyboardButton("⚙️ Cài đặt"), types.KeyboardButton("📥 EXPORT/IMPORT"))
    return markup

def get_stock_keyboard():
    """Bàn phím (Menu STOCK)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(types.KeyboardButton("➕ Giao dịch"), types.KeyboardButton("🔄 Cập nhật giá"))
    markup.row(types.KeyboardButton("📈 Báo cáo nhóm"), types.KeyboardButton("🏠 Trang chủ"))
    return markup

def get_crypto_keyboard():
    """Bàn phím (Menu CRYPTO - Tương tự Stock nhưng dùng riêng để dễ mở rộng)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(types.KeyboardButton("➕ Giao dịch"), types.KeyboardButton("🔄 Cập nhật giá"))
    markup.row(types.KeyboardButton("📈 Báo cáo nhóm"), types.KeyboardButton("🏠 Trang chủ"))
    return markup
