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
    """Menu tại ô nhập liệu - Luôn cố định để về nhà nhanh nhất"""
    keyboard = [
        [KeyboardButton("🏠 Trang chủ"), KeyboardButton("🔄 Làm mới")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_inline_dashboard(is_sub_menu=False):
    """
    Nút bấm dưới tin nhắn Dashboard. 
    Nếu is_sub_menu=True, sẽ hiển thị nút Back thay vì Dashboard chính.
    """
    keyboard = [
        [InlineKeyboardButton("💼 Tài sản", callback_data='view_dashboard')],
        [InlineKeyboardButton("📊 Chứng Khoán", callback_data='view_stock'), 
         InlineKeyboardButton("🪙 Crypto", callback_data='view_crypto')],
        [InlineKeyboardButton("📜 Lịch sử", callback_data='view_history'),
         InlineKeyboardButton("🤖 AI Chat", callback_data='ai_chat')],
        [InlineKeyboardButton("⚙️ Cài đặt", callback_data='settings')]
    ]
    
    # Logic CTO: Luôn chèn nút Quay lại/Trang chủ ở cuối để thoát khỏi menu con
    if is_sub_menu:
        keyboard.append([InlineKeyboardButton("🔙 Quay lại Trang chủ", callback_data='view_dashboard')])
    else:
        keyboard.append([InlineKeyboardButton("🔄 Làm mới dữ liệu", callback_data='view_dashboard')])
        
    return InlineKeyboardMarkup(keyboard)

# --- BƯỚC 4: LOGIC XỬ LÝ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    dash = DashboardModule(update.effective_user.id)
    # Gửi Dashboard và kích hoạt Menu cố định
    await update.message.reply_html(
        dash.run(), 
        reply_markup=get_inline_dashboard()
    )
    await update.message.reply_text(
        "✨ Hệ điều hành tài chính đã sẵn sàng. Dùng nút 🏠 để về Trang chủ.",
        reply_markup=get_persistent_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text

    # Xử lý nút bấm cố định "🏠 Trang chủ"
    if text in ["🏠 Trang chủ", "🔄 Làm mới"]:
        dash = DashboardModule(update.effective_user.id)
        await update.message.reply_html(dash.run(), reply_markup=get_inline_dashboard())
        return

    # Xử lý Parser giao dịch
    parsed_data = CommandParser.parse_transaction(text)
    if parsed_data:
        try:
            repo.save_transaction(
                update.effective_user.id, parsed_data['ticker'], parsed_data['asset_type'],
                parsed_data['qty'], parsed_data['price'], parsed_data['total_val'], parsed_data['action']
            )
            undo_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Hoàn tác (Undo)", callback_data='undo_last')],
                [InlineKeyboardButton("🏠 Về Trang chủ", callback_data='view_dashboard')]
            ])
            msg = f"✅ <b>Ghi nhận:</b> {parsed_data['action']} {parsed_data['ticker']}\n💰 {parsed_data['total_val']:,.0f} đ"
            await update.message.reply_html(msg, reply_markup=undo_kb)
        except Exception as e:
            logger.error(f"DB Error: {e}")
            await update.message.reply_text("❌ Lỗi Database.")
    else:
        # Nếu gõ sai, hiện hướng dẫn kèm nút về nhà
        await update.message.reply_text(
            "❓ Lệnh không hợp lệ.\nVí dụ: <code>nap 10ty</code> hoặc <code>S VPB 100 22.5</code>",
            reply_markup=get_inline_dashboard(is_sub_menu=True)
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID: return
    await query.answer()
    
    # Tại đây, bất kể bấm nút gì, nếu cần quay lại chỉ cần gọi get_inline_dashboard(is_sub_menu=True)
    if query.data == 'view_dashboard':
        dash = DashboardModule(update.effective_user.id)
        await query.edit_message_text(
            text=dash.run(), 
            reply_markup=get_inline_dashboard(), 
            parse_mode=constants.ParseMode.HTML
        )
    
    elif query.data == 'undo_last':
        status = "↩️ Đã hoàn tác!" if repo.undo_last_transaction(update.effective_user.id) else "❌ Không có gì để xóa."
        await query.edit_message_text(
            text=status,
            reply_markup=get_inline_dashboard(is_sub_menu=True) # Hiện nút Back để về nhà
        )

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("🚀 Bot Finance V2.0 - ONLINE")
    application.run_polling(drop_pending_updates=True)
