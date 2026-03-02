import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.telegram.bot_client import bot
from backend.telegram.keyboards import get_home_keyboard, get_stock_keyboard
from backend.database.repository import DatabaseRepo
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.wallet import WalletModule

# Khởi tạo các thành phần hệ thống
db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
wallet_mod = WalletModule()

# --- 1. HANDLER TRANG CHỦ & START ---
@bot.message_handler(func=lambda message: message.text in ["💼 Tài sản của bạn", "🏠 Trang chủ"] or message.text == "/start")
def show_home(message):
    bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

# --- 2. HANDLER STOCK DASHBOARD ---
@bot.message_handler(func=lambda message: message.text == "📊 Chứng Khoán")
def show_stock(message):
    bot.send_message(message.chat.id, stock_mod.get_dashboard(), reply_markup=get_stock_keyboard())

# --- 3. HANDLER BÁO CÁO NHÓM ---
@bot.message_handler(func=lambda message: message.text == "📈 Báo cáo nhóm")
def show_report(message):
    bot.send_message(message.chat.id, stock_mod.get_group_report())

# --- 4. HANDLER LỆNH GÕ TAY (ƯU TIÊN CAO) ---
# Đưa các lệnh chuẩn lên trước để xử lý ngay
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'up ']))
def handle_commands(message):
    text = message.text.lower()
    
    # Nhóm lệnh Ví (Nạp/Rút/Chuyển/Thu)
    if text.startswith(('nap ', 'rut ', 'chuyen ', 'thu ')):
        bot.reply_to(message, wallet_mod.handle_fund_command(message.text))
    
    # Nhóm lệnh Cập nhật giá nhanh (up)
    elif text.startswith('up '):
        try:
            parts = message.text.split()
            if len(parts) < 3:
                bot.reply_to(message, "❌ Cú pháp: `up [MÃ] [GIÁ]`\nVD: `up HPG 35`")
                return
            symbol, price = parts[1].upper(), float(parts[2])
            from config import RATE_STOCK
            db.update_market_price(symbol, price * RATE_STOCK)
            bot.reply_to(message, f"✅ Cập nhật {symbol} = {price:,.1f}k\nBấm [📊 Chứng Khoán] để xem NAV mới.")
        except Exception as e:
            bot.reply_to(message, f"❌ Lỗi cập nhật: {str(e)}")
            
    # Nhóm lệnh Giao dịch (s/c)
    else:
        from backend.core.parser import parse_trade_command
        from config import RATE_STOCK, RATE_CRYPTO
        parsed = parse_trade_command(message.text)
        if not parsed:
            bot.reply_to(message, "❌ Sai cú pháp giao dịch.")
            return
        
        w_type, sym, qty, price = parsed
        rate = RATE_STOCK if w_type == 'STOCK' else RATE_CRYPTO
        try:
            # Thực thi giao dịch qua Repo
            res = db.execute_trade(w_type, sym, qty, price * rate, abs(qty) * price * rate)
            msg = f"✅ Khớp {'MUA' if qty > 0 else 'BÁN'} {abs(qty):,.0f} {sym}"
            if qty < 0:
                msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)
        except Exception as e:
            bot.reply_to(message, f"❌ {str(e)}")

# --- 5. HANDLER GỢI Ý
