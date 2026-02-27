# Telegram/bot_client.py
import os
import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# Import các module từ backend
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
                [KeyboardButton("📈 Báo cáo nhóm"), KeyboardButton("❌ Xóa mã")],
                [KeyboardButton("🏠 Trang chủ")]
            ],
            "CRYPTO": [
                [KeyboardButton("➕ Giao dịch Crypto"), KeyboardButton("🔄 Cập nhật giá Crypto")],
                [KeyboardButton("📈 Báo cáo Crypto"), KeyboardButton("❌ Xóa mã Crypto")],
                [KeyboardButton("🏠 Trang chủ")]
            ],
            "REPORT": [
                [KeyboardButton("📊 Stock"), KeyboardButton("🪙 Crypto")],
                [KeyboardButton("📥 Xuất Excel"), KeyboardButton("🏠 Trang chủ")]
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

        # 1. ĐIỀU HƯỚNG MENU CỨNG
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

        # 2. XỬ LÝ NÚT CHỨC NĂNG (Hướng dẫn nhập lệnh)
        elif text in ["➕ Giao dịch", "➕ Giao dịch Crypto"]:
            await update.message.reply_html("📝 <b>Lệnh giao dịch:</b>\n• Stock: <code>HPG 1000 28.5</code>\n• Crypto: <code>C BTC 0.01 65000</code>")
        
        elif text in ["🔄 Cập nhật giá", "🔄 Cập nhật giá Crypto"]:
            await update.message.reply_html("🔄 <b>Lệnh cập nhật giá:</b>\n<code>gia HPG 30.5</code>")

        elif text == "📥 Xuất Excel":
            await update.message.reply_html("⏳ <b>Đang trích xuất dữ liệu...</b>")
            try:
                excel_file = generate_excel_report(user_id)
                await context.bot.send_document(chat_id=user_id, document=excel_file, filename=f"Bao_Cao_{datetime.datetime.now().strftime('%d%m%Y')}.xlsx")
            except Exception as e:
                await update.message.reply_text(f"❌ Lỗi: {e}")

        # 3. PARSER LỆNH CHUẨN
        else:
            parsed = CommandParser.parse_transaction(text)
            if parsed:
                # A. Xử lý cài đặt (Tỷ giá EX_RATE)
                if parsed.get('action') == 'SET_SETTING':
                    repo.set_setting(parsed['key'], parsed['value'], user_id)
                    await update.message.reply_html(f"⚙️ <b>Đã cập nhật:</b> <code>{parsed['key']} = {parsed['value']:,}</code>")
                
                # B. Xử lý giao dịch tài sản
                else:
                    success, msg = repo.save_transaction(
                        user_id, parsed['ticker'], parsed['asset_type'], 
                        parsed['qty'], parsed['price'], parsed['total_val'], parsed['action']
                    )
                    if success:
                        formatted_val = repo.format_smart_currency(parsed['total_val'])
                        await update.message.reply_html(f"✅ <b>Ghi nhận:</b> <code>{text.upper()}</code>\n💰 Giá trị: {formatted_val}")
                    else:
                        await update.message.reply_html(msg) # Hiện lỗi thiếu tiền
            else:
                await update.message.reply_text("❓ Lệnh không hợp lệ. Hãy thử: 'nap 10tr' hoặc 'HPG 100 30'")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data
        
        # Xử lý phân trang lịch sử (History)
        if data.startswith("hist_page_") or data.startswith("hist_filter_"):
            parts = data.split("_")
            page = int(parts[2]) if "page" in data else 0
            a_type = parts[-1] if parts[-1] not in ['ALL', 'prompt'] else None
            text, kb = HistoryModule(user_id).run(page=page, asset_type=a_type)
            await query.edit_message_text(text, reply_markup=kb, parse_mode=constants.ParseMode.HTML)
        
        elif data == "go_home":
            await query.message.reply_html(DashboardModule(user_id).run(), reply_markup=self.get_menu("HOME"))

    def _register_handlers(self):
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

    def run(self):
        print("🚀 Bot Finance v2.0 - System Online.")
        self.app.run_polling(drop_pending_updates=True)

bot_app = FinanceBot()
