from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def get_home_keyboard():
    """Bàn phím (Menu HOME)"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # Hàng 1: Nút to full width
    markup.add(KeyboardButton("💼 Tài sản của bạn"))
    # Hàng 2
    markup.row(KeyboardButton("📊 Chứng Khoán"), KeyboardButton("🪙 Crypto"))
    # Hàng 3
    markup.row(KeyboardButton("🥇 Tài sản khác"), KeyboardButton("📜 Lịch sử"))
    # Hàng 4
    markup.row(KeyboardButton("📊 Báo cáo"), KeyboardButton("🤖 AI Chat"))
    # Hàng 5
    markup.row(KeyboardButton("⚙️ Cài đặt"), KeyboardButton("📥 EXPORT/IMPORT"))
    return markup

def get_stock_keyboard():
    """Bàn phím (Menu STOCK)"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # Hàng 1
    markup.row(KeyboardButton("➕ Giao dịch"), KeyboardButton("🔄 Cập nhật giá"))
    # Hàng 2
    markup.row(KeyboardButton("📈 Báo cáo nhóm"), KeyboardButton("🏠 Trang chủ"))
    return markup
