# backend/telegram/keyboards.py
from telebot import types

def get_home_keyboard():
    """Bàn phím (Menu HOME) - Đã căn chỉnh layout chuẩn"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Hàng 1: Nút to nhất (Full width)
    markup.add(types.KeyboardButton("💼 Tài sản của bạn"))
    
    # Hàng 2: Hai trụ cột chính
    markup.row(types.KeyboardButton("📊 Chứng Khoán"), types.KeyboardButton("🪙 Crypto"))
    
    # Hàng 3: Tiện ích mở rộng
    markup.row(types.KeyboardButton("🥇 Tài sản khác"), types.KeyboardButton("📜 Lịch sử"))
    
    # Hàng 4: Phân tích & Trợ lý
    markup.row(types.KeyboardButton("📊 Báo cáo"), types.KeyboardButton("🤖 AI Chat"))
    
    # Hàng 5: Hệ thống
    markup.row(types.KeyboardButton("⚙️ Cài đặt"), types.KeyboardButton("📥 EXPORT/IMPORT"))
    
    return markup

def get_stock_keyboard():
    """Bàn phím (Menu STOCK) - 2 hàng, mỗi hàng 2 nút chuẩn ý Sếp"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    btn_trade = types.KeyboardButton("➕ Giao dịch")
    btn_refresh = types.KeyboardButton("🔄 Cập nhật giá")
    btn_report = types.KeyboardButton("📈 Báo cáo nhóm")
    btn_home = types.KeyboardButton("🏠 Trang chủ")
    
    markup.row(btn_trade, btn_refresh)
    markup.row(btn_report, btn_home)
    
    return markup
