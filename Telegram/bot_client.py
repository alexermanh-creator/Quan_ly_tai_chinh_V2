# Telegram/bot_client.py
import os
import re
import logging
import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, constants, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# Import các module từ backend (Đảm bảo các file này tồn tại theo cấu trúc của bạn)
from backend.database.db_manager import db
from backend.database.repository import repo  # Sử dụng instance repo từ repository
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

    # --- HỆ THỐNG MENU (Hợp nhất từ bản cũ) ---
    def get_menu(self, menu_type="HOME"):
        menus = {
            "HOME": [
                [KeyboardButton("💼 Tài sản của bạn")],
                [KeyboardButton("📊 Chứng Khoán"), KeyboardButton("🪙 Crypto")],
                [KeyboardButton("🥇 Tài sản khác"), KeyboardButton("📜 Lịch sử")],
                [KeyboardButton("📊 Báo cáo"), KeyboardButton("🤖 AI Chat")],
                [KeyboardButton("⚙️ Cài đặt"), KeyboardButton("📥 EXPORT/IMPORT")],
                [KeyboardButton("📸 SNAPSHOT"), KeyboardButton("🔄 Làm mới")]
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
                [KeyboardButton("📊 Stock"), KeyboardButton("🪙 Crypto"), KeyboardButton("🥇 Tài sản khác")],
                [KeyboardButton("🔍 TÌM KIẾM"), KeyboardButton("📥 Xuất Excel"), KeyboardButton("🏠 Trang chủ")]
            ]
        }
        return ReplyKeyboardMarkup(menus.get(menu_type, menus["HOME"]), resize_keyboard=True)

    # --- HANDLERS CHÍNH ---
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        context.user_data['current_menu'] = 'HOME'
        await update.message.reply_html("🌟 <b>Hệ điều hành tài chính v2.0</b>", reply_markup=self.get_menu("HOME"))

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data
        hist = HistoryModule(user_id)

        if data.startswith("hist_page_") or data.startswith("hist_filter_"):
            parts = data.split("_")
            page = int(parts[2]) if "page" in data else 0
            a_type = parts[-1] if parts[-1] != 'ALL' else None
            text, kb = hist.run(page=page, asset_type=a_type)
            await query.edit_message_text(text, reply_markup=kb, parse_mode=constants.ParseMode.HTML)

        elif data == "go_home":
            context.user_data['current_menu'] = 'HOME'
            await query.message.reply_html(DashboardModule(user_id).run(), reply_markup=self.get_menu("HOME"))
        
        # ... (Các logic Callback khác như edit_, delete_ giữ nguyên từ bản cũ của bạn)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        text = update.message.text
        user_id = update.effective_user.id

        # 1. Xử lý điều hướng Menu
        if text in ["💼 Tài sản của bạn", "🏠 Trang chủ", "🔄 Làm mới"]:
            context.user_data['current_menu'] = 'HOME'
            await update.message.reply_html(DashboardModule(user_id).run(), reply_markup=self.get_menu("HOME"))
        
        elif text == "📊 Chứng Khoán":
            context.user_data['current_menu'] = 'STOCK'
            await update.message.reply_html(StockModule(user_id).run(), reply_markup=self.get_menu("STOCK"))

        elif text == "🪙 Crypto":
            context.user_data['current_menu'] = 'CRYPTO'
            await update.message.reply_html(CryptoModule(user_id).run(), reply_markup=self.get_menu("CRYPTO"))

        elif text == "📊 Báo cáo":
            context.user_data['current_menu'] = 'REPORT'
            await update.message.reply_html(ReportModule(user_id).get_overview_report(), reply_markup=self.get_menu("REPORT"))

        elif text == "📜 Lịch sử":
            content, kb = HistoryModule(user_id).run()
            await update.message.reply_html(content, reply_markup=kb)

        # 2. Xử lý Xuất Excel
        elif text in ["📥 Xuất Excel", "📥 EXPORT/IMPORT"]:
            await update.message.reply_html("⏳ <b>Đang xử lý báo cáo...</b>")
            try:
                excel_file = generate_excel_report(user_id)
                await context.bot.send_document(chat_id=user_id, document=excel_file, filename=f"Bao_Cao_{datetime.datetime.now().strftime('%d%m%Y')}.xlsx")
            except Exception as e:
                await update.message.reply_text(f"❌ Lỗi: {e}")

        # 3. Xử lý Parse lệnh giao dịch (Giai đoạn 2)
        else:
            parsed = CommandParser.parse_transaction(text)
            if parsed:
                # Logic kiểm tra tiền mặt và lưu repository
                repo.save_transaction(user_id, parsed['ticker'], parsed['asset_type'], parsed['qty'], parsed['price'], parsed['total_val'], parsed['action'])
                await update.message.reply_html(f"✅ <b>Ghi nhận:</b> <code>{text.upper()}</code>")
            else:
                await update.message.reply_text("❓ Tôi không hiểu lệnh này. Gõ /help để xem hướng dẫn.")

    def _register_handlers(self):
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

    def run(self):
        print("🚀 Bot Finance v2.0 - System Online.")
        self.app.run_polling(drop_pending_updates=True)

bot_app = FinanceBot()
