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
from backend.core.parser import parse_currency, parse_trade_command, parse_dividend_command
from backend.modules.ai_chat import AIChatModule
from backend.modules.price_updater import PriceUpdaterModule
from backend.modules.settings import SettingsModule
from backend.modules.backup import BackupModule

# KHỞI TẠO CÁC MODULE
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
settings_mod = SettingsModule()
backup_mod = BackupModule(bot, db.db_path)

# Nạp API Keys từ Database vào AI nếu có
db_keys = settings_mod.get_setting('gemini_keys')
if db_keys:
    cfo_ai.api_keys = [k.strip() for k in db_keys.split(',') if k.strip()]

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
    if message.text == "/start":
        settings_mod.update_setting('admin_chat_id', str(message.chat.id))
    bot.send_message(message.chat.id, dash.get_main_dashboard(), reply_markup=get_home_keyboard())

@bot.message_handler(commands=['backup'])
def manual_backup(message):
    bot.send_message(message.chat.id, "⏳ Đang trích xuất nén toàn bộ sổ sách hệ thống...")
    backup_mod.send_backup_to_user(message.chat.id, manual=True)

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
# MODULE CÀI ĐẶT (SETTINGS)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "⚙️ Cài đặt" or message.text == "/settings")
def show_settings(message):
    user_context[message.chat.id] = 'SETTINGS'
    text, markup = settings_mod.get_main_menu()
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_') or call.data.startswith('ai_') or call.data.startswith('confirm_'))
def handle_settings_callbacks(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    action = call.data

    if action == "set_main":
        user_context[chat_id] = 'SETTINGS'
        text, markup = settings_mod.get_main_menu()
        bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=markup, parse_mode="Markdown")
        
    elif action == "set_close":
        bot.delete_message(chat_id, msg_id)
        
    elif action == "set_rate":
        user_context[chat_id] = 'WAIT_RATE'
        bot.edit_message_text("💱 Sếp hãy gõ tỷ giá USD/VND mới (VD: `25500`):", chat_id=chat_id, message_id=msg_id, parse_mode="Markdown")
        
    elif action == "set_target":
        user_context[chat_id] = 'WAIT_TARGET'
        bot.edit_message_text("🎯 Sếp hãy gõ Mục tiêu NAV (VD: `500tr`, `hòa vốn`, `lãi 10%`):", chat_id=chat_id, message_id=msg_id, parse_mode="Markdown")

    elif action == "set_sync":
        user_context[chat_id] = 'WAIT_SYNC'
        bot.edit_message_text("⏱️ Sếp hãy gõ số phút cập nhật giá (VD: `15`, `30`, `60`. Gõ `0` để tắt):", chat_id=chat_id, message_id=msg_id, parse_mode="Markdown")

    elif action == "set_guide":
        text, markup = settings_mod.get_guide_text()
        bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=markup, parse_mode="Markdown")

    elif action == "set_ai_keys":
        text, markup = settings_mod.get_ai_keys_menu()
        bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=markup, parse_mode="Markdown")
        
    elif action == "ai_add_key":
        user_context[chat_id] = 'WAIT_API_KEY'
        bot.edit_message_text("🤖 Sếp hãy dán mã API Key của Gemini vào đây:", chat_id=chat_id, message_id=msg_id, parse_mode="Markdown")
        
    elif action == "ai_clear_keys":
        settings_mod.update_setting('gemini_keys', '')
        import os
        env_keys = os.environ.get("GEMINI_API_KEYS", "")
        cfo_ai.api_keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        bot.answer_callback_query(call.id, "✅ Đã xóa toàn bộ Key! Trở về dùng cấu hình .env", show_alert=True)
        text, markup = settings_mod.get_ai_keys_menu()
        bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=markup, parse_mode="Markdown")

    elif action == "set_factory_reset":
        text, markup = settings_mod.get_factory_reset_warning()
        bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=markup, parse_mode="Markdown")
        
    elif action == "confirm_reset_yes":
        bot.answer_callback_query(call.id, "⏳ Đang dọn dẹp sổ sách...")
        try:
            db.execute_query("DELETE FROM transactions")
            db.execute_query("DELETE FROM holdings")
            db.execute_query("UPDATE wallets SET balance = 0, total_in = 0, total_out = 0")
            
            bot.edit_message_text("✅ **ĐÃ KHÔI PHỤC CÀI ĐẶT GỐC THÀNH CÔNG.**\nToàn bộ Danh mục, Lịch sử và Vốn Nạp/Rút đã về 0!", chat_id=chat_id, message_id=msg_id, parse_mode="Markdown")
            show_home(call.message)
        except Exception as e:
            bot.edit_message_text(f"❌ Lỗi Database khi xóa: {str(e)}", chat_id=chat_id, message_id=msg_id)

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

