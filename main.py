# main.py
import os
import re
import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, constants, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from backend.core.parser import CommandParser
from backend.database.repository import Repository
from backend.database.db_manager import db
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.crypto import CryptoModule 
from backend.modules.history import HistoryModule
from backend.modules.report import ReportModule
# --- Hợp nhất: Thêm module xuất Excel ---
from backend.modules.export import generate_excel_report

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))
repo = Repository()

# --- HỆ THỐNG MENU ---
def get_ceo_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💼 Tài sản của bạn")],
        [KeyboardButton("📊 Chứng Khoán"), KeyboardButton("🪙 Crypto")],
        [KeyboardButton("🥇 Tài sản khác"), KeyboardButton("📜 Lịch sử")],
        [KeyboardButton("📊 Báo cáo"), KeyboardButton("🤖 AI Chat")],
        [KeyboardButton("⚙️ Cài đặt"), KeyboardButton("📥 EXPORT/IMPORT")],
        [KeyboardButton("📸 SNAPSHOT"), KeyboardButton("🔄 Làm mới")]
    ], resize_keyboard=True)

def get_stock_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Giao dịch"), KeyboardButton("🔄 Cập nhật giá")],
        [KeyboardButton("📈 Báo cáo nhóm"), KeyboardButton("❌ Xóa mã")],
        [KeyboardButton("🏠 Trang chủ")]
    ], resize_keyboard=True)

def get_crypto_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Giao dịch Crypto"), KeyboardButton("🔄 Cập nhật giá Crypto")],
        [KeyboardButton("📈 Báo cáo Crypto"), KeyboardButton("❌ Xóa mã Crypto")],
        [KeyboardButton("🏠 Trang chủ")]
    ], resize_keyboard=True)

def get_report_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Stock"), KeyboardButton("🪙 Crypto"), KeyboardButton("🥇 Tài sản khác")],
        [KeyboardButton("🔍 TÌM KIẾM"), KeyboardButton("📥 Xuất Excel"), KeyboardButton("🏠 Trang chủ")]
    ], resize_keyboard=True)

def get_category_report_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📅 Chọn thời gian"), KeyboardButton("🔍 TÌM KIẾM")],
        [KeyboardButton("⬅️ Menu Báo Cáo"), KeyboardButton("🏠 Trang chủ")]
    ], resize_keyboard=True)

def get_detail_report_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📅 Chọn thời gian")],
        [KeyboardButton("⬅️ Menu Báo Cáo"), KeyboardButton("🏠 Trang chủ")]
    ], resize_keyboard=True)

def get_time_filter_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📅 7 Ngày qua"), KeyboardButton("📅 30 Ngày qua")],
        [KeyboardButton("📅 3 Tháng"), KeyboardButton("📅 1 Năm")],
        [KeyboardButton("🗓 Tùy chọn"), KeyboardButton("♾ Toàn thời gian")],
        [KeyboardButton("⬅️ Menu Báo Cáo")]
    ], resize_keyboard=True)

# --- XỬ LÝ CALLBACK ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    hist = HistoryModule(user_id)

    if data.startswith("hist_page_") or data.startswith("hist_filter_"):
        parts = data.split("_")
        page = int(parts[2]) if "page" in data else 0
        a_type = parts[-1] if parts[-1] != 'ALL' else None
        text, kb = hist.run(page=page, asset_type=a_type)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=constants.ParseMode.HTML)

    elif data == "hist_search_prompt":
        await query.message.reply_html("🔍 <b>TÌM KIẾM LỊCH SỬ</b>\nCEO hãy gõ mã tài sản cần tìm...")

    elif data == "go_home":
        if 'edit_trx' in context.user_data: del context.user_data['edit_trx']
        context.user_data['current_menu'] = 'HOME'
        await query.message.reply_html(DashboardModule(user_id).run(), reply_markup=get_ceo_menu())

    elif data.startswith("view_"):
        if 'edit_trx' in context.user_data: del context.user_data['edit_trx']
        trx_id = data.split("_")[-1]
        content, kb = hist.get_detail_view(trx_id)
        await query.edit_message_text(content, reply_markup=kb, parse_mode=constants.ParseMode.HTML)

    elif data.startswith("edit_"):
        parts = data.split("_")
        field, trx_id = parts[1], parts[-1]
        context.user_data['edit_trx'] = {'id': trx_id, 'field': field}
        prompts = {'qty': "🔢 Nhập SỐ LƯỢNG:", 'price': "💲 Nhập GIÁ:", 'date': "📅 Nhập NGÀY (YYYY-MM-DD):"}
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data=f"view_{trx_id}")]])
        await query.message.reply_html(f"✏️ <b>Đang sửa #{trx_id}</b>\n{prompts[field]}", reply_markup=kb)

    elif data.startswith("confirm_delete_"):
        trx_id = data.split("_")[-1]
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ CÓ, XÓA", callback_data=f"execute_delete_{trx_id}")], [InlineKeyboardButton("❌ HỦY", callback_data=f"view_{trx_id}")]])
        await query.edit_message_text(f"⚠️ <b>XÓA GIAO DỊCH #{trx_id}?</b>", reply_markup=kb, parse_mode=constants.ParseMode.HTML)

    elif data.startswith("execute_delete_"):
        trx_id = data.split("_")[-1]
        if repo.delete_transaction(trx_id): await query.edit_message_text(f"✅ Xóa thành công #{trx_id}!")
        else: await query.edit_message_text("❌ Lỗi.")

