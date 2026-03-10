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

# IMPORT MODULE AI CFO MỚI
from backend.modules.ai_chat import AIChatModule

db = DatabaseRepo()
dash = DashboardModule()
stock_mod = StockModule()
crypto_mod = CryptoModule()
wallet_mod = WalletModule()
data_mod = DataManagerModule()
hist_mod = HistoryModule()
report_mod = ReportModule()

# KHỞI TẠO NÃO BỘ AI
cfo_ai = AIChatModule()

# Biến toàn cục lưu trạng thái người dùng (Đang ở Menu nào)
user_context = {}

def get_history_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("💵 LS Nạp/Rút"), KeyboardButton("📊 LS Chứng khoán"))
    markup.row(KeyboardButton("🪙 LS Crypto"), KeyboardButton("🥇 LS Khác"))
    markup.row(KeyboardButton("🔍 Tìm kiếm LS"), KeyboardButton("🔙 Đóng Menu"))
    return markup

@bot.message_handler(func=lambda message: message.text in ["🏠 Trang chủ", "💼 Tài sản của bạn", "/start"])
def show_home(message):
    user_context[message.chat.id] = 'HOME' # Thoát khỏi phòng CFO
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
def show_group_report(message):
    ctx = user_context.get(message.chat.id, 'STOCK')
    if ctx == 'CRYPTO':
        bot.send_message(message.chat.id, crypto_mod.get_group_report())
    else:
        bot.send_message(message.chat.id, stock_mod.get_group_report())

# ==========================================
# MODULE REPORT & XUẤT EXCEL / CHART
# ==========================================
@bot.message_handler(func=lambda message: message.text == "📊 Báo cáo")
def show_overall_report(message):
    user_context[message.chat.id] = 'REPORT'
    bot.send_message(message.chat.id, "⏳ Đang tổng hợp số liệu danh mục...", parse_mode="Markdown")
    msg, markup = report_mod.get_telegram_report()
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'view_nav_chart')
def handle_view_chart(call):
    bot.answer_callback_query(call.id, "⏳ Đang vẽ biểu đồ. Sếp đợi vài giây nhé...")
    try:
        chart_bytes = report_mod.generate_chart_bytes()
        bot.send_photo(
            call.message.chat.id, 
            photo=chart_bytes, 
            caption="📈 **BIỂU ĐỒ VỐN NẠP RÒNG & TÀI SẢN THỰC TẾ**\nKhoảng cách giữa điểm màu đỏ và đường màu xanh chính là Lãi/Lỗ hiện tại của Sếp!",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Lỗi khi vẽ biểu đồ: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == 'export_excel_report')
def handle_export_excel(call):
    bot.answer_callback_query(call.id, "Đang tạo file Excel. Vui lòng đợi...")
    try:
        excel_bytes = report_mod.generate_excel_bytes()
        bot.send_document(
            call.message.chat.id, 
            document=("Bao_Cao_V3.4.xlsx", excel_bytes), 
            caption="✅ File báo cáo Excel của Sếp đây ạ!"
        )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Lỗi khi xuất file: {str(e)}")

@bot.message_handler(func=lambda message: message.text in ["📥 EXPORT/IMPORT", "💾 Dữ liệu"])
def show_data_menu(message):
    user_context[message.chat.id] = 'DATA'
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
# MODULE AI CFO (VÀO PHÒNG CFO)
# ==========================================
@bot.message_handler(func=lambda message: message.text in ["🤖 AI Chat", "🤖 Trợ lý AI"])
def handle_cfo_ai_button(message):
    # Đánh dấu sếp đã vào phòng CFO (Từ giờ chat tự nhiên không cần tiền tố)
    user_context[message.chat.id] = 'AI_CHAT' 
    
    msg = bot.send_message(message.chat.id, "⏳ CFO đang lấy sổ sách ra rà soát, sếp đợi một lát...")
    try:
        auto_prompt = "Hãy quét toàn cảnh danh mục của tôi hiện tại. Đưa ra một bản báo cáo tàn nhẫn nhất về các khoản lỗ, tỷ trọng mất cân bằng và yêu cầu tôi hành động ngay lập tức."
        response = cfo_ai.chat_with_cfo(auto_prompt)
        
        # Thêm hướng dẫn chat tự nhiên
        response += "\n\n💡 (Sếp đang ở trong phòng CFO. Sếp có thể chat tự nhiên ngay tại đây. Bấm nút Menu khác để thoát)."
        
        # ĐÃ BỎ parse_mode='Markdown' ĐỂ CHỐNG LỖI TELEGRAM
        bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=response)
    except Exception as e:
        bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=f"❌ CFO không thể truy cập sổ sách: {str(e)}")

