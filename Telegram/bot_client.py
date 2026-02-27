# Telegram/bot_client.py
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from backend.database.repository import repo
from backend.core.parser import CommandParser
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule

class FinanceBot:
    def __init__(self):
        self.app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
        self._register_handlers()

    def get_menu(self, menu_type="HOME"):
        if menu_type == "STOCK":
            return ReplyKeyboardMarkup([
                [KeyboardButton("➕ Giao dịch"), KeyboardButton("🔄 Cập nhật giá")],
                [KeyboardButton("📈 Báo cáo nhóm"), KeyboardButton("🏠 Trang chủ")]
            ], resize_keyboard=True)
        return ReplyKeyboardMarkup([
            [KeyboardButton("💼 Tài sản của bạn")],
            [KeyboardButton("📊 Chứng Khoán"), KeyboardButton("🪙 Crypto")],
            [KeyboardButton("🥇 Tài sản khác"), KeyboardButton("📜 Lịch sử")],
            [KeyboardButton("📊 Báo cáo"), KeyboardButton("🤖 AI Chat")],
            [KeyboardButton("⚙️ Cài đặt"), KeyboardButton("📥 EXPORT/IMPORT")]
        ], resize_keyboard=True)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text, user_id = update.message.text, update.effective_user.id
        if text in ["💼 Tài sản của bạn", "🏠 Trang chủ"]:
            await update.message.reply_html(DashboardModule(user_id).run(), reply_markup=self.get_menu("HOME"))
        elif text == "📊 Chứng Khoán":
            await update.message.reply_html(StockModule(user_id).run(), reply_markup=self.get_menu("STOCK"))
        elif text == "➕ Giao dịch":
            await update.message.reply_html("📝 <b>Lệnh mẫu:</b> <code>s HPG 1000 28.5</code>", reply_markup=self.get_menu("STOCK"))
        elif text == "🔄 Cập nhật giá":
            await update.message.reply_html("🔍 Đang đồng bộ giá thị trường...", reply_markup=self.get_menu("STOCK"))
        elif text == "📈 Báo cáo nhóm":
            await update.message.reply_html("📊 Đang phân tích tỉ trọng...", reply_markup=self.get_menu("STOCK"))
        else:
            p = CommandParser.parse_transaction(text)
            if p:
                success, msg = repo.save_transaction(user_id, p['ticker'], p['asset_type'], p['qty'], p['price'], p['total_val'], p['action'])
                await update.message.reply_html(f"✅ Ghi nhận: {text.upper()}" if success else msg, reply_markup=self.get_menu())

    def _register_handlers(self):
        self.app.add_handler(CommandHandler('start', lambda u, c: u.message.reply_text("Sẵn sàng!", reply_markup=self.get_menu())))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

    def run(self): self.app.run_polling()

bot_app = FinanceBot()
