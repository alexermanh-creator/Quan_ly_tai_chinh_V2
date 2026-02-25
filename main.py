# main.py
import os
import logging
import sys
from dotenv import load_dotenv

# --- BƯỚC 1: KHỞI TẠO HỆ THỐNG GỐC (BOOTSTRAP) ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
load_dotenv()

from backend.database.db_manager import db
logger.info("🛠 Đang kiểm tra cấu trúc Database...")
db._init_db()

# --- BƯỚC 2: IMPORT NGHIỆP VỤ ---
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from backend.core.parser import CommandParser
from backend.database.repository import Repository
from backend.modules.dashboard import DashboardModule

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))
repo = Repository()

# --- BƯỚC 3: CẤU CẤU HÌNH GIAO DIỆN (UI/UX) ---

def get_persistent_menu():
    """Tạo Menu cố định tại ô nhập liệu (Dấu ::)"""
    keyboard = [
        [KeyboardButton("🏠 Trang chủ"), KeyboardButton("📊 Báo cáo")],
        [KeyboardButton("➕ Nạp tiền (Ví dụ: nap 10ty)"), KeyboardButton("🔄 Làm mới")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_inline_dashboard():
    """Nút bấm dưới tin nhắn Dashboard"""
    keyboard = [
        [InlineKeyboardButton("💼 Tài sản của bạn", callback_data='view_dashboard')],
        [InlineKeyboardButton("📊 Chứng Khoán", callback_data='view_stock'), 
         InlineKeyboardButton("🪙 Crypto", callback_data='view_crypto')],
        [InlineKeyboardButton("📜 Lịch sử", callback_data='view_history'),
         InlineKeyboardButton("🤖 AI Chat", callback_data='ai_chat')],
        [InlineKeyboardButton("⚙️ Cài đặt", callback_data='settings'),
         InlineKeyboardButton("🔄 Làm mới", callback_data='view_dashboard')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- BƯỚC 4: LOGIC XỬ LÝ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    dash = DashboardModule(update.effective_user.id)
    # Gửi Dashboard kèm theo Menu cố định ở ô nhập liệu
    await update.message.reply_html(
        dash.run(), 
        reply_markup=get_inline_dashboard()
    )
    # Kích hoạt bàn phím cố định
    await update.message.reply_text(
        "⌨️ Đã kết nối Hệ điều hành Tài chính. Sử dụng Menu bên dưới để thao tác nhanh.",
        reply_markup=get_persistent_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text

    # Xử lý các nút bấm từ Menu cố định
    if text == "🏠 Trang chủ" or text == "🔄 Làm mới":
        dash = DashboardModule(update.effective_user.id)
        await update.message.reply_html(dash.run(), reply_markup=get_inline_dashboard())
        return
    elif text == "➕ Nạp tiền (Ví dụ: nap 10ty)":
        await update.message.reply_text("💡 Bạn hãy gõ theo cú pháp: `nap 10ty` hoặc `nap 500tr`", parse_mode='Markdown')
        return

    # Xử lý Parser cho lệnh giao dịch và nạp/rút
    parsed_data = CommandParser.parse_transaction(text)
    
    if parsed_data:
        try:
            repo.save_transaction(
                update.effective_user.id, parsed_data['ticker'], parsed_data['asset_type'],
                parsed_data['qty'], parsed_data['price'], parsed_data['total_val'], parsed_data['action']
            )
            
            undo_kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Hoàn tác (Undo)", callback_data='undo_last')]])
            
            # Format hiển thị số tiền đẹp chuẩn CTO
            formatted_val = f"{parsed_data['total_val']:,.0f}".replace(',', '.')
            msg = (
                f"✅ <b>Ghi nhận thành công:</b>\n"
                f"🔹 Lệnh: {parsed_data['action']}\n"
                f"🔹 Đối tượng: {parsed_data['ticker']}\n"
                f"💰 Giá trị: {formatted_val} đ"
            )
            await update.message.reply_html(msg, reply_markup=undo_kb)
        except Exception as e:
            logger.error(f"DB Error: {e}")
            await update.message.reply_text("❌ Lỗi ghi dữ liệu vào Database.")
    else:
        await update.message.reply_text("❓ Lệnh không hợp lệ.\n- Nạp tiền: <code>nap 10ty</code>\n- Giao dịch: <code>S VPB 100 22.5</code>")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID: return
    await query.answer()
    
    if query.data == 'view_dashboard':
        dash = DashboardModule(update.effective_user.id)
        await query.edit_message_text(text=dash.run(), reply_markup=get_inline_dashboard(), parse_mode=constants.ParseMode.HTML)
    
    elif query.data == 'undo_last':
        if repo.undo_last_transaction(update.effective_user.id):
            await query.edit_message_text("↩️ Đã hoàn tác thành công!")
        else:
            await query.edit_message_text("❌ Không có giao dịch nào để xóa.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("🚀 Bot Finance V2.0 - CTO Edition is ONLINE")
    application.run_polling(drop_pending_updates=True)
