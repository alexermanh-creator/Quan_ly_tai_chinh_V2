# Telegram/bot_client.py
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

from backend.database.repository import repo
from backend.core.parser import CommandParser
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))

class FinanceBot:
    def __init__(self):
        self.app = ApplicationBuilder().token(TOKEN).build()
        self._register_handlers()

    def get_menu(self, menu_type="HOME"):
        menus = {
            "HOME": [[KeyboardButton("💼 Tài sản của bạn")], [KeyboardButton("📊 Chứng Khoán"), KeyboardButton("🪙 Crypto")], [KeyboardButton("🔄 Làm mới")]],
            "STOCK": [[KeyboardButton("➕ Giao dịch"), KeyboardButton("🔄 Cập nhật giá")], [KeyboardButton("🏠 Trang chủ")]]
        }
        return ReplyKeyboardMarkup(menus.get(menu_type, menus["HOME"]), resize_keyboard=True)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        text, user_id = update.message.text, update.effective_user.id

        if text in ["💼 Tài sản của bạn", "🏠 Trang chủ", "🔄 Làm mới"]:
            await update.message.reply_html(DashboardModule(user_id).run(), reply_markup=self.get_menu("HOME"))
        elif text == "📊 Chứng Khoán":
            await update.message.reply_html(StockModule(user_id).run(), reply_markup=self.get_menu("STOCK"))
        else:
            parsed = CommandParser.parse_transaction(text)
            if parsed:
                success, msg = repo.save_transaction(user_id, parsed['ticker'], parsed['asset_type'], parsed['qty'], parsed['price'], parsed['total_val'], parsed['action'])
                await update.message.reply_html(f"✅ <b>Ghi nhận:</b> <code>{text.upper()}</code>" if success else msg, reply_markup=self.get_menu("HOME"))
            else:
                await update.message.reply_text("❓ Lệnh không rõ.", reply_markup=self.get_menu("HOME"))

    def _register_handlers(self):
        self.app.add_handler(CommandHandler('start', lambda u, c: u.message.reply_text("Chào sếp!", reply_markup=self.get_menu())))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

    def run(self): self.app.run_polling(drop_pending_updates=True)

bot_app = FinanceBot()