@bot.callback_query_handler(func=lambda call: call.data == 'export_excel_report')
def handle_export_excel(call):
    bot.answer_callback_query(call.id, "Đang tạo file Excel...")
    try:
        excel_bytes = report_mod.generate_excel_bytes()
        bot.send_document(call.message.chat.id, document=("Bao_Cao.xlsx", excel_bytes))
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Lỗi xuất file: {str(e)}")

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

@bot.message_handler(func=lambda message: message.text in ["🤖 AI Chat", "🤖 Trợ lý AI"])
def handle_cfo_ai_button(message):
    user_context[message.chat.id] = 'AI_CHAT' 
    msg = bot.send_message(message.chat.id, "⏳ CFO đang lấy sổ sách ra rà soát, sếp đợi một lát...")
    try:
        auto_prompt = "Hãy quét toàn cảnh danh mục của tôi hiện tại. Đưa ra một bản báo cáo tàn nhẫn nhất về các khoản lỗ, tỷ trọng mất cân bằng và yêu cầu tôi hành động ngay lập tức."
        response = cfo_ai.chat_with_cfo(message.chat.id, auto_prompt)
        response += "\n\n💡 (Sếp đang ở trong phòng CFO. Sếp có thể chat tự nhiên ngay tại đây. Bấm nút Menu khác để thoát)."
        bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=response)
    except Exception as e:
        bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=f"❌ CFO không thể truy cập sổ sách: {str(e)}")

@bot.message_handler(func=lambda message: message.text in ["📜 Lịch sử", "/history"])
def show_history(message):
    user_context[message.chat.id] = 'HISTORY'
    bot.send_message(message.chat.id, "🗄️ **TRUNG TÂM LƯU TRỮ**\n👇 Sử dụng menu bên dưới để lọc giao dịch:", reply_markup=get_history_keyboard(), parse_mode="Markdown")
    msg, markup = hist_mod.get_history_ui(page=1, filter_type='ALL')
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text in ["💵 LS Nạp/Rút", "📊 LS Chứng khoán", "🪙 LS Crypto", "🥇 LS Khác"])
def handle_history_filters(message):
    filter_map = {"💵 LS Nạp/Rút": "CASH", "📊 LS Chứng khoán": "STOCK", "🪙 LS Crypto": "CRYPTO", "🥇 LS Khác": "OTHER"}
    f_type = filter_map[message.text]
    msg, markup = hist_mod.get_history_ui(page=1, filter_type=f_type)
    bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔍 Tìm kiếm LS")
