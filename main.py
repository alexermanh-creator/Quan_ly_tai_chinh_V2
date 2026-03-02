import sys
import os

# Nạp đường dẫn gốc để import mượt mà
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.telegram.bot_client import bot
from backend.telegram.keyboards import get_home_keyboard, get_stock_keyboard
from backend.database.repository import DatabaseRepo
from backend.modules.dashboard import DashboardModule
dash = DashboardModule()

# Khởi tạo kết nối DB
db = DatabaseRepo()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Lệnh /start hiển thị Menu HOME"""
    welcome_text = (
        "🌟 CHÀO MỪNG SẾP ĐẾN VỚI HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0 🌟\n"
        "Hệ thống đã sẵn sàng nhận lệnh. Vui lòng chọn menu bên dưới:"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_home_keyboard())

# --- XỬ LÝ NÚT BẤM TỪ BÀN PHÍM ---

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def handle_stock_menu(message):
    """Khi bấm vào Chứng Khoán -> Hiện danh mục STOCK + Đổi bàn phím"""
    text = dash.get_stock_dashboard()
    bot.send_message(message.chat.id, text, reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text == "🏠 Trang chủ")
def handle_home_menu(message):
    """Khi bấm Trang chủ -> Quay lại bàn phím HOME"""
    bot.send_message(message.chat.id, "Đã quay lại Màn hình chính 🏠", reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "💼 Tài sản của bạn")
def show_dashboard(message):
    """Hiển thị Dashboard Tổng quan"""
    text = dash.get_main_dashboard()
    bot.send_message(message.chat.id, text, reply_markup=get_home_keyboard())

# --- XỬ LÝ LỆNH GÕ TAY (PARSER) ---

@bot.message_handler(func=lambda message: message.text.lower().startswith(('s ', 'c ')))
def handle_trading_commands(message):
    """Bắt các lệnh gõ tay s (Stock) và c (Crypto)"""
    from backend.core.parser import parse_trade_command
    from config import RATE_STOCK, RATE_CRYPTO
    
    parsed = parse_trade_command(message.text)
    if not parsed:
        bot.reply_to(message, "❌ Cú pháp sai. Vui lòng dùng: s [MÃ] [SL] [GIÁ] (Ví dụ: s HAH -400 80)")
        return
        
    wallet_type, symbol, quantity, price = parsed
    action = "MUA" if quantity > 0 else "BÁN"
    
    # Tính toán tỷ giá
    rate = RATE_STOCK if wallet_type == 'STOCK' else RATE_CRYPTO
    actual_price = price * rate
    total_value = abs(quantity) * actual_price
    
    try:
        # Ghi vào DB
        realized_pl = db.execute_trade(wallet_type, symbol, quantity, actual_price, total_value)
        
        # Phản hồi
        reply_msg = (
            f"✅ Đã ghi nhận lệnh {action} {abs(quantity)} {symbol}\n"
            f"Thành tiền: {total_value:,.0f} đ"
        )
        if action == "BÁN":
            reply_msg += f"\n💰 Lãi/Lỗ chốt (Realized P/L): {realized_pl:,.0f} đ"
            
        bot.reply_to(message, reply_msg)
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi giao dịch: {str(e)}")

# Khởi chạy hệ thống 24/7
if __name__ == "__main__":
    print("🚀 Hệ điều hành Tài chính V2.0 đang chạy...")
    bot.infinity_polling()

