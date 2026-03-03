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

# Khởi tạo các Module hạt nhân
db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
wallet_mod = WalletModule()

# --- 1. HANDLER MENU CHÍNH (HOME) ---

@bot.message_handler(func=lambda message: message.text in ["🏠 Trang chủ", "💼 Tài sản của bạn"] or message.text == "/start")
def show_home(message): 
    bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message): 
    bot.send_message(message.chat.id, stock_mod.get_dashboard(), reply_markup=get_stock_keyboard())

@bot.message_handler(func=lambda message: message.text in ["🪙 Crypto", "🟡 Crypto"])
def show_crypto(message):
    bot.reply_to(message, "🟡 **MODULE CRYPTO V2.0**\n\nTính năng quy đổi tự động (Rate 25k) đang được nạp dữ liệu. Sếp có thể dùng lệnh `c [MÃ] [SL] [GIÁ]` để giao dịch ngay!")

@bot.message_handler(func=lambda message: message.text == "🥇 Tài sản khác")
def show_other_assets(message):
    bot.reply_to(message, "🥇 **QUẢN LÝ TÀI SẢN NGOÀI SÀN**\n\nSếp dùng lệnh: `k [TÊN] [GIÁ TRỊ]`\n👉 Ví dụ: `k VANG 85tr` hoặc `k BDS_DALAT 1.2ty`.")

@bot.message_handler(func=lambda message: message.text == "📜 Lịch sử")
def show_history(message):
    bot.reply_to(message, "📜 Tính năng truy xuất 10 giao dịch gần nhất đang được tối ưu. Sếp chờ em chút nhé!")

@bot.message_handler(func=lambda message: message.text == "🤖 AI Chat")
def ai_chat(message):
    bot.reply_to(message, "🤖 Chào Sếp, tôi là Gemini. Sếp muốn tôi phân tích danh mục hay dự báo dòng tiền cho mã nào?")

@bot.message_handler(func=lambda message: message.text in ["📊 Báo cáo", "⚙️ Cài đặt", "📥 EXPORT/IMPORT"])
def coming_soon(message):
    bot.reply_to(message, f"🛠️ Tính năng **{message.text}** đang được hoàn thiện trong bản cập nhật tới!")

# --- 2. HANDLER MENU PHỤ (STOCK) ---

@bot.message_handler(func=lambda message: message.text == "➕ Giao dịch")
def stock_trade_ins(message):
    msg = "➕ **LỆNH GIAO DỊCH CHỨNG KHOÁN**\n\nCú pháp: `s [MÃ] [SL] [GIÁ]`\n👉 Ví dụ: `s HPG 1000 28.5` (Mua)\n👉 Ví dụ: `s HPG -1000 30` (Bán)"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def stock_refresh_ins(message):
    msg = "🔄 **CẬP NHẬT GIÁ NHANH**\n\nCú pháp: `up [MÃ] [GIÁ]`\n👉 Ví dụ: `up FPT 120`"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def show_stock_report(message):
    # Gọi hàm get_group_report vừa tạo ở StockModule
    bot.send_message(message.chat.id, stock_mod.get_group_report())

# --- 3. HANDLER LỆNH ĐẶT MỤC TIÊU ---

@bot.message_handler(func=lambda message: message.text.lower().startswith('set goal '))
def handle_set_goal(message):
    goal_str = message.text.lower().replace('set goal ', '').strip()
    db.set_goal(goal_str)
    bot.reply_to(message, f"🎯 Đã thiết lập mục tiêu: **{goal_str}**\nBấm [🏠 Trang chủ] để xem tiến độ.")

# --- 4. HANDLER TỔNG HỢP LỆNH GÕ TAY (INTEGRATED) ---

@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ']))
def handle_manual_commands(message):
    text = message.text.lower()
    
    # Nhóm 1: Ví con & Ví Mẹ
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        if "other" in text: # Ép logic cho ví OTHER
            try:
                amount_text = text.replace('chuyen other', '').strip()
                val = parse_currency(amount_text)
                db.transfer_funds('CASH', 'OTHER', val)
                bot.reply_to(message, f"✅ Đã cấp vốn {val:,.0f} đ cho Ví OTHER.")
            except: bot.reply_to(message, "❌ Lỗi: `chuyen other 500tr`")
        else:
            bot.reply_to(message, wallet_mod.handle_fund_command(message.text))

    # Nhóm 2: Tài sản khác (k)
    elif text.startswith('k '):
        try:
            parts = text.split()
            if len(parts) < 3: raise ValueError
            name, val = parts[1].upper(), parse_currency(" ".join(parts[2:]))
            db.update_other_asset(name, val)
            bot.reply_to(message, f"✅ Ghi nhận tài sản {name}: {val:,.0f} đ")
        except: bot.reply_to(message, "❌ Cú pháp: `k [TÊN] [GIÁ]`\nVD: `k VANG 85tr`")

    # Nhóm 3: Cập nhật giá (up)
    elif text.startswith('up '):
        try:
            parts = text.split()
            if len(parts) < 3: raise ValueError
            sym, price = parts[1].upper(), float(parts[2])
            # Tự hiểu 120 là 120k
            real_p = price * 1000 if price < 1000 else price
            db.update_market_price(sym, real_p)
            bot.reply_to(message, f"✅ {sym} = {real_p/1000:,.1f}k")
        except: bot.reply_to(message, "❌ Lỗi: `up FPT 120`")

    # Nhóm 4: Giao dịch (s/c)
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

# --- 5. GỢI Ý THÔNG MINH (CATCH-ALL) ---

@bot.message_handler(func=lambda message: True)
def handle_smart_hints(message):
    parts = message.text.split()
    if len(parts) >= 3 and parts[1].replace('.','',1).isdigit():
        bot.reply_to(message, "💡 Sếp quên gõ lệnh `s`, `c` hoặc `k` rồi!\nVD: `s HPG 1000 28.5` hoặc `k VANG 85tr`.")

# --- 6. KHỞI CHẠY VÀ HỒI SINH TỰ ĐỘNG ---

if __name__ == "__main__":
    print("🚀 Hệ điều hành Tài chính V2.6 đang trực chiến...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Telegram: {e}")
            time.sleep(5)

