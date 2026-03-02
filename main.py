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

# Khởi tạo các Module
db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
wallet_mod = WalletModule()

# --- 1. HANDLER NÚT BẤM (KEYBOARD) ---
@bot.message_handler(func=lambda message: message.text in ["💼 Tài sản của bạn", "🏠 Trang chủ"] or message.text == "/start")
def show_home(message): 
    bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message): 
    bot.send_message(message.chat.id, stock_mod.get_dashboard(), reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def show_report(message): 
    bot.send_message(message.chat.id, stock_mod.get_group_report())

@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def stock_refresh_instruction(message):
    msg = "🔄 **HƯỚNG DẪN CẬP NHẬT GIÁ NHANH**\n\nCú pháp: `up [MÃ] [GIÁ]`\n👉 **Ví dụ:** `up HPG 28.5`\nSau đó bấm lại **📊 Chứng Khoán** để xem NAV mới!"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

# --- 2. HANDLER LỆNH ĐẶT MỤC TIÊU ---
@bot.message_handler(func=lambda message: message.text.lower().startswith('set goal '))
def handle_set_goal(message):
    goal_str = message.text.lower().replace('set goal ', '').strip()
    db.set_goal(goal_str)
    bot.reply_to(message, f"🎯 Đã thiết lập mục tiêu: {goal_str}\nBấm [🏠 Trang chủ] để xem tiến độ.")

# --- 3. HANDLER TẤT CẢ LỆNH GÕ TAY (INTEGRATED) ---
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ']))
def handle_all_manual_commands(message):
    text = message.text.lower()
    
    # Nhóm 1: Dòng tiền (Nap/Rut/Chuyen/Thu)
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        bot.reply_to(message, wallet_mod.handle_fund_command(message.text))
    
    # Nhóm 2: Tài sản khác (Lệnh k)
    elif text.startswith('k '):
        try:
            parts = text.split()
            if len(parts) < 3: raise ValueError
            name = parts[1].upper()
            val = parse_currency(" ".join(parts[2:]))
            db.update_other_asset(name, val)
            bot.reply_to(message, f"✅ Đã ghi nhận tài sản {name}: {val:,.0f} đ")
        except:
            bot.reply_to(message, "❌ Cú pháp: `k [TÊN] [GIÁ TRỊ]`\nVD: `k VANG 85 trieu` hay `k OTO 1.2 ty`")
            
    # Nhóm 3: Cập nhật giá (Lệnh up)
    elif text.startswith('up '):
        try:
            parts = text.split()
            symbol, price = parts[1].upper(), float(parts[2])
            from config import RATE_STOCK
            db.update_market_price(symbol, price * RATE_STOCK)
            bot.reply_to(message, f"✅ Cập nhật {symbol} = {price:,.1f}k")
        except:
            bot.reply_to(message, "❌ Cú pháp: `up HPG 35`")
            
    # Nhóm 4: Giao dịch Stock/Crypto (Lệnh s/c)
    else:
        parsed = parse_trade_command(message.text)
        if not parsed:
            bot.reply_to(message, "❌ Sai cú pháp lệnh giao dịch.")
            return
            
        w_type, sym, qty, price = parsed
        from config import RATE_STOCK, RATE_CRYPTO
        rate = RATE_STOCK if w_type == 'STOCK' else RATE_CRYPTO
        
        try:
            res = db.execute_trade(w_type, sym, qty, price * rate, abs(qty) * price * rate)
            msg = f"✅ Khớp {'MUA' if qty > 0 else 'BÁN'} {abs(qty):,.0f} {sym}"
            if qty < 0:
                msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)
        except Exception as e:
            bot.reply_to(message, f"❌ {str(e)}")

# --- 4. HANDLER GỢI Ý THÔNG MINH (CATCH-ALL) ---
# Thằng này PHẢI nằm cuối cùng
@bot.message_handler(func=lambda message: True)
def handle_smart_hints(message):
    parts = message.text.split()
    if len(parts) >= 3 and parts[1].replace('.','',1).isdigit():
        bot.reply_to(message, "💡 Sếp quên gõ lệnh `s`, `c` hoặc `k` ở đầu rồi!\nVí dụ: `s HPG 1000 30` hoặc `k VANG 85tr`.")
    else:
        bot.reply_to(message, "❓ Lệnh không rõ ràng. Sếp dùng Menu hoặc gõ đúng cú pháp nhé.")

# --- 5. KHỞI CHẠY VÀ HỒI SINH TỰ ĐỘNG ---
if __name__ == "__main__":
    print("🚀 Bot Finance V2.0 đang trực chiến...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Telegram: {e}")
            time.sleep(5)
