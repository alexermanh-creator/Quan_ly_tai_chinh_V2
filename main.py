# main.py
import sys, os, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.telegram.bot_client import bot
from backend.telegram.keyboards import get_home_keyboard
from backend.database.repository import DatabaseRepo
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.wallet import WalletModule
from backend.core.parser import parse_currency, parse_trade_command
from config import RATE_STOCK, RATE_CRYPTO

# Khởi tạo các Module
db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
wallet_mod = WalletModule()

# --- 1. HANDLER NÚT BẤM (KEYBOARD) ---
@bot.message_handler(func=lambda message: message.text in ["🏠 Trang chủ", "💼 Tài sản của bạn"] or message.text == "/start")
def show_home(message): 
    bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message): 
    bot.send_message(message.chat.id, stock_mod.get_dashboard())

# --- 2. HANDLER LỆNH ĐẶT MỤC TIÊU ---
@bot.message_handler(func=lambda message: message.text.lower().startswith('set goal '))
def handle_set_goal(message):
    db.set_goal(message.text.lower().replace('set goal ', '').strip())
    bot.reply_to(message, "🎯 Đã cập nhật mục tiêu mới.\nBấm [🏠 Trang chủ] để xem tiến độ.")

# --- 3. HANDLER TỔNG HỢP CHO MỌI LỆNH GÕ TAY ---
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ']))
def handle_all_commands(message):
    text = message.text.lower()
    
    # 3.1 Nhóm Ví (Nap/Rut/Chuyen/Thu)
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        if "other" in text: # Ép logic cho ví Khác (Fix lỗi Chỉ hỗ trợ Stock)
            try:
                # Bóc tách số tiền sau chữ 'chuyen other'
                amount_text = text.replace('chuyen other', '').strip()
                val = parse_currency(amount_text)
                db.transfer_funds('CASH', 'OTHER', val)
                bot.reply_to(message, f"✅ Đã cấp vốn {val:,.0f} đ cho Ví OTHER.")
            except: 
                bot.reply_to(message, "❌ Lỗi: `chuyen other 500 trieu`")
        else: 
            bot.reply_to(message, wallet_mod.handle_fund_command(message.text))

    # 3.2 Nhóm Tài sản khác (Lệnh k)
    elif text.startswith('k '):
        try:
            parts = text.split()
            if len(parts) < 3: raise ValueError
            name, val = parts[1].upper(), parse_currency(" ".join(parts[2:]))
            db.update_other_asset(name, val)
            bot.reply_to(message, f"✅ Ghi nhận tài sản {name}: {val:,.0f} đ")
        except: 
            bot.reply_to(message, "❌ Cú pháp: `k [TÊN] [GIÁ]`\nVD: `k VANG 85tr`")

    # 3.3 Nhóm Cập nhật giá (Lệnh up)
    elif text.startswith('up '):
        try:
            parts = text.split()
            if len(parts) < 3: raise ValueError
            sym, price = parts[1].upper(), float(parts[2])
            # Tự hiểu: gõ 120 -> 120,000 | gõ 120000 -> 120,000
            real_price = price * 1000 if price < 1000 else price
            db.update_market_price(sym, real_price)
            bot.reply_to(message, f"✅ Cập nhật {sym} = {real_price/1000:,.1f}k")
        except: 
            bot.reply_to(message, "❌ Cú pháp: `up FPT 120` hoặc `up HPG 28.5`")

    # 3.4 Nhóm Giao dịch (Lệnh s/c)
    else:
        parsed = parse_trade_command(text)
        if not parsed: return
        w_type, sym, qty, price = parsed
        rate = RATE_STOCK if w_type == 'STOCK' else RATE_CRYPTO
        try:
            res = db.execute_trade(w_type, sym, qty, price * rate, abs(qty) * price * rate)
            msg = f"✅ Khớp {'MUA' if qty > 0 else 'BÁN'} {abs(qty):,.0f} {sym}"
            if qty < 0:
                msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)
        except Exception as e: 
            bot.reply_to(message, f"❌ {str(e)}")

# --- 4. GỢI Ý THÔNG MINH ---
@bot.message_handler(func=lambda message: True)
def handle_smart_hints(message):
    parts = message.text.split()
    if len(parts) >= 3 and parts[1].replace('.','',1).isdigit():
        bot.reply_to(message, "💡 Sếp quên gõ lệnh `s`, `c` hoặc `k` rồi!\nVD: `s HPG 1000 30` hoặc `k VANG 85tr`")

# --- 5. VÒNG LẶP KHỞI CHẠY (LUÔN Ở CUỐI FILE) ---
if __name__ == "__main__":
    print("🚀 Bot Finance V2.0 đang trực chiến...")
    while True:
        try:
            # none_stop=True giúp bot không chết khi mất mạng
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Telegram: {e}")
            time.sleep(5) # Đợi 5 giây rồi tự hồi sinh
