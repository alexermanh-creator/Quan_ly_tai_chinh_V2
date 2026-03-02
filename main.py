import sys
import os

# Nạp đường dẫn gốc để import mượt mà
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.telegram.bot_client import bot
from backend.telegram.keyboards import get_home_keyboard, get_stock_keyboard
from backend.database.repository import DatabaseRepo
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.wallet import WalletModule

# Khởi tạo các thành phần
db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
wallet_mod = WalletModule()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "🌟 CHÀO MỪNG SẾP ĐẾN VỚI HỆ ĐIỀU HÀNH TÀI CHÍNH V2.0 🌟\n"
        "Hệ thống đã sẵn sàng nhận lệnh. Vui lòng chọn menu bên dưới:"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_home_keyboard())

# --- 1. XỬ LÝ LỆNH VÍ (nap, rut, chuyen, thu) ---
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ']))
def handle_wallet_commands(message):
    response = wallet_mod.handle_fund_command(message.text)
    if response:
        bot.reply_to(message, response)

# --- 2. XỬ LÝ LỆNH GIAO DỊCH (s, c) ---
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['s ', 'c ']))
def handle_trading_commands(message):
    from backend.core.parser import parse_trade_command
    from config import RATE_STOCK, RATE_CRYPTO
    
    parsed = parse_trade_command(message.text)
    if not parsed:
        bot.reply_to(message, "❌ Cú pháp sai. Vui lòng dùng: s [MÃ] [SL] [GIÁ]")
        return
        
    wallet_type, symbol, quantity, price = parsed
    action = "MUA" if quantity > 0 else "BÁN"
    rate = RATE_STOCK if wallet_type == 'STOCK' else RATE_CRYPTO
    actual_price = price * rate
    total_value = abs(quantity) * actual_price
    
    try:
        realized_pl = db.execute_trade(wallet_type, symbol, quantity, actual_price, total_value)
        reply_msg = f"✅ Đã ghi nhận lệnh {action} {abs(quantity)} {symbol}\nThành tiền: {total_value:,.0f} đ"
        if action == "BÁN":
            reply_msg += f"\n💰 Lãi/Lỗ chốt (Realized P/L): {realized_pl:,.0f} đ"
        bot.reply_to(message, reply_msg)
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

# --- 3. XỬ LÝ NÚT BẤM BÀN PHÍM ---

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def handle_stock_menu(message):
    """Bấm nút Stock -> Hiện danh mục STOCK + Đổi bàn phím STOCK"""
    text = stock_mod.get_dashboard()
    bot.send_message(message.chat.id, text, reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text == "💼 Tài sản của bạn")
def show_dashboard(message):
    """Bấm nút Dashboard -> Hiện tổng quan + Giữ bàn phím HOME"""
    text = dash.get_main_dashboard()
    bot.send_message(message.chat.id, text, reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "🏠 Trang chủ")
def handle_home_menu(message):
    """Quay lại Menu HOME"""
    bot.send_message(message.chat.id, "Đã quay lại Màn hình chính 🏠", reply_markup=get_home_keyboard())

# Khởi chạy
if __name__ == "__main__":
    print("🚀 Hệ điều hành Tài chính V2.0 đang chạy...")
    bot.infinity_polling()
