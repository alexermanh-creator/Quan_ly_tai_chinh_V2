# main.py
import os
import logging
import sys
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# Import các module nội bộ
from backend.core.parser import CommandParser
from backend.database.repository import Repository
from backend.modules.dashboard import DashboardModule
from backend.database.db_manager import db

# 1. CẤU HÌNH LOGGING CHUYÊN NGHIỆP
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout) # Đẩy log ra console của Railway
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Kiểm tra cấu hình bảo mật
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID_STR = os.getenv("ADMIN_USER_ID")

if not TOKEN or not ADMIN_ID_STR:
    logger.critical("❌ LỖI: Thiếu TELEGRAM_BOT_TOKEN hoặc ADMIN_USER_ID trong cấu hình Environment Variables!")
    sys.exit(1)

ADMIN_ID = int(ADMIN_ID_STR)
repo = Repository()

# 2. GIAO DIỆN NÚT BẤM (DASHBOARD LAYOUT)
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

# 3. CÁC HÀM XỬ LÝ SỰ KIỆN (HANDLERS)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /start - Hiện Dashboard chính"""
    if update.effective_user.id != ADMIN_ID:
        logger.warning(f"Truy cập trái phép từ ID: {update.effective_user.id}")
        return
    
    dash = DashboardModule(update.effective_user.id)
    text = dash.run()
    await update.message.reply_html(text, reply_markup=get_main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nhập lệnh giao dịch bằng tay"""
    if update.effective_user.id != ADMIN_ID:
        return

    text = update.message.text
    parsed_data = CommandParser.parse_transaction(text)
    
    if parsed_data:
        try:
            repo.save_transaction(
                user_id=update.effective_user.id,
                ticker=parsed_data['ticker'],
                asset_type=parsed_data['asset_type'],
                qty=parsed_data['qty'],
                price=parsed_data['price'],
                total_val=parsed_data['total_val'],
                t_type=parsed_data['action']
            )
            
            undo_kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Hoàn tác (Undo)", callback_data='undo_last')]])
            
            success_msg = (
                f"✅ <b>Ghi nhận thành công:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Lệnh: <b>{parsed_data['action']}</b>\n"
                f"🔹 Mã: <b>{parsed_data['ticker']}</b>\n"
                f"💰 Tổng: <b>{parsed_data['total_val']:,.0f} đ</b>"
            )
            await update.message.reply_html(success_msg, reply_markup=undo_kb)
        except Exception as e:
            logger.error(f"Lỗi ghi DB: {e}")
            await update.message.reply_text("❌ Lỗi hệ thống khi lưu giao dịch.")
    else:
        await update.message.reply_text("❓ Lệnh không hợp lệ. Thử lại: S VPB 100 22.5")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi người dùng bấm các nút Inline"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("Bạn không có quyền!", show_alert=True)
        return

    await query.answer()

    if query.data == 'view_dashboard':
        dash = DashboardModule(user_id)
        await query.edit_message_text(
            text=dash.run(), 
            reply_markup=get_main_menu(), 
            parse_mode=constants.ParseMode.HTML
        )
    
    elif query.data == 'undo_last':
        if repo.undo_last_transaction(user_id):
            await query.edit_message_text("↩️ Đã hoàn tác lệnh cuối cùng thành công!")
        else:
            await query.edit_message_text("❌ Không có lệnh nào để hoàn tác.")

# 4. KHỞI CHẠY (ENTRY POINT)
if __name__ == '__main__':
    # Đảm bảo Database luôn được khởi tạo trước
    db._init_db()
    
    # Khởi tạo Bot Application
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Đăng ký các cổng lắng nghe
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("🚀 Bot Finance V2.0 - CTO Edition is ONLINE")
    
    # Chạy Bot với cơ chế xóa tin nhắn kẹt (Conflict Protection)
    application.run_polling(drop_pending_updates=True)