# ==========================================
# MODULE LỊCH SỬ
# ==========================================
@bot.message_handler(func=lambda message: message.text in ["📜 Lịch sử", "/history"])
def show_history(message):
    user_context[message.chat.id] = 'HISTORY'
    bot.send_message(message.chat.id, "🗄️ **ĐÃ MỞ TRUNG TÂM LƯU TRỮ**\n👇 Sử dụng menu bên dưới để lọc giao dịch:", reply_markup=get_history_keyboard(), parse_mode="Markdown")
    msg, markup = hist_mod.get_history_ui(page=1, filter_type='ALL')
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

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

@bot.callback_query_handler(func=lambda call: call.data.startswith('his_') or call.data == 'ignore')
def handle_history_callbacks(call):
    if call.data == 'ignore':
        bot.answer_callback_query(call.id, "⚠️ Bạn đang ở ranh giới trang (đầu/cuối) rồi!", show_alert=False)
        return
    parts = call.data.split('_')
    if parts[1] == 'p': 
        page, filter_type = int(parts[2]), parts[3]
        symbol = parts[4] if parts[4] != 'NONE' else None
        msg, markup = hist_mod.get_history_ui(page, filter_type, symbol)
        bot.edit_message_text(msg, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# ==========================================
# PARSER NHẬN DIỆN LỆNH GÕ TAY (MUA/BÁN/NẠP/RÚT)
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
                if term in ['NAP', 'RUT', 'CASH']: 
                    msg, markup = hist_mod.get_history_ui(filter_type='CASH')
                elif term in ['STOCK', 'CK', 'CHUNGKHOAN']: 
                    msg, markup = hist_mod.get_history_ui(filter_type='STOCK')
                elif term in ['CRYPTO', 'COIN']: 
                    msg, markup = hist_mod.get_history_ui(filter_type='CRYPTO')
                elif term in ['KHAC', 'OTHER']: 
                    msg, markup = hist_mod.get_history_ui(filter_type='OTHER')
                else: 
                    msg, markup = hist_mod.get_history_ui(symbol=term)
                
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

# ==========================================
# CATCH-ALL: NHẬN DIỆN CHAT TỰ NHIÊN VỚI CFO (PHẢI ĐỂ CUỐI CÙNG)
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_fallback_and_ai_chat(message):
    if not message.text: return
    text = message.text
    user_query = None
    
    # 1. Nhận diện nếu user có dùng tiền tố (gọi nhanh CFO từ bất kỳ đâu)
    if text.startswith('?'):
        user_query = text[1:].strip()
    elif text.lower().startswith('ai '):
        user_query = text[3:].strip()
    elif text.lower().startswith('cfo '):
        user_query = text[4:].strip()
    # 2. Nhận diện nếu user đang ở trong phòng CFO (không cần tiền tố)
    elif user_context.get(message.chat.id) == 'AI_CHAT':
        user_query = text.strip()
        
    # Nếu là câu hỏi dành cho AI
    if user_query:
        msg = bot.send_message(message.chat.id, "⏳ CFO đang suy nghĩ...")
        try:
            response = cfo_ai.chat_with_cfo(user_query)
            # ĐÃ BỎ parse_mode='Markdown' ĐỂ CHỐNG LỖI TELEGRAM
            bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=response)
        except Exception as e:
            bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=f"❌ Lỗi kết nối API CFO: {str(e)}")
    else:
        # Nếu gõ linh tinh mà không ở trong phòng CFO
        bot.reply_to(message, "⚠️ Lệnh không hợp lệ. Vui lòng sử dụng Menu hoặc gõ `? [câu hỏi]` để nhờ CFO tư vấn.")

if __name__ == "__main__":
    bot.polling(none_stop=True)
