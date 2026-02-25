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

# Khởi tạo Database TRƯỚC KHI import các module nghiệp vụ
from backend.database.db_manager import db
logger.info("🛠 Đang kiểm tra cấu trúc Database...")
db._init_db()

# --- BƯỚC 2: IMPORT NGHIỆP VỤ (BUSINESS LOGIC) ---
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from backend.core.parser import CommandParser
from backend.database.repository import Repository
from backend.modules.dashboard import DashboardModule

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))
repo = Repository()

# --- BƯỚC 3: GIAO DIỆN & XỬ LÝ ---
def get_main_menu():
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    dash = DashboardModule(update.effective_user.id)
    await update.message.reply_html(dash.run(), reply_markup=get_main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    parsed_data = CommandParser.parse_transaction(update.message.text)
    if parsed_data:
        try:
            repo.save_transaction(
                update.effective_user.id, parsed_data['ticker'], parsed_data['asset_type'],
                parsed_data['qty'], parsed_data['price'], parsed_data['total_val'], parsed_data['action']
            )
            undo_kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Hoàn tác (Undo)", callback_data='undo_last')]])
            msg = f"✅ <b>Đã lưu:</b> {parsed_data['action']} {parsed_data['ticker']}\n💰 Tổng: {parsed_data['total_val']:,.0f} đ"
            await update.message.reply_html(msg, reply_markup=undo_kb)
        except Exception as e:
            logger.error(f"DB Error: {e}")
            await update.message.reply_text("❌ Lỗi ghi dữ liệu.")
    else:
        await update.message.reply_text("❓ Lệnh không hợp lệ. Ví dụ: S VPB 100 22.5")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID: return
    await query.answer()
    if query.data == 'view_dashboard':
        dash = DashboardModule(update.effective_user.id)
        await query.edit_message_text(text=dash.run(), reply_markup=get_main_menu(), parse_mode=constants.ParseMode.HTML)
    elif query.data == 'undo_last':
        msg = "↩️ Đã hoàn tác!" if repo.undo_last_transaction(update.effective_user.id) else "❌ Không có gì để hoàn tác."
        await query.edit_message_text(msg)

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("🚀 Bot Finance V2.0 - CTO Edition is ONLINE")
    application.run_polling(drop_pending_updates=True)
