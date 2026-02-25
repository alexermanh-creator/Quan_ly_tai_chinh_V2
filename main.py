# main.py
import os
import logging
import sys
from dotenv import load_dotenv

# --- BƯỚC 1: KHỞI TẠO HỆ THỐNG GỐC ---
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

# --- BƯỚC 2: IMPORT LINH KIỆN ---
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from backend.core.parser import CommandParser
from backend.database.repository import Repository
from backend.modules.dashboard import DashboardModule

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))
repo = Repository()

# --- BƯỚC 3: LAYOUT ENGINE (ĐÚNG NHƯ ẢNH DEMO) ---

def get_persistent_menu():
    """Tạo Menu cố định tại ô nhập liệu (Khớp ảnh image_41b33c.png)"""
    keyboard = [
        [KeyboardButton("🏠 Trang chủ"), KeyboardButton("📊 Báo cáo")],
        [KeyboardButton("➕ Nạp tiền (Ví dụ: nap 10ty)"), KeyboardButton("🔄 Làm mới")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_main_layout():
    """Layout Menu chính 2 cột (Khớp ảnh image_41a3d6.png)"""
    keyboard = [
        [InlineKeyboardButton("💼 Tài sản của bạn", callback_data='view_dashboard')],
        [InlineKeyboardButton("📊 Chứng Khoán", callback_data='view_stock'), 
         InlineKeyboardButton("🪙 Crypto", callback_data='view_crypto')],
        [InlineKeyboardButton("🥇 Tài sản khác", callback_data='view_other'),
         InlineKeyboardButton("📜 Lịch sử", callback_data='view_history')],
        [InlineKeyboardButton("📊 Báo cáo", callback_data='view_report'),
         InlineKeyboardButton("🤖 AI Chat", callback_data='ai_chat')],
        [InlineKeyboardButton("⚙️ Cài đặt", callback_data='settings'),
         InlineKeyboardButton("📥 EXPORT/IMPORT", callback_data='data_io')],
        [InlineKeyboardButton("📸 SNAPSHOT", callback_data='snapshot'),
         InlineKeyboardButton("🔄 Làm mới", callback_data='view_dashboard')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_layout():
    """Nút quay lại thông minh cho các phản hồi lệnh"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Quay lại Trang chủ", callback_data='view_dashboard')]
    ])

# --- BƯỚC 4: HANDLERS (LOGIC ĐIỀU HƯỚNG) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    dash = DashboardModule(update.effective_user.id)
    
    # Gửi Dashboard chính kèm bộ nút 2 cột
    await update.message.reply_html(dash.run(), reply_markup=get_main_layout())
    
    # Luôn gửi kèm Menu cố định tại ô nhập liệu
    await update.message.reply_text(
        "✨ Hệ điều hành tài chính đã ONLINE.",
        reply_markup=get_persistent_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text

    # Xử lý các nút bấm từ Menu cố định (Reply Keyboard)
    if text == "🏠 Trang chủ" or text == "🔄 Làm mới":
        dash = DashboardModule(update.effective_user.id)
        await update.message.reply_html(dash.run(), reply_markup=get_main_layout())
        return
    elif text == "📊 Báo cáo":
        await update.message.reply_text("📊 Tính năng báo cáo chuyên sâu đang được xử lý...", reply_markup=get_back_layout())
        return

    # Xử lý lệnh giao dịch qua Parser (S VPB 100 22.5 hoặc nap 10ty)
    parsed_data = CommandParser.parse_transaction(text)
    if parsed_data:
        try:
            repo.save_transaction(
                update.effective_user.id, parsed_data['ticker'], parsed_data['asset_type'],
                parsed_data['qty'], parsed_data['price'], parsed_data['total_val'], parsed_data['action']
            )
            # Thông báo thành công kèm nút Back để về xem Dashboard ngay
            msg = f"✅ <b>Ghi nhận:</b> {parsed_data['action']} {parsed_data['ticker']}\n💰 Tổng: {parsed_data['total_val']:,.0f} đ"
            await update.message.reply_html(msg, reply_markup=get_back_layout())
        except Exception as e:
            logger.error(f"DB Error: {e}")
            await update.message.reply_text("❌ Lỗi Database.", reply_markup=get_back_layout())
    else:
        # Nếu gõ lệnh sai (như image_b69715.jpg), hiện hướng dẫn
        await update.message.reply_text(
            "❓ Lệnh không hợp lệ.\n💡 Thử lại: <code>nap 10ty</code> hoặc <code>S VPB 100 22.5</code>",
            reply_markup=get_back_layout()
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID: return
    await query.answer()
    
    if query.data == 'view_dashboard':
        dash = DashboardModule(update.effective_user.id)
        # Sử dụng edit_message để tạo hiệu ứng mượt mà khi chuyển menu
        await query.edit_message_text(
            text=dash.run(), 
            reply_markup=get_main_layout(), 
            parse_mode=constants.ParseMode.HTML
        )
    elif query.data == 'undo_last':
        status = "↩️ Đã hoàn tác!" if repo.undo_last_transaction(update.effective_user.id) else "❌ Không có gì để xóa."
        await query.edit_message_text(text=status, reply_markup=get_back_layout())

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("🚀 Bot Finance V2.0 - CTO Edition is ONLINE")
    application.run_polling(drop_pending_updates=True)
