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

# --- 1. XỬ LÝ NÚT BẤM MENU ---

@bot.message_handler(func=lambda message: message.text in ["💼 Tài sản của bạn", "🏠 Trang chủ"] or message.text == "/start")
def show_home(message): 
    bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message): 
    # Khi bấm nút này, Bot hiện Dashboard Stock kèm Menu Giao dịch mới
    bot.send_message(message.chat.id, stock_mod.get_dashboard(), reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text == "➕ Giao dịch")
def trade_instruction(message):
    msg = (
        "➕ **HƯỚNG DẪN GIAO DỊCH NHANH**\n\n"
        "Sếp gõ lệnh theo cú pháp sau:\n"
        "🔹 **Mua:** `s [MÃ] [SL] [GIÁ]`\n"
        "🔹 **Bán:** `s [MÃ] -[SL] [GIÁ]`\n\n"
        "👉 **Ví dụ:** `s HPG 1000 28.5` (Mua 1k HPG giá 28.5)"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def stock_refresh_instruction(message):
    msg = "🔄 **CẬP NHẬT GIÁ THỊ TRƯỜNG**\n\nSếp gõ: `up [MÃ] [GIÁ]`\n👉 Ví dụ: `up FPT 120`"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def show_report(message): 
    bot.send_message(message.chat.id, stock_mod.get_group_report())

# --- 2. XỬ LÝ THIẾT LẬP MỤC TIÊU ---
@bot.message_handler(func=lambda message: message.text.lower().startswith('set goal '))
def handle_set_goal(message):
    goal_str = message.text.lower().replace('set goal ', '').strip()
    db.set_goal(goal_str)
    bot.reply_to(message, f"🎯 Đã thiết lập mục tiêu: {goal_str}")

# --- 3. HANDLER TỔNG HỢP LỆNH GÕ TAY ---
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ']))
def handle_manual_commands(message):
    text = message.text.lower()
    
    # Dòng tiền
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        if "other" in text:
            try:
                val = parse_currency(text.replace('chuyen other', '').strip())
                db.transfer_funds('CASH', 'OTHER', val)
                bot.reply_to(message, f"✅ Đã cấp vốn {val:,.0f} đ cho Ví OTHER.")
            except: bot.reply_to(message, "❌ Lỗi lệnh chuyển.")
        else: bot.reply_to(message, wallet_mod.handle_fund_command(message.text))

    # Tài sản khác
    elif text.startswith('k '):
        try:
            parts = text.split()
            name, val = parts[1], parse_currency(" ".join(parts[2:]))
            db.update_other_asset(name, val)
            bot.reply_to(message, f"✅ Đã ghi nhận {name}: {val:,.0f} đ")
        except: bot.reply_to(message, "❌ Lỗi: `k BDS 500tr`")

    # Cập nhật giá (up)
    elif text.startswith('up '):
        try:
            parts = text.split()
            sym, price = parts[1].upper(), float(parts[2])
            real_p = price * 1000 if price < 1000 else price
            db.update_market_price(sym, real_p)
            bot.reply_to(message, f"✅ {sym} = {real_p/1000:,.1f}k")
        except: bot.reply_to(message, "❌ Lỗi: `up FPT 120`")

    # Giao dịch (s/c)
    else:
        parsed = parse_trade_command(text)
        if not parsed: return
        w_type, sym, qty, price = parsed
        rate = RATE_STOCK if w_type == 'STOCK' else RATE_CRYPTO
        try:
            res = db.execute_trade(w_type, sym, qty, price * rate, abs(qty) * price * rate)
            msg = f"✅ Khớp {'MUA' if qty>0 else 'BÁN'} {abs(qty):,.0f} {sym}"
            if qty < 0: msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)
        except Exception as e: bot.reply_to(message, f"❌ {str(e)}")

# --- 4. KHỞI CHẠY ---
if __name__ == "__main__":
    print("🚀 Bot Finance V2.0 đang trực chiến...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            time.sleep(5)
