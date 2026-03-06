# main.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from backend.telegram.bot_client import bot
from backend.telegram.keyboards import get_home_keyboard, get_stock_keyboard, get_crypto_keyboard
from backend.database.repository import DatabaseRepo
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.wallet import WalletModule
from backend.modules.crypto import CryptoModule
from backend.modules.data_manager import DataManagerModule
from backend.modules.history import HistoryModule
from backend.core.parser import parse_currency, parse_trade_command

db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
crypto_mod = CryptoModule()
wallet_mod = WalletModule()
data_mod = DataManagerModule()
hist_mod = HistoryModule()

user_context = {}

# --- BÀN PHÍM ẢO [::] CHO LỊCH SỬ ---
def get_history_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("💵 LS Nạp/Rút"), KeyboardButton("📊 LS Chứng khoán"))
    markup.row(KeyboardButton("🪙 LS Crypto"), KeyboardButton("🥇 LS Khác"))
    markup.row(KeyboardButton("🔍 Tìm kiếm LS"), KeyboardButton("🔙 Đóng Menu"))
    return markup

@bot.message_handler(func=lambda message: message.text in ["🏠 Trang chủ", "💼 Tài sản của bạn", "/start"])
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
    if ctx == 'CRYPTO':
        bot.send_message(message.chat.id, crypto_mod.get_group_report())
    else:
        bot.send_message(message.chat.id, stock_mod.get_group_report())

@bot.message_handler(func=lambda message: message.text in ["📥 EXPORT/IMPORT", "💾 Dữ liệu"])
def show_data_menu(message):
    msg, markup = data_mod.get_menu_ui()
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.document.file_name.endswith('.json'):
        bot.reply_to(message, "⏳ Đang phân tích sổ sách tài chính...")
        data_mod.handle_document(bot, message)
    else:
        bot.reply_to(message, "⚠️ Vui lòng gửi file định dạng .json")

# ==========================================
# MODULE LỊCH SỬ (NÚT BẤM & LỌC)
# ==========================================
@bot.message_handler(func=lambda message: message.text in ["📜 Lịch sử", "/history"])
def show_history(message):
    # Kích hoạt bàn phím ảo [::] Lịch Sử trước
    bot.send_message(message.chat.id, "🗄️ **ĐÃ MỞ TRUNG TÂM LƯU TRỮ**\n👇 Sử dụng menu bên dưới để lọc giao dịch:", reply_markup=get_history_keyboard(), parse_mode="Markdown")
    # Gửi bảng dữ liệu có nút lật trang
    msg, markup = hist_mod.get_history_ui(page=1, filter_type='ALL')
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

# Xử lý các nút bấm từ bàn phím [::]
@bot.message_handler(func=lambda message: message.text in ["💵 LS Nạp/Rút", "📊 LS Chứng khoán", "🪙 LS Crypto", "🥇 LS Khác"])
def handle_history_filters(message):
    filter_map = {
        "💵 LS Nạp/Rút": "CASH",
        "📊 LS Chứng khoán": "STOCK",
        "🪙 LS Crypto": "CRYPTO",
        "🥇 LS Khác": "OTHER"
    }
    f_type = filter_map[message.text]
    msg, markup = hist_mod.get_history_ui(page=1, filter_type=f_type)
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔍 Tìm kiếm LS")
def history_search_guide(message):
    bot.send_message(message.chat.id, "🔍 **HƯỚNG DẪN TÌM KIẾM NHANH**\n\nGõ lệnh:\n👉 `his [MÃ]` (VD: `his VPB`)\n👉 `his nap` (Xem lịch sử Nạp)\n👉 `his rut` (Xem lịch sử Rút)", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔙 Đóng Menu")
def close_history_menu(message):
    bot.send_message(message.chat.id, "✅ Đã đóng Menu Lịch sử.", reply_markup=get_home_keyboard())
    show_home(message)

# Xử lý lật trang Inline
@bot.callback_query_handler(func=lambda call: call.data.startswith('his_'))
def handle_history_callbacks(call):
    if call.data == 'ignore':
        bot.answer_callback_query(call.id)
        return
    parts = call.data.split('_')
    if parts[1] == 'p': 
        page, filter_type = int(parts[2]), parts[3]
        symbol = parts[4] if parts[4] != 'NONE' else None
        msg, markup = hist_mod.get_history_ui(page, filter_type, symbol)
        bot.edit_message_text(msg, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# ==========================================
# PARSER NHẬN DIỆN LỆNH GÕ TAY
# ==========================================
@bot.message_handler(func=lambda message: message.text == "➕ Giao dịch")
def trade_ins(message):
    bot.reply_to(message, "➕ **LỆNH GIAO DỊCH**\n- Stock: `s [MÃ] [SL] [GIÁ VNĐ]`\n- Crypto: `c [MÃ] [SL] [GIÁ USD]`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def refresh_ins(message):
    bot.reply_to(message, "🔄 **CẬP NHẬT GIÁ NHANH**\nCú pháp: `up [MÃ] [GIÁ]`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ', 'rate ', 'his ', 'del ']))
def handle_manual_commands(message):
    text = message.text.lower().strip()
    try:
        if text.startswith('his '):
            parts = text.split()
            if len(parts) > 1:
                term = parts[1].upper()
                if term in ['NAP', 'RUT']: msg, markup = hist_mod.get_history_ui(filter_type='CASH')
                else: msg, markup = hist_mod.get_history_ui(symbol=term)
                bot.reply_to(message, msg, reply_markup=markup, parse_mode="Markdown")
                
        elif text.startswith('del '):
            sym = text.split()[1].upper()
            _, msg_text = db.delete_holding_and_refund(sym)
            bot.reply_to(message, msg_text, parse_mode="Markdown")

        elif text.startswith('rate crypto '):
            val = float(text.replace('rate crypto ', '').strip())
            db.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('crypto_rate', ?)", (val,))
            bot.reply_to(message, f"✅ Đã cập nhật tỷ giá: 1 USD = {val:,.0f} đ")
        
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
            if w_type == 'STOCK' and price < 1000: price *= 1000
            
            rate = 1
            if w_type == 'CRYPTO':
                r_row = db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
                rate = float(r_row['value']) if r_row else 25000.0

            total_vnd = abs(qty) * price * rate
            res = db.execute_trade(w_type, sym, qty, price, total_vnd)
            
            sl_str = f"{abs(qty)}" if w_type == 'CRYPTO' else f"{abs(qty):,.0f}"
            msg = f"✅ Khớp {'MUA' if qty>0 else 'BÁN'} {sl_str} {sym}"
            if qty < 0: msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

if __name__ == "__main__":
    bot.polling(none_stop=True)