async def handle_transaction_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if 'edit_trx' in context.user_data: del context.user_data['edit_trx']
    trx_id = update.message.text[1:]
    content, kb = HistoryModule(update.effective_user.id).get_detail_view(trx_id)
    await update.message.reply_html(content, reply_markup=kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    context.user_data['current_menu'] = 'HOME'
    await update.message.reply_text("🌟 <b>Hệ điều hành tài chính v2.0</b>", reply_markup=get_ceo_menu(), parse_mode=constants.ParseMode.HTML)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text
    user_id = update.effective_user.id

    if 'edit_trx' in context.user_data:
        edit_data = context.user_data['edit_trx']
        trx_id, field = edit_data['id'], edit_data['field']
        trx = repo.get_transaction_by_id(trx_id)
        if not trx:
            del context.user_data['edit_trx']
            await update.message.reply_text("❌ Giao dịch không tồn tại."); return
        try:
            rate_factor = 1
            if trx['qty'] > 0 and trx['price'] > 0: rate_factor = trx['total_value'] / (trx['qty'] * trx['price'])
            new_qty, new_price, new_date = trx['qty'], trx['price'], trx['date']
            if field == 'qty': new_qty = float(text.replace(',', '.'))
            elif field == 'price': new_price = float(text.replace(',', '.'))
            elif field == 'date':
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', text.strip()):
                    await update.message.reply_text("❌ Sai định dạng! Hãy nhập: YYYY-MM-DD"); return
                time_part = trx['date'].split()[1] if len(trx['date'].split()) > 1 else "00:00:00"
                new_date = f"{text.strip()} {time_part}"
            new_total = abs(new_qty) * new_price * rate_factor
            repo.update_transaction(trx_id, new_qty, new_price, new_total, new_date)
            del context.user_data['edit_trx']
            content, kb = HistoryModule(user_id).get_detail_view(trx_id)
            await update.message.reply_html(f"✅ <b>CẬP NHẬT THÀNH CÔNG!</b>\n\n{content}", reply_markup=kb)
        except ValueError: await update.message.reply_text("❌ Vui lòng nhập số hợp lệ.")
        return

    # --- NHÓM 1: LỘ TRÌNH ĐIỀU HƯỚNG BÁO CÁO & BỘ LỌC THỜI GIAN ---
    if text == "⬅️ Menu Báo Cáo" or text == "📊 Báo cáo":
        context.user_data['current_menu'] = 'REPORT'
        await update.message.reply_html(ReportModule(user_id).get_overview_report(), reply_markup=get_report_menu())
        return

    if text == "📊 Stock":
        context.user_data['current_menu'] = 'REPORT'
        context.user_data['report_category'] = 'STOCK'
        await update.message.reply_html(ReportModule(user_id).get_category_report('STOCK'), reply_markup=get_category_report_menu())
        return

    if text == "🪙 Crypto":
        if context.user_data.get('current_menu') == 'REPORT':
            context.user_data['report_category'] = 'CRYPTO'
            await update.message.reply_html(ReportModule(user_id).get_category_report('CRYPTO'), reply_markup=get_category_report_menu())
        else:
            context.user_data['current_menu'] = 'CRYPTO'
            await update.message.reply_html(CryptoModule(user_id).run(), reply_markup=get_crypto_menu())
        return

    if text == "🥇 Tài sản khác":
        if context.user_data.get('current_menu') == 'REPORT':
            context.user_data['report_category'] = 'OTHER'
            await update.message.reply_html(ReportModule(user_id).get_category_report('OTHER'), reply_markup=get_category_report_menu())
        else: await update.message.reply_text("Đang phát triển.")
        return

    if text == "🔍 TÌM KIẾM":
        context.user_data['report_search'] = True
        await update.message.reply_html("🔍 <b>NHẬP MÃ TÀI SẢN CẦN PHÂN TÍCH:</b>\nVí dụ: <code>FPT</code>, <code>BTC</code>...", reply_markup=get_detail_report_menu())
        return

    if text == "📅 Chọn thời gian":
        await update.message.reply_html("⏳ <b>CHỌN KHOẢNG THỜI GIAN:</b>\nNgài muốn xem báo cáo biến động trong bao lâu?", reply_markup=get_time_filter_menu())
        return

    if text == "🗓 Tùy chọn":
        context.user_data['report_custom_time'] = True
        await update.message.reply_html(
            "🗓 <b>NHẬP KHOẢNG THỜI GIAN TÙY CHỌN:</b>\nCú pháp: <code>DD/MM/YYYY - DD/MM/YYYY</code>\n\nVí dụ: <code>01/01/2026 - 26/02/2026</code>", 
            reply_markup=get_category_report_menu()
        )
        return

    time_filters = ["📅 7 Ngày qua", "📅 30 Ngày qua", "📅 3 Tháng", "📅 1 Năm", "♾ Toàn thời gian"]
    if text in time_filters:
        cat = context.user_data.get('report_category', 'STOCK')
        now = datetime.datetime.now()
        start_date = None
        label = text.replace("📅 ", "").replace("♾ ", "")
        
        if "7 Ngày" in text: start_date = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        elif "30 Ngày" in text: start_date = (now - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        elif "3 Tháng" in text: start_date = (now - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
        elif "1 Năm" in text: start_date = (now - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
        
        await update.message.reply_html(
            ReportModule(user_id).get_category_report(cat, start_date=start_date, label_time=label), 
            reply_markup=get_category_report_menu()
        )
        return

    if context.user_data.get('report_custom_time'):
        match = re.match(r'^(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})$', text.strip())
        if match:
            del context.user_data['report_custom_time']
            start_str, end_str = match.groups()
            try:
                start_date = datetime.datetime.strptime(start_str, '%d/%m/%Y').strftime('%Y-%m-%d')
                end_date = datetime.datetime.strptime(end_str, '%d/%m/%Y').strftime('%Y-%m-%d')
                cat = context.user_data.get('report_category', 'STOCK')
                label = f"Từ {start_str} đến {end_str}"
                await update.message.reply_html(
                    ReportModule(user_id).get_category_report(cat, start_date=start_date, end_date=end_date, label_time=label), 
                    reply_markup=get_category_report_menu()
                )
            except ValueError:
                await update.message.reply_text("❌ Ngày tháng không hợp lệ. Vui lòng thử lại.")
        else:
            await update.message.reply_html("❌ Sai cú pháp! Hãy nhập đúng dạng: <code>DD/MM/YYYY - DD/MM/YYYY</code>\nHoặc bấm nút để hủy.")
        return

    if context.user_data.get('report_search'):
        ticker = text.strip().upper()
        del context.user_data['report_search']
        await update.message.reply_html(ReportModule(user_id).get_ticker_detail_report(ticker), reply_markup=get_detail_report_menu())
        return

    # --- NHÓM 2: MENU CHÍNH VÀ CÁC MODULE KHÁC ---
    if text in ["💼 Tài sản của bạn", "🏠 Trang chủ"]: 
        context.user_data['current_menu'] = 'HOME'
        if 'report_search' in context.user_data: del context.user_data['report_search']
        if 'report_custom_time' in context.user_data: del context.user_data['report_custom_time']
        await update.message.reply_html(DashboardModule(user_id).run(), reply_markup=get_ceo_menu())
        return

    # --- Hợp nhất: Xử lý Xuất Excel ---
    if text in ["📥 Xuất Excel", "📥 EXPORT/IMPORT"]:
        await update.message.reply_html("⏳ <b>Đang tổng hợp dữ liệu và vẽ biểu đồ...</b>\nVui lòng chờ trong giây lát.")
        try:
            excel_file = generate_excel_report(user_id)
            file_name = f"ThanhAn_Report_{datetime.datetime.now().strftime('%d%m%Y')}.xlsx"
            await context.bot.send_document(
                chat_id=user_id,
                document=excel_file,
                filename=file_name,
                caption="📊 <b>BÁO CÁO TÀI CHÍNH THÀNH AN</b>\n<i>Đã bao gồm Dashboard, Biểu đồ và Lịch sử giao dịch.</i>",
                parse_mode=constants.ParseMode.HTML
            )
        except Exception as e:
            print(f"Lỗi xuất Excel: {e}")
            await update.message.reply_html("❌ <b>LỖI:</b> Không thể tạo báo cáo lúc này.")
        return

    if text == "📊 Chứng Khoán": await update.message.reply_html(StockModule(user_id).run(), reply_markup=get_stock_menu()); return
    if text == "📜 Lịch sử": content, kb = HistoryModule(user_id).run(); await update.message.reply_html(content, reply_markup=kb); return
    if text in ["📈 Báo cáo nhóm", "📈 Báo cáo Crypto"]:
        mod = CryptoModule(user_id) if "Crypto" in text else StockModule(user_id)
        await update.message.reply_html(mod.get_group_report()); return
    if text in ["➕ Giao dịch", "➕ Giao dịch Crypto"]:
        p = "S" if text == "➕ Giao dịch" else "C"
        await update.message.reply_html(f"➕ <b>GIAO DỊCH {p}:</b>\n<code>{p} [Mã] [SL] [Giá]</code>"); return
    if text in ["🔄 Cập nhật giá", "🔄 Cập nhật giá Crypto"]:
        await update.message.reply_html("🔄 <b>CẬP NHẬT GIÁ:</b>\n<code>gia [Mã] [Giá mới]</code>"); return
    if text in ["❌ Xóa mã", "❌ Xóa mã Crypto"]:
        await update.message.reply_html("🗑 <b>XÓA MÃ:</b> Gõ <code>xoa [Mã]</code>"); return
    if text == "🔄 Làm mới": await update.message.reply_html(f"🔄 <b>Làm mới:</b>\n\n{DashboardModule(user_id).run()}"); return

    # --- NHÓM 3: GIAO DỊCH NHANH ---
    if text.lower().startswith("xoa "):
        ticker = text.split()[1].upper()
        with db.get_connection() as conn:
            conn.execute("DELETE FROM transactions WHERE ticker = ?", (ticker,))
            conn.execute("DELETE FROM manual_prices WHERE ticker = ?", (ticker,))
        await update.message.reply_html(f"🗑 Đã xóa mã <b>{ticker}</b>."); return

    if text.lower().startswith("gia "):
        match = re.match(r'^gia\s+([a-z0-9]+)\s+([\d\.,]+)$', text.lower().strip())
        if match:
            t, p = match.group(1).upper(), float(match.group(2).replace(',', '.'))
            with db.get_connection() as conn:
                conn.execute("INSERT INTO manual_prices (ticker, current_price, updated_at) VALUES (?, ?, datetime('now', 'localtime')) ON CONFLICT(ticker) DO UPDATE SET current_price=excluded.current_price, updated_at=excluded.updated_at", (t, p))
            await update.message.reply_html(f"✅ Đã cập nhật <b>{t}</b>: <code>{p}</code>"); return

    if len(text.split()) == 1 and text.isalpha() and text.lower() not in ["gia", "xoa", "nap", "rut"]:
        content, kb = HistoryModule(user_id).run(search_query=text)
        await update.message.reply_html(content, reply_markup=kb); return

    parsed = CommandParser.parse_transaction(text)
    if parsed:
        if parsed['action'] in ['BUY', 'OUT', 'WITHDRAW']:
            current_cash = repo.get_available_cash(user_id)
            if parsed['total_val'] > current_cash:
                await update.message.reply_html("<b>Hết tiền rồi chủ tịch ơi!!!</b>"); return
        repo.save_transaction(user_id, parsed['ticker'], parsed['asset_type'], parsed['qty'], parsed['price'], parsed['total_val'], parsed['action'])
        await update.message.reply_html(f"✅ <b>Ghi nhận:</b> <code>{text.upper()}</code>\n💰: <b>{parsed['total_val']:,.0f}đ</b>"); return

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.Regex(r'^/\d+$'), handle_transaction_click))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("🚀 Bot Finance v2.0 - System Online."); application.run_polling(drop_pending_updates=True)
