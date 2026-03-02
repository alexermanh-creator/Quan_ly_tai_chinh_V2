# main.py
import sys, os, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.telegram.bot_client import bot
from backend.telegram.keyboards import get_home_keyboard, get_stock_keyboard
from backend.database.repository import DatabaseRepo
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.wallet import WalletModule
from backend.core.parser import parse_currency, parse_trade_command
from config import RATE_STOCK, RATE_CRYPTO

db, dash, stock_mod, wallet_mod = DatabaseRepo(), DashboardModule(), StockModule(), WalletModule()

@bot.message_handler(func=lambda message: message.text in ["🏠 Trang chủ", "💼 Tài sản của bạn"] or message.text == "/start")
def show_home(message): bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message): bot.send_message(message.chat.id, stock_mod.get_dashboard(), reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text == "➕ Giao dịch")
def trade_ins(message): bot.reply_to(message, "➕ Gõ: `s [MÃ] [SL] [GIÁ]`\nVí dụ: `s HPG 1000 28.5`")

@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def refresh_ins(message): bot.reply_to(message, "🔄 Gõ: `up [MÃ] [GIÁ]`\nVí dụ: `up FPT 120`")

@bot.message_handler(func=lambda message: message.text.lower().startswith('set goal '))
def handle_set_goal(message):
    db.set_goal(message.text.lower().replace('set goal ', '').strip())
    bot.reply_to(message, "🎯 Đã cập nhật mục tiêu.")

@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ']))
def handle_all(message):
    text = message.text.lower()
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        if "other" in text:
            try:
                val = parse_currency(text.replace('chuyen other',''))
                db.transfer_funds('CASH', 'OTHER', val)
                bot.reply_to(message, f"✅ Đã cấp vốn {val:,.0f} đ cho Ví OTHER.")
            except: bot.reply_to(message, "❌ Lỗi lệnh.")
        else: bot.reply_to(message, wallet_mod.handle_fund_command(message.text))
    elif text.startswith('k '):
        try:
            parts = text.split(); name, val = parts[1], parse_currency(" ".join(parts[2:]))
            db.update_other_asset(name, val); bot.reply_to(message, f"✅ Ghi nhận {name}: {val:,.0f} đ")
        except: bot.reply_to(message, "❌ Lỗi: `k BDS 500tr`")
    elif text.startswith('up '):
        try:
            parts = text.split(); sym, price = parts[1].upper(), float(parts[2])
            real_p = price * 1000 if price < 1000 else price
            db.update_market_price(sym, real_p); bot.reply_to(message, f"✅ {sym} = {real_p/1000:,.1f}k")
        except: bot.reply_to(message, "❌ Lỗi: `up FPT 120`")
    else:
        parsed = parse_trade_command(text)
        if not parsed: return
        w_type, sym, qty, price = parsed
        rate = RATE_STOCK if w_type == 'STOCK' else RATE_CRYPTO
        try:
            res = db.execute_trade(w_type, sym, qty, price * rate, abs(qty) * price * rate)
            bot.reply_to(message, f"✅ Khớp {sym}" + (f"\n💰 Lãi chốt: {res:,.0f} đ" if qty<0 else ""))
        except Exception as e: bot.reply_to(message, f"❌ {str(e)}")

if __name__ == "__main__":
    print("🚀 Bot Finance V2.0 đang trực chiến...")
    bot.infinity_polling()
