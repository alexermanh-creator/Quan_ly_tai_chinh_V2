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

db, dash, stock_mod, wallet_mod = DatabaseRepo(), DashboardModule(), StockModule(), WalletModule()

@bot.message_handler(func=lambda message: message.text in ["💼 Tài sản của bạn", "🏠 Trang chủ"] or message.text == "/start")
def show_home(message): bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message): bot.send_message(message.chat.id, stock_mod.get_dashboard(), reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def show_report(message): bot.send_message(message.chat.id, stock_mod.get_group_report())

@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def stock_refresh_instruction(message):
    msg = "🔄 **HƯỚNG DẪN CẬP NHẬT GIÁ NHANH**\n\nCú pháp: `up [MÃ] [GIÁ]`\n👉 **Ví dụ:** `up HPG 28.5`\nSau đó bấm lại **📊 Chứng Khoán** để xem NAV mới!"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text.lower().startswith('set goal '))
def handle_set_goal(message):
    goal_str = message.text.lower().replace('set goal ', '').strip()
    db.set_goal(goal_str)
    bot.reply_to(message, f"🎯 Đã thiết lập mục tiêu: {goal_str}")

# --- HANDLER TỔNG HỢP CHO MỌI LỆNH GÕ TAY ---
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ']))
def handle_all_commands(message):
    text = message.text.lower()
    
    # 1. Lệnh Ví (Nạp/Rút/Chuyển/Thu)
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        # Cho phép chuyen other
        res = wallet_mod.handle_fund_command(message.text)
        if "Chỉ hỗ trợ ví STOCK hoặc CRYPTO" in res and "other" in text:
             # Fix nóng cho lệnh chuyen other nếu wallet_mod bị cứng nhắc
             try:
                 parts = text.split()
                 val = parse_currency(" ".join(parts[2:]))
                 db.transfer_funds('CASH', 'OTHER', val)
                 res = f"✅ Đã cấp vốn {val:,.0f} đ từ Ví Mẹ -> Ví OTHER."
             except: res = "❌ Lỗi lệnh chuyển Other."
        bot.reply_to(message, res)

    # 2. Lệnh Tài sản khác (k)
    elif text.startswith('k '):
        try:
            parts = text.split()
            name, val = parts[1], parse_currency(" ".join(parts[2:]))
            db.update_other_asset(name, val)
            bot.reply_to(message, f"✅ Đã ghi nhận tài sản {name}: {val:,.0f} đ")
        except: bot.reply_to(message, "❌ Cú pháp: `k [TÊN] [GIÁ TRỊ]`")

    # 3. Lệnh cập nhật giá (up)
    elif text.startswith('up '):
        try:
            parts = text.split()
            symbol, price = parts[1].upper(), float(parts[2])
            # Tự động nhân 1000 cho chứng khoán nếu sếp gõ số thực
            rate = 1000 if price < 1000 else 1
            db.update_market_price(symbol, price * rate)
            bot.reply_to(message, f"✅ Cập nhật {symbol} = {price if rate==1 else price:,.1f}k")
        except Exception as e:
            bot.reply_to(message, "❌ Cú pháp: `up HPG 35` hoặc `up FPT 120`")

    # 4. Lệnh giao dịch (s/c)
    else:
        parsed = parse_trade_command(message.text)
        if not parsed: return
        w_type, sym, qty, price = parsed
        from config import RATE_STOCK, RATE_CRYPTO
        rate = RATE_STOCK if w_type == 'STOCK' else RATE_CRYPTO
        try:
            res = db.execute_trade(w_type, sym, qty, price * rate, abs(qty) * price * rate)
            msg = f"✅ Khớp {'MUA' if qty>0 else 'BÁN'} {abs(qty):,.0f} {sym}"
            if qty < 0: msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)
        except Exception as e: bot.reply_to(message, f"❌ {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_smart_hints(message):
    parts = message.text.split()
    if len(parts) >= 3 and parts[1].replace('.','',1).isdigit():
        bot.reply_to(message, "💡 Sếp quên gõ lệnh `s`, `c` hoặc `k` rồi!")

if __name__ == "__main__":
    print("🚀 Bot Finance V2.0 đang trực chiến...")
    while True:
        try: bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            time.sleep(5)