def history_search_guide(message):
    bot.send_message(message.chat.id, "🔍 **HƯỚNG DẪN TÌM KIẾM NHANH**\n\nGõ lệnh:\n👉 `his [MÃ]` (VD: `his VPB`)\n👉 `his nap` (Xem lịch sử Nạp)", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔙 Đóng Menu")
def close_history_menu(message):
    bot.send_message(message.chat.id, "✅ Đã đóng Menu Lịch sử.", reply_markup=get_home_keyboard())
    show_home(message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('his_') or call.data == 'ignore')
def handle_history_callbacks(call):
    if call.data == 'ignore':
        bot.answer_callback_query(call.id, "⚠️ Bạn đang ở ranh giới trang!", show_alert=False)
        return
    parts = call.data.split('_')
    if parts[1] == 'p': 
        page, filter_type = int(parts[2]), parts[3]
        symbol = parts[4] if parts[4] != 'NONE' else None
        msg, markup = hist_mod.get_history_ui(page, filter_type, symbol)
        bot.edit_message_text(msg, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "➕ Giao dịch")
def trade_ins(message):
    bot.reply_to(message, "➕ **LỆNH GIAO DỊCH**\n- Stock: `s [MÃ] [SL] [GIÁ VNĐ]`\n- Crypto: `c [MÃ] [SL] [GIÁ USD]`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔄 Cập nhật giá")
def handle_auto_update_price(message):
    msg = bot.send_message(message.chat.id, "⏳ Đang phi lên sàn cào giá Real-time và tỷ giá USD/VND...")
    try:
        # Cập nhật tỷ giá USD/VND
        new_rate = auto_updater.fetch_usd_vnd_rate()
        rate_text = f"💱 **Tỷ giá USD/VND:** {new_rate:,.0f} đ\n" if new_rate else "💱 **Tỷ giá USD/VND:** Đang dùng giá cũ\n"

        stats = report_mod._process_data()
        holdings = stats['raw_data']['holdings']
        
        if not holdings or len(holdings) == 0:
            bot.edit_message_text(f"{rate_text}\n⚠️ Danh mục trống hoặc chưa có mã nào được ghi nhận.", chat_id=message.chat.id, message_id=msg.message_id, parse_mode="Markdown")
            return

        from concurrent.futures import ThreadPoolExecutor
        def _fetch_and_update(item):
            sym = item['symbol']
            w_type = item['wallet_id']
            price = auto_updater._get_realtime_price(sym, w_type)
            if price:
                db.update_market_price(sym, price)
                
                # SỬA LỖI ĐỊNH DẠNG USD VÀ VNĐ CHO CHUẨN MỰC
                if w_type == 'CRYPTO':
                    if sym in ['USDT', 'USDC', 'BUSD', 'FDUSD']:
                        current_rate = float(settings_mod.get_setting('crypto_rate') or 25400)
                        return f"✅ `{sym}`: 1.00 USD (~{current_rate:,.0f} đ)"
                    return f"✅ `{sym}`: ${price:,.2f}"
                else:
                    return f"✅ `{sym}`: {price:,.0f} đ"
            return f"⚠️ `{sym}`: Không lấy được giá"

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(_fetch_and_update, holdings))
        
        res_text = f"🔄 **KẾT QUẢ ĐỒNG BỘ TỪ SÀN:**\n{rate_text}\n" + "\n".join(results) + "\n\n💡 _Gõ: `up [MÃ] [GIÁ]` để cập nhật tay_"
        bot.edit_message_text(res_text, chat_id=message.chat.id, message_id=msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ Lỗi đồng bộ: {str(e)}", chat_id=message.chat.id, message_id=msg.message_id)

# ==========================================
# BỘ XỬ LÝ LỆNH GÕ TAY
# ==========================================
@bot.message_handler(func=lambda message: any(message.text.lower().startswith(x) for x in ['nap ', 'rut ', 'chuyen ', 'thu ', 's ', 'c ', 'k ', 'up ', 'rate ', 'his ', 'del ', 'ct ']))
def handle_manual_commands(message):
    text = message.text.lower().strip()
    try:
        if text.startswith('ct '):
            parsed = parse_dividend_command(text)
            if not parsed:
                bot.reply_to(message, "⚠️ Lệnh không hợp lệ. Hãy dùng: `ct tien [MÃ] [TIỀN]` hoặc `ct cp [MÃ] [SỐ LƯỢNG]`\nVí dụ: `ct tien VPB 500k`", parse_mode="Markdown")
                return
                
            action_type, sym, val = parsed
            if action_type == 'tien':
                success, msg_text = db.add_cash_dividend(sym, val)
            else:
                success, msg_text = db.add_stock_dividend(sym, val)
                
            bot.reply_to(message, msg_text, parse_mode="Markdown")

        elif text.startswith('his '):
            parts = text.split()
            if len(parts) > 1:
                term = parts[1].upper()
                if term in ['NAP', 'RUT', 'CASH']: msg, markup = hist_mod.get_history_ui(filter_type='CASH')
                elif term in ['STOCK', 'CK', 'CHUNGKHOAN']: msg, markup = hist_mod.get_history_ui(filter_type='STOCK')
                elif term in ['CRYPTO', 'COIN']: msg, markup = hist_mod.get_history_ui(filter_type='CRYPTO')
                elif term in ['KHAC', 'OTHER']: msg, markup = hist_mod.get_history_ui(filter_type='OTHER')
                else: msg, markup = hist_mod.get_history_ui(symbol=term)
                bot.reply_to(message, msg, reply_markup=markup, parse_mode="Markdown")
                
        elif text.startswith('del '):
            param = text.split()[1].upper()
            if param.startswith('#'):
                try:
                    tx_id = int(param.replace('#', ''))
                    success, msg_text = db.undo_transaction(tx_id)
                except ValueError:
                    msg_text = "⚠️ ID giao dịch không hợp lệ. Hãy gõ ví dụ: `del #154`"
            else:
                _, msg_text = db.delete_holding_and_refund(param)
            bot.reply_to(message, msg_text, parse_mode="Markdown")

        elif text.startswith('rate crypto '):
            val = float(text.replace('rate crypto ', '').strip())
            settings_mod.update_setting('crypto_rate', val)
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
                rate = float(settings_mod.get_setting('crypto_rate') or 25400.0)

            total_vnd = abs(qty) * price * rate
            res = db.execute_trade(w_type, sym, qty, price, total_vnd)
            
            sl_str = f"{abs(qty)}" if w_type == 'CRYPTO' else f"{abs(qty):,.0f}"
            msg = f"✅ Khớp {'MUA' if qty>0 else 'BÁN'} {sl_str} {sym}"
            if qty < 0: msg += f"\n💰 Lãi chốt: {res:,.0f} đ"
            bot.reply_to(message, msg)

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

# ==========================================
# CATCH-ALL: BẮT TRẠNG THÁI GÕ TEXT CHO SETTINGS HOẶC AI CHAT
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_fallback_and_ai_chat(message):
    if not message.text: return
    text = message.text
    chat_id = message.chat.id
    ctx = user_context.get(chat_id)

    if ctx == 'WAIT_RATE':
        try:
            val = float(text.replace(',', ''))
            settings_mod.update_setting('crypto_rate', val)
            bot.reply_to(message, f"✅ Tỷ giá mới đã được lưu: {val:,.0f} đ")
            show_settings(message)
        except:
            bot.reply_to(message, "❌ Sai định dạng số. Xin nhập lại.")
        return

    elif ctx == 'WAIT_TARGET':
        settings_mod.update_setting('goal', text.strip())
        bot.reply_to(message, f"✅ Mục tiêu NAV đã lưu: {text.strip()}")
        show_settings(message)
        return

    elif ctx == 'WAIT_SYNC':
        try:
            val = int(text)
            settings_mod.update_setting('auto_sync_interval', val)
            auto_updater.interval_seconds = val * 60 
            status = f"{val} phút/lần" if val > 0 else "ĐÃ TẮT"
            bot.reply_to(message, f"✅ Thời gian Auto-Sync đã cập nhật thành: {status}")
            show_settings(message)
        except:
            bot.reply_to(message, "❌ Sai định dạng số phút. Xin nhập lại.")
        return

    elif ctx == 'WAIT_API_KEY':
        new_key = text.strip()
        current_keys_str = settings_mod.get_setting('gemini_keys')
        
        if current_keys_str:
            new_keys_str = current_keys_str + "," + new_key
        else:
            new_keys_str = new_key
            
        settings_mod.update_setting('gemini_keys', new_keys_str)
        cfo_ai.api_keys = [k.strip() for k in new_keys_str.split(',') if k.strip()]
        
        bot.reply_to(message, "✅ Đã nạp thành công API Key mới vào Đầu não AI CFO!")
        show_settings(message)
        return

    user_query = None
    if text.startswith('?'):
        user_query = text[1:].strip()
    elif text.lower().startswith('ai '):
        user_query = text[3:].strip()
    elif text.lower().startswith('cfo '):
        user_query = text[4:].strip()
    elif ctx == 'AI_CHAT':
        user_query = text.strip()
        
    if user_query:
        msg = bot.send_message(chat_id, "⏳ Hệ thống đang suy nghĩ...")
        try:
            response = cfo_ai.chat_with_cfo(chat_id, user_query)
            bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=response)
        except Exception as e:
            bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=f"❌ Lỗi kết nối API: {str(e)}")
    else:
        bot.reply_to(message, "⚠️ Lệnh không hợp lệ. Vui lòng gõ `/settings` để mở Cài đặt, hoặc gõ `? [câu hỏi]` để AI hỗ trợ.")

if __name__ == "__main__":
    from flask import Flask
    import threading

    # 1. Khởi tạo Dummy Web Server cho Render
    app = Flask(__name__)
    @app.route('/')
    def home():
        return "Hệ điều hành V3.4 - CFO AI đang hoạt động bình thường!"

    def run_web():
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port)

    # Khởi chạy luồng Web ngầm
    #threading.Thread(target=run_web, daemon=True).start()

    # 2. Khởi chạy các tiến trình ngầm (Sync Giá & Auto-Backup)
    interval = int(settings_mod.get_setting('auto_sync_interval') or 30)
    if interval > 0:
        auto_updater.interval_seconds = interval * 60
        auto_updater.start_background_sync()
        
    backup_mod.start_auto_backup()
    
    print("🤖 Hệ thống V3.4 Plug & Play đang chạy trên Render...")
    
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
