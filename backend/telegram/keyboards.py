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
    # Đúng Menu Sếp yêu cầu: 2 hàng, mỗi hàng 2 nút
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_trade = types.KeyboardButton("➕ Giao dịch")
    btn_refresh = types.KeyboardButton("🔄 Cập nhật giá")
    btn_report = types.KeyboardButton("📈 Báo cáo nhóm")
    btn_home = types.KeyboardButton("🏠 Trang chủ")
    
    markup.row(btn_trade, btn_refresh)
    markup.row(btn_report, btn_home)
    return markup
