# main.py
import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from backend.core.parser import CommandParser
from backend.database.repository import Repository
from backend.modules.dashboard import DashboardModule

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))
repo = Repository()

def get_ceo_menu():
    """Layout Menu (::) chuẩn CEO: Tài sản hàng đầu, các nút khác 2 cột"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("💼 Tài sản của bạn")], # Hàng 1: Ưu tiên cao nhất
        [KeyboardButton("📊 Chứng Khoán"), KeyboardButton("🪙 Crypto")],
        [KeyboardButton("🥇 Tài sản khác"), KeyboardButton("📜 Lịch sử")],
        [KeyboardButton("📊 Báo cáo"), KeyboardButton("🤖 AI Chat")],
        [KeyboardButton("⚙️ Cài đặt"), KeyboardButton("📥 EXPORT/IMPORT")],
        [KeyboardButton("📸 SNAPSHOT"), KeyboardButton("🔄 Làm mới")]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(
        "🌟 <b>Hệ điều hành tài chính v2.0</b>\nẤn biểu tượng (::) để quản lý tài sản.",
        reply_markup=get_ceo_menu(),
        parse_mode=constants.ParseMode.HTML
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text

    # 1. Điều hướng nút bấm
    if text == "💼 Tài sản của bạn":
        dash = DashboardModule(update.effective_user.id)
        await update.message.reply_html(dash.run())
        return
    
    if text == "🔄 Làm mới":
        dash = DashboardModule(update.effective_user.id)
        await update.message.reply_html(f"🔄 <b>Dữ liệu đã được cập nhật mới nhất:</b>\n\n{dash.run()}")
        return

    # 2. Xử lý logic nhập liệu thông minh (nap 10ty, S HPG 100 25...)
    parsed_data = CommandParser.parse_transaction(text)
    if parsed_data:
        try:
            repo.save_transaction(
                user_id=update.effective_user.id,
                ticker=parsed_data['ticker'],
                asset_type=parsed_data['asset_type'],
                qty=parsed_data['qty'],
                price=parsed_data['price'],
                total_value=parsed_data['total_val'],
                type=parsed_data['action']
            )
            # Format tiền để thông báo cho sang trọng
            val_format = f"{parsed_data['total_val']:,.0f}".replace(',', '.')
            await update.message.reply_html(f"✅ <b>Ghi nhận thành công:</b>\n<code>{text.upper()}</code>\n💰 Giá trị: <b>{val_format}đ</b>")
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi Database: {e}")
    else:
        await update.message.reply_text("❓ Lệnh không hợp lệ. Hãy sử dụng Menu (::) hoặc gõ ví dụ: <code>nap 10ty</code>")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.run_polling(drop_pending_updates=True)
