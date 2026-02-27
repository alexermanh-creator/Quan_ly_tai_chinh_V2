# Telegram/bot_client.py
import os
import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# Import từ backend (đảm bảo viết thường đúng tên thư mục)
from backend.database.db_manager import db
from backend.database.repository import repo
from backend.core.parser import CommandParser
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.crypto import CryptoModule 
from backend.modules.history import HistoryModule
from backend.modules.report import ReportModule
from backend.modules.export import generate_excel_report

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))

class FinanceBot:
    def __init__(self):
        self.app = ApplicationBuilder().token(TOKEN).build()
        self._register_handlers()

    def get_menu(self, menu_type="HOME"):
        menus = {
            "HOME": [
                [KeyboardButton("💼 Tài sản của bạn")],
                [KeyboardButton("📊 Chứng Khoán"), KeyboardButton("🪙 Crypto")],
                [KeyboardButton("🥇 Tài sản khác"), KeyboardButton("📜 Lịch sử")],
                [KeyboardButton("📊 Báo cáo"), KeyboardButton("🤖 AI Chat")],
                [KeyboardButton("⚙️ Cài đặt"), KeyboardButton("📥 EXPORT/IMPORT")],
                [KeyboardButton("🔄 Làm mới")]
            ],
            "STOCK": [
                [KeyboardButton("➕ Giao dịch"), KeyboardButton("🔄 Cập nhật giá")],
                [KeyboardButton("📈 Báo cáo nhóm"), KeyboardButton("🏠 Trang chủ")]
            ],
            "CRYPTO": [
                [KeyboardButton("➕ Giao dịch Crypto"), KeyboardButton("🔄 Cập nhật giá Crypto")],
                [KeyboardButton("🏠 Trang chủ")]
            ],
            "REPORT": [
                [KeyboardButton("📊 Stock"), KeyboardButton("🪙 Crypto")],
                [KeyboardButton("🏠 Trang chủ")]
            ]
        }
        return ReplyKeyboardMarkup(menus.get(menu_type, menus["HOME"]), resize_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        await update.message.reply_html("🌟 <b>Hệ điều hành tài chính v2.0</b>\nChào sếp, hệ thống đã sẵn sàng.", reply_markup=self.get_menu("HOME"))

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        text = update.message.text
        user_id = update.effective_user.id

        if text in ["💼 Tài sản của bạn", "🏠 Trang chủ", "🔄 Làm mới"]:
            await update.message.reply_html(DashboardModule(user_id).run(), reply_markup=self.get_menu("HOME"))
        elif text == "📊 Chứng Khoán":
            await update.message.reply_html(StockModule(user_id).run(), reply_markup=self.get_menu("STOCK"))
        elif text == "🪙 Crypto":
            await update.message.reply_html(CryptoModule(user_id).run(), reply_markup=self.get_menu("CRYPTO"))
        elif text == "📊 Báo cáo":
            await update.message.reply_html(ReportModule(user_id).get_overview_report(), reply_markup=self.get_menu("REPORT"))
        elif text == "📜 Lịch sử":
            content, kb = HistoryModule(user_id).run()
            await update.message.reply_html(content, reply_markup=kb)
        elif text == "➕ Giao dịch":
            await update.message.reply_html("📝 <b>Lệnh:</b> <code>HPG 1000 28.5</code>\n💡 <i>Lưu ý: Phải 'chuyen' tiền vào ví STOCK trước.</i>")
        elif text == "➕ Giao dịch Crypto":
            await update.message.reply_html("📝 <b>Lệnh:</b> <code>C BTC 0.01 65000</code>")
        elif text == "📥 EXPORT/IMPORT":
            await update.message.reply_html("⏳ <b>Đang xuất file Excel...</b>")
            excel_file = generate_excel_report(user_id)
            await context.bot.send_document(chat_id=user_id, document=excel_file, filename=f"Report_{datetime.datetime.now().strftime('%d%m')}.xlsx")
        else:
            parsed = CommandParser.parse_transaction(text)
            if parsed:
                if parsed.get('action') == 'SET_SETTING':
                    repo.set_setting(parsed['key'], parsed['value'], user_id)
                    await update.message.reply_html(f"✅ Đã cập nhật <code>{parsed['key']}</code> = <b>{parsed['value']:,}</b>")
                else:
                    success, msg = repo.save_transaction(user_id, parsed['ticker'], parsed['asset_type'], parsed['qty'], parsed['price'], parsed['total_val'], parsed['action'])
                    await update.message.reply_html(f"✅ <b>Ghi nhận:</b> <code>{text.upper()}</code>" if success else msg)
            else:
                await update.message.reply_text("❓ Lệnh không rõ. Ví dụ: 'nap 100tr', 'chuyen 50tr stock', 'HPG 100 30'")

    def _register_handlers(self):
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "go_home":
            await query.message.reply_html(DashboardModule(query.from_user.id).run(), reply_markup=self.get_menu("HOME"))

    def run(self):
        self.app.run_polling(drop_pending_updates=True)

bot_app = FinanceBot()
