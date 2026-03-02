import sys
import os
# Đảm bảo root được thêm vào path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

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

@bot.message_handler(func=lambda message: message.text in ["💼 Tài sản của bạn", "🏠 Trang chủ"] or message.text == "/start")
def show_home(message):
    bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message):
    bot.send_message(message.chat.id, stock_mod.get_dashboard(), reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def show_report(message):
    bot.send_message(message.chat.id, stock_mod.get_group_report())

# HANDLER LỆNH GÕ TAY (PHẢI NẰM TRÊN CÁC HANDLER GỢI Ý)
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'up ']))
def handle_commands(message):
    text = message.text.lower()
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        bot.reply_to(message, wallet_mod.handle_fund_command(message.text))
    elif text.startswith('up '):
        try:
            parts = message.text.split()
            symbol, price = parts[1].upper(), float(parts[2])
            from config import RATE_STOCK
            db.update_market_price(symbol, price * RATE_STOCK)
            bot.reply_to(message, f"✅ Cập nhật {symbol} = {price:,.1f}k")
        except: bot.reply_to(message, "❌ Cú pháp: `up HPG 35`")
    else:
        from backend.core.parser import parse_trade_command
        from config import RATE_STOCK, RATE_CRYPTO
        parsed = parse_trade_command(message.text)
        if not parsed: return
        w_type, sym, qty, price = parsed
        rate = RATE_STOCK if w_type == 'STOCK' else RATE_CRYPTO
        try:
            res = db.execute_trade(w_type, sym, qty, price * rate, abs(qty) * price * rate)
            msg = f"✅ Khớp {'MUA' if qty>0 else 'BÁN'} {abs(qty)} {sym}"
            if qty < 0: msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)
        except Exception as e: bot.reply_to(message, f"❌ {str(e)}")

# HANDLER GỢI Ý (NẰM CUỐI CÙNG)
@bot.message_handler(func=lambda message: True)
def handle_smart_hints(message):
    parts = message.text.split()
    if len(parts) >= 3 and parts[1].replace('.','',1).isdigit():
        bot.reply_to(message, "💡 Sếp quên gõ lệnh `s` hoặc `c` ở đầu rồi!")

if __name__ == "__main__":
    bot.infinity_polling()
