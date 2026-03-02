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
def stock_refresh(message):
    text = stock_mod.get_dashboard()
    bot.send_message(message.chat.id, "🔄 Dữ liệu mới nhất:\n\n" + text)

@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def stock_report(message):
    bot.send_message(message.chat.id, "📊 Tính năng đang phát triển...")

# --- HANDLER LỆNH GÕ TAY ---
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ']))
def handle_commands(message):
    text = message.text.lower()
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        bot.reply_to(message, wallet_mod.handle_fund_command(message.text))
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
