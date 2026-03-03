# main.py
import sys, os, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.telegram.bot_client import bot
from backend.telegram.keyboards import get_home_keyboard, get_stock_keyboard, get_crypto_keyboard
from backend.database.repository import DatabaseRepo
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.wallet import WalletModule
from backend.modules.crypto import CryptoModule
from backend.core.parser import parse_currency, parse_trade_command

db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
crypto_mod = CryptoModule()
wallet_mod = WalletModule()

user_context = {}

@bot.message_handler(func=lambda message: message.text in ["🏠 Trang chủ", "💼 Tài sản của bạn"] or message.text == "/start")
def show_home(message): 
    user_context[message.chat.id] = 'HOME'
    bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message): 
    user_context[message.chat.id] = 'STOCK'
    bot.send_message(message.chat.id, stock_mod.get_dashboard(), reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text in ["🪙 Crypto", "🟡 Crypto"])
def show_crypto(message):
    user_context[message.chat.id] = 'CRYPTO'
    bot.send_message(message.chat.id, crypto_mod.get_dashboard(), reply_markup=get_crypto_keyboard())

@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def show_report(message):
    ctx = user_context.get(message.chat.id, 'STOCK')
    mod = crypto_mod if ctx == 'CRYPTO' else stock_mod
    bot.send_message(message.chat.id, mod.get_group_report())

@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ', 'rate ']))
def handle_manual_commands(message):
    text = message.text.lower().strip()
    try:
        if text.startswith('rate crypto '):
            val = text.replace('rate crypto ', '').strip()
            db.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('crypto_rate', ?)", (val,))
            bot.reply_to(message, f"✅ Tỷ giá Crypto: 1 USD = {float(val):,.0f} đ")
        
        elif text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
            bot.reply_to(message, wallet_mod.handle_fund_command(message.text))

        elif text.startswith('k '):
            parts = text.split()
            name, val = parts[1].upper(), parse_currency(" ".join(parts[2:]))
            db.update_other_asset(name, val)
            bot.reply_to(message, f"✅ Ghi nhận {name}: {val:,.0f} đ")

        elif text.startswith('up '):
            parts = text.split()
            sym, p = parts[1].upper(), float(parts[2])
            real_p = p * 1000 if (p < 1000 and sym not in ['BTC', 'ETH', 'SOL', 'BNB']) else p
            db.update_market_price(sym, real_p)
            bot.reply_to(message, f"✅ {sym} = {real_p:,.2f}")

        elif text.startswith(('s ', 'c ')):
            parsed = parse_trade_command(text)
            if not parsed: return
            w_type, sym, qty, price = parsed
            
            # Fix mệnh giá Stock
            if w_type == 'STOCK' and price < 1000: price *= 1000
            
            rate = 1
            if w_type == 'CRYPTO':
                r_row = db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
                rate = float(r_row['value']) if r_row else 25000.0

            total_vnd = abs(qty) * price * rate
            res = db.execute_trade(w_type, sym, qty, price, total_vnd)
            
            # Fix SL hiển thị số thập phân cho Crypto
            sl_str = f"{abs(qty)}" if w_type == 'CRYPTO' else f"{abs(qty):,.0f}"
            msg = f"✅ Khớp {'MUA' if qty>0 else 'BÁN'} {sl_str} {sym}"
            if qty < 0: msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)
    except Exception as e: bot.reply_to(message, f"❌ Lỗi: {str(e)}")

if __name__ == "__main__":
    bot.polling(none_stop=True)
