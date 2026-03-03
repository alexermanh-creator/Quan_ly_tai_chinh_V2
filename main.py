# main.py
import sys, os, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from telebot import types
from backend.telegram.bot_client import bot
from backend.telegram.keyboards import get_home_keyboard, get_stock_keyboard, get_crypto_keyboard
from backend.database.repository import DatabaseRepo
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.wallet import WalletModule
from backend.modules.crypto import CryptoModule
from backend.core.parser import parse_currency, parse_trade_command

# Khởi tạo các Module hạt nhân
db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
crypto_mod = CryptoModule()
wallet_mod = WalletModule()

# Biến toàn cục để theo dõi người dùng đang ở Module nào (Stock hay Crypto)
user_context = {}

# --- 1. HANDLER MENU CHÍNH (HOME) ---

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

@bot.message_handler(func=lambda message: message.text == "🥇 Tài sản khác")
def show_other_assets(message):
    bot.reply_to(message, "🥇 **QUẢN LÝ TÀI SẢN NGOÀI SÀN**\n\nSếp dùng lệnh: `k [TÊN] [GIÁ TRỊ]`\n👉 Ví dụ: `k VANG 85tr` hoặc `k BDS_DALAT 1.2ty`.")

@bot.message_handler(func=lambda message: message.text == "📜 Lịch sử")
def show_history(message):
    bot.reply_to(message, "📜 Tính năng truy xuất 10 giao dịch gần nhất đang được tối ưu.")

@bot.message_handler(func=lambda message: message.text == "🤖 AI Chat")
def ai_chat(message):
    bot.reply_to(message, "🤖 Chào Sếp, tôi là Gemini. Sếp muốn tôi phân tích danh mục nào?")

@bot.message_handler(func=lambda message: message.text in ["📊 Báo cáo", "⚙️ Cài đặt", "📥 EXPORT/IMPORT"])
def coming_soon(message):
    bot.reply_to(message, f"🛠️ Tính năng **{message.text}** đang được hoàn thiện!")

# --- 2. HANDLER MENU PHỤ (STOCK / CRYPTO) ---

@bot.message_handler(func=lambda message: message.text == "➕ Giao dịch")
def trade_ins(message):
    msg = "➕ **LỆNH GIAO DỊCH**\n\nStock: `s [MÃ] [SL] [GIÁ VNĐ]`\nCrypto: `c [MÃ] [SL] [GIÁ USD]`\n👉 Ví dụ: `c BTC 0.5 65000`"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def refresh_ins(message):
    msg = "🔄 **CẬP NHẬT GIÁ NHANH**\n\nCú pháp: `up [MÃ] [GIÁ]`\n👉 Ví dụ: `up BTC 68000`"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def show_report(message):
    # Sửa lỗi hiển thị kép: Đứng ở ví nào, gọi báo cáo ví đó
    context = user_context.get(message.chat.id, 'STOCK')
    if context == 'CRYPTO':
        bot.send_message(message.chat.id, crypto_mod.get_group_report())
    else:
        bot.send_message(message.chat.id, stock_mod.get_group_report())

# --- 3. HANDLER SETTINGS & TỔNG HỢP ---

@bot.message_handler(func=lambda message: text_starts_with(message.text.lower(), ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ', 'set goal ', 'rate ']))
def handle_manual_commands(message):
    text = message.text.lower().strip()
    
    try:
        # Cập nhật Tỷ giá Crypto
        if text.startswith('rate crypto '):
            rate_val = text.replace('rate crypto ', '').strip()
            db.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('crypto_rate', ?)", (rate_val,))
            bot.reply_to(message, f"✅ Đã cập nhật tỷ giá Crypto: 1 USD = {float(rate_val):,.0f} VNĐ")

        # Thiết lập mục tiêu
        elif text.startswith('set goal '):
            goal = text.replace('set goal ', '').strip()
            db.set_goal(goal)
            bot.reply_to(message, f"🎯 Đã thiết lập mục tiêu: **{goal}**")

        # Luân chuyển tiền (CASH, STOCK, CRYPTO, OTHER)
        elif text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
            if "other" in text and "chuyen" in text:
                val = parse_currency(text.replace('chuyen other', '').strip())
                db.transfer_funds('CASH', 'OTHER', val)
                bot.reply_to(message, f"✅ Đã cấp vốn {val:,.0f} đ cho Ví OTHER.")
            else:
                bot.reply_to(message, wallet_mod.handle_fund_command(message.text))

        # Ghi nhận tài sản khác
        elif text.startswith('k '):
            parts = text.split()
            name, val = parts[1].upper(), parse_currency(" ".join(parts[2:]))
            db.update_other_asset(name, val)
            bot.reply_to(message, f"✅ Ghi nhận tài sản {name}: {val:,.0f} đ")

        # Cập nhật giá
        elif text.startswith('up '):
            parts = text.split()
            sym, price = parts[1].upper(), float(parts[2])
            real_p = price * 1000 if (price < 1000 and sym not in ['BTC', 'ETH', 'SOL', 'BNB']) else price
            db.update_market_price(sym, real_p)
            bot.reply_to(message, f"✅ Cập nhật {sym} = {real_p:,.2f}")

        # Giao dịch (S / C)
        elif text.startswith(('s ', 'c ')):
            parsed = parse_trade_command(text)
            if not parsed: return
            w_type, sym, qty, price = parsed
            
            # SỬA LỖI MỆNH GIÁ: Nếu là Stock và Sếp gõ giá < 1000, tự nhân 1000
            if w_type == 'STOCK' and price < 1000:
                price = price * 1000

            # Lấy tỷ giá nếu là lệnh Crypto
            rate = 1
            if w_type == 'CRYPTO':
                rate_row = db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
                rate = float(rate_row['value']) if rate_row else 25000.0

            # Tính toán tiền tệ
            total_vnd = abs(qty) * price * rate
            res = db.execute_trade(w_type, sym, qty, price, total_vnd)
            
            msg = f"✅ Khớp {'MUA' if qty>0 else 'BÁN'} {abs(qty)} {sym}"
            if w_type == 'CRYPTO': msg += f" (Tỷ giá: {rate:,.0f}đ)"
            if qty < 0: msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

def text_starts_with(text, prefixes):
    return any(text.startswith(x) for x in prefixes)

@bot.message_handler(func=lambda message: True)
def handle_smart_hints(message):
    parts = message.text.split()
    if len(parts) >= 3 and parts[1].replace('.','',1).isdigit():
        bot.reply_to(message, "💡 Sếp quên gõ lệnh `s`, `c` hoặc `k` rồi!")

if __name__ == "__main__":
    print("🚀 Hệ điều hành Tài chính V3.1 (Fixed) đang trực chiến...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Telegram: {e}")
            time.sleep(5)
