# main.py
import os
import re
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, constants, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from backend.core.parser import CommandParser
from backend.database.repository import Repository
from backend.database.db_manager import db
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.crypto import CryptoModule 
from backend.modules.history import HistoryModule # 1. Import mới

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
        [KeyboardButton("⚙️ Cài đặt"), KeyboardButton("📥 EXPORT/IMPORT")]
    ], resize_keyboard=True)

# --- XỬ LÝ CALLBACK (CHO NÚT BẤM INLINE) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    hist = HistoryModule(user_id)

    # Xử lý Phân trang & Lọc
    if data.startswith("hist_page_") or data.startswith("hist_filter_"):
        parts = data.split("_")
        page = int(parts[2]) if "page" in data else 0
        a_type = parts[-1] if parts[-1] != 'ALL' else None
        text, kb = hist.run(page=page, asset_type=a_type)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=constants.ParseMode.HTML)

    # Xử lý Về Home
    elif data == "go_home":
        dash = DashboardModule(user_id)
        await query.message.reply_html(dash.run(), reply_markup=get_ceo_menu())

    # Xử lý Xác nhận Xóa
    elif data.startswith("confirm_delete_"):
        trx_id = data.split("_")[-1]
        text = f"⚠️ <b>XÁC NHẬN XÓA?</b>\nBạn chắc chắn muốn xóa vĩnh viễn giao dịch #{trx_id}?"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ CÓ, XÓA NGAY", callback_data=f"execute_delete_{trx_id}")],
            [InlineKeyboardButton("❌ HỦY", callback_data=f"view_{trx_id}")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode=constants.ParseMode.HTML)

    # Thực thi Xóa
    elif data.startswith("execute_delete_"):
        trx_id = data.split("_")[-1]
        if repo.delete_transaction(trx_id):
            await query.edit_message_text(f"✅ Đã xóa thành công giao dịch #{trx_id}!")
        else:
            await query.edit_message_text("❌ Lỗi: Không thể xóa giao dịch.")

# --- XỬ LÝ MESSAGE ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text
    user_id = update.effective_user.id

    # Lệnh xem chi tiết (Deep Link)
    if text.startswith("/view_"):
        trx_id = text.split("_")[1]
        hist = HistoryModule(user_id)
        content, kb = hist.get_detail_view(trx_id)
        await update.message.reply_html(content, reply_markup=kb)
        return

    # 1. NÚT BẤM EXACT MATCH
    if text == "📜 Lịch sử":
        hist = HistoryModule(user_id)
        content, kb = hist.run()
        await update.message.reply_html(content, reply_markup=kb)
        return

    if text in ["💼 Tài sản của bạn", "🏠 Trang chủ"]:
        dash = DashboardModule(user_id)
        await update.message.reply_html(dash.run(), reply_markup=get_ceo_menu())
        return

    # 2. TÌM KIẾM NHANH (Ví dụ gõ 'vpb' hoặc 'btc')
    # Nếu text chỉ có 1 từ và không phải lệnh hệ thống -> Tìm lịch sử mã đó
    parts = text.split()
    if len(parts) == 1 and text.isalpha() and text.lower() not in ["gia", "xoa", "nap", "rut"]:
        hist = HistoryModule(user_id)
        content, kb = hist.run(search_query=text)
        await update.message.reply_html(content, reply_markup=kb)
        return

    # 3. LỆNH CẬP NHẬT GIÁ
    if text.lower().startswith("gia "):
        match = re.match(r'^gia\s+([a-z0-9]+)\s+([\d\.,]+)$', text.lower().strip())
        if match:
            ticker, price = match.group(1).upper(), float(match.group(2).replace(',', '.'))
            with db.get_connection() as conn:
                conn.execute("INSERT INTO manual_prices (ticker, current_price, updated_at) VALUES (?, ?, datetime('now', 'localtime')) ON CONFLICT(ticker) DO UPDATE SET current_price=excluded.current_price, updated_at=excluded.updated_at", (ticker, price))
                conn.commit()
            await update.message.reply_html(f"✅ Đã cập nhật giá mới cho <b>{ticker}</b>: <code>{price}</code>")
        return

    # 4. PARSER GIAO DỊCH (S, C, nap, rut)
    parsed_data = CommandParser.parse_transaction(text)
    if parsed_data:
        repo.save_transaction(user_id, parsed_data['ticker'], parsed_data['asset_type'], parsed_data['qty'], parsed_data['price'], parsed_data['total_val'], parsed_data['action'])
        val_f = f"{parsed_data['total_val']:,.0f}".replace(',', '.')
        await update.message.reply_html(f"✅ <b>Ghi nhận thành công:</b>\n📝 Lệnh: <code>{text.upper()}</code>\n💰 Giá trị: <b>{val_f}đ</b>")
        return

if __name__ == '__main__':
    from telegram import InlineKeyboardButton # Đảm bảo import đầy đủ cho callback
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(handle_callback)) # Xử lý nút bấm
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 Bot Finance v2.0 - History Module Active...")
    application.run_polling(drop_pending_updates=True)
