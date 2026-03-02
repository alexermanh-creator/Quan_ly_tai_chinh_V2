import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.telegram.bot_client import bot
from backend.telegram.keyboards import get_home_keyboard, get_stock_keyboard
from backend.database.repository import DatabaseRepo
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.wallet import WalletModule

db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
wallet_mod = WalletModule()

# --- HANDLER TRANG CHỦ ---
@bot.message_handler(func=lambda message: message.text in ["💼 Tài sản của bạn", "🏠 Trang chủ"] or message.text == "/start")
def show_home(message):
    text = dash.get_main_dashboard()
    bot.send_message(message.chat.id, text, reply_markup=get_home_keyboard())

# --- HANDLER STOCK ---
@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message):
    text = stock_mod.get_dashboard()
    bot.send_message(message.chat.id, text, reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text == "➕ Giao dịch")
def stock_trade_help(message):
    msg = "📝 **HƯỚNG DẪN:**\n• Mua: `s HPG 100 30`\n• Bán: `s HPG -100 35`"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def stock_price_instruction(message):
    msg = "🔄 **CẬP NHẬT GIÁ THỊ TRƯỜNG:**\nHãy gõ lệnh: `up [MÃ] [GIÁ]`\n\nVí dụ: `up HPG 35` (Bot tự nhân x1000)"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def stock_report(message):
    # NÂNG CẤP: Gọi hàm báo cáo tài chính chi tiết
    text = stock_mod.get_group_report()
    bot.send_message(message.chat.id, text)

# --- HANDLER LỆNH GÕ TAY (Bổ sung lệnh up) ---
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'up ']))
def handle_commands(message):
    text = message.text.lower()
    
    # 1. Lệnh Ví
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        bot.reply_to(message, wallet_mod.handle_fund_command(message.text))
    
    # 2. Lệnh cập nhật giá nhanh
    elif text.startswith('up '):
        try:
            parts = message.text.split()
            symbol = parts[1].upper()
            new_price = float(parts[2])
            from config import RATE_STOCK
            db.update_market_price(symbol, new_price * RATE_STOCK)
            bot.reply_to(message, f"✅ Đã cập nhật giá {symbol} = {new_price:,.1f}k")
        except:
            bot.reply_to(message, "❌ Lỗi cú pháp! VD: `up HPG 35`")

    # 3. Lệnh Giao dịch s, c
    else:
        from backend.core.parser import parse_trade_command
        from config import RATE_STOCK, RATE_CRYPTO
        parsed = parse_trade_command(message.text)
        if not parsed:
            bot.reply_to(message, "❌ Sai cú pháp.")
            return
        w_type, sym, qty, price = parsed
        rate = RATE_STOCK if w_type == 'STOCK' else RATE_CRYPTO
        try:
            res = db.execute_trade(w_type, sym, qty, price * rate, abs(qty) * price * rate)
            msg = f"✅ Khớp lệnh {'MUA' if qty>0 else 'BÁN'} {abs(qty)} {sym}"
            if qty < 0: msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)
        except Exception as e:
            bot.reply_to(message, f"❌ {str(e)}")

if __name__ == "__main__":
    bot.infinity_polling()
