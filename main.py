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
from backend.modules.report import ReportModule
from backend.core.parser import parse_currency, parse_trade_command
from backend.modules.ai_chat import AIChatModule
from backend.modules.price_updater import PriceUpdaterModule

db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
crypto_mod = CryptoModule()
wallet_mod = WalletModule()
data_mod = DataManagerModule()
hist_mod = HistoryModule()
report_mod = ReportModule()
cfo_ai = AIChatModule()
auto_updater = PriceUpdaterModule(interval_minutes=30)

user_context = {}

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

# ==========================================
# FIX LỖI: NÚT CẬP NHẬT GIÁ (NHẬN DIỆN DANH MỤC)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def handle_auto_update_price(message):
    msg = bot.send_message(message.chat.id, "⏳ Đang phi lên sàn cào giá Real-time cho Sếp...")
    try:
        # Cải tiến SQL: Lấy tất cả các mã đang có bản ghi trong holdings (không phân biệt số lượng)
        rows = db.execute_query("SELECT DISTINCT symbol, wallet_id FROM holdings", fetch_one=False)
        
        if not rows or len(rows) == 0:
            bot.edit_message_text("⚠️ Hệ thống không tìm thấy mã nào trong sổ cái để cập nhật.", chat_id=message.chat.id, message_id=msg.message_id)
            return

        from concurrent.futures import ThreadPoolExecutor
        
        def _fetch_and_update(item):
            sym = item['symbol']
            w_type = item['wallet_id']
            price = auto_updater._get_realtime_price(sym, w_type)
            if price:
                db.update_market_price(sym, price)
                return f"✅ `{sym}`: {price:,.0f} đ"
            return f"⚠️ `{sym}`: Không lấy được giá"

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(_fetch_and_update, rows))
        
        res_text = "🔄 **KẾT QUẢ ĐỒNG BỘ GIÁ TỪ SÀN:**\n\n" + "\n".join(results)
        bot.edit_message_text(res_text, chat_id=message.chat.id, message_id=msg.message_id, parse_mode="Markdown")
        
    except Exception as e:
        bot.edit_message_text(f"❌ Lỗi đồng bộ: {str(e)}", chat_id=message.chat.id, message_id=msg.message_id)

# ==========================================
# CÁC MODULE KHÁC GIỮ NGUYÊN
# ==========================================
@bot.message_handler(func=lambda message: message.text == "📊 Báo cáo")
def show_overall_report(message):
    user_context[message.chat.id] = 'REPORT'
    bot.send_message(message.chat.id, "⏳ Đang tổng hợp số liệu danh mục...", parse_mode="Markdown")
    msg, markup = report_mod.get_telegram_report()
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'view_nav_chart')
def handle_view_chart(call):
    bot.answer_callback_query(call.id, "⏳ Đang vẽ biểu đồ...")
    try:
        chart_bytes = report_mod.generate_chart_bytes()
        bot.send_photo(call.message.chat.id, photo=chart_bytes, caption="📈 BIỂU ĐỒ TÀI SẢN", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Lỗi chart: {str(e)}")

@bot.message_handler(func=lambda message: message.text in ["📥 EXPORT/IMPORT", "💾 Dữ liệu"])
def show_data_menu(message):
    user_context[message.chat.id] = 'DATA'
    msg, markup = data_mod.get_menu_ui()
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.document.file_name.endswith('.json'):
        data_mod.handle_document(bot, message)

@bot.message_handler(func=lambda message: message.text in ["🤖 AI Chat", "🤖 Trợ lý AI"])
def handle_cfo_ai_button(message):
    user_context[message.chat.id] = 'AI_CHAT' 
    msg = bot.send_message(message.chat.id, "⏳ CFO đang rà soát sổ sách...")
    try:
        response = cfo_ai.chat_with_cfo("Hãy quét toàn cảnh danh mục của tôi hiện tại và đưa ra cảnh báo.")
        bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=response)
    except Exception as e:
        bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=f"❌ Lỗi AI: {str(e)}")

@bot.message_handler(func=lambda message: message.text in ["📜 Lịch sử", "/history"])
def show_history(message):
    user_context[message.chat.id] = 'HISTORY'
    bot.send_message(message.chat.id, "🗄️ TRUNG TÂM LƯU TRỮ", reply_markup=get_history_keyboard(), parse_mode="Markdown")
    msg, markup = hist_mod.get_history_ui(page=1, filter_type='ALL')
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ', 'rate ', 'his ', 'del ']))
def handle_manual_commands(message):
    text = message.text.lower().strip()
    try:
        if text.startswith('up '):
            parts = text.split()
            sym, p = parts[1].upper(), float(parts[2])
            db.update_market_price(sym, p * 1000 if p < 1000 else p)
            bot.reply_to(message, f"✅ Đã cập nhật tay {sym}")
        elif text.startswith(('nap ', 'rut ', 'chuyen ')):
            bot.reply_to(message, wallet_mod.handle_fund_command(message.text))
        elif text.startswith(('s ', 'c ')):
            parsed = parse_trade_command(text)
            if parsed:
                w_type, sym, qty, price = parsed
                rate = 1.0
                if w_type == 'CRYPTO':
                    r_row = db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
                    rate = float(r_row['value']) if r_row else 25000.0
                db.execute_trade(w_type, sym, qty, price, abs(qty)*price*rate)
                bot.reply_to(message, f"✅ Đã ghi nhận giao dịch {sym}")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi lệnh: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_fallback_and_ai_chat(message):
    if not message.text: return
    text = message.text
    if text.startswith('?') or text.lower().startswith('ai ') or user_context.get(message.chat.id) == 'AI_CHAT':
        query = text.replace('?', '').replace('ai ', '').strip()
        msg = bot.send_message(message.chat.id, "⏳ Đang suy nghĩ...")
        bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=cfo_ai.chat_with_cfo(query))

if __name__ == "__main__":
    auto_updater.start_background_sync()
    print("🤖 Hệ thống V3.4 đang chạy...")
    bot.polling(none_stop=True)
