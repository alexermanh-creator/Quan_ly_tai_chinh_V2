# Telegram/bot_client.py
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from backend.database.repository import repo
from backend.core.parser import CommandParser
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule

class FinanceBot:
    def __init__(self):
        # Khởi tạo Bot với token từ môi trường
        self.app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
        self._register_handlers()

    def get_menu(self, menu_type="HOME"):
        """Layout Menu chuẩn bọc thép"""
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
        text = update.message.text
        user_id = update.effective_user.id
        loop = asyncio.get_running_loop()

        # 1. Xử lý Dashboard (Chạy trong luồng riêng để tránh treo Bot)
        if text in ["💼 Tài sản của bạn", "🏠 Trang chủ"]:
            module = DashboardModule(user_id)
            # Nhấc lệnh tính toán dashboard sang Executor
            response_text = await loop.run_in_executor(None, module.run)
            await update.message.reply_html(response_text, reply_markup=self.get_menu("HOME"))

        # 2. Xử lý Module Chứng Khoán
        elif text == "📊 Chứng Khoán":
            module = StockModule(user_id)
            response_text = await loop.run_in_executor(None, module.run)
            await update.message.reply_html(response_text, reply_markup=self.get_menu("STOCK"))

        # 3. Phân tích tỉ trọng
        elif text == "📈 Báo cáo nhóm":
            module = StockModule(user_id)
            response_text = await loop.run_in_executor(None, module.run, "ANALYZE")
            await update.message.reply_html(response_text, reply_markup=self.get_menu("STOCK"))

        # 4. Các nút thông báo tĩnh (Phản hồi nhanh)
        elif text == "➕ Giao dịch":
            await update.message.reply_html("📝 <b>Lệnh mẫu:</b>\n- Stock: <code>s HPG 1000 28.5</code>\n- Crypto: <code>c BTC 0.1 50000</code>", reply_markup=self.get_menu("STOCK"))
        elif text == "🔄 Cập nhật giá":
            await update.message.reply_html("🔍 Đang đồng bộ giá thị trường...", reply_markup=self.get_menu("STOCK"))

        # 5. Xử lý Lệnh Giao dịch (Logic bọc thép triệt để)
        else:
            p = CommandParser.parse_transaction(text)
            if p:
                # Chạy ghi Database trong luồng riêng để không treo Bot
                success, msg = await loop.run_in_executor(
                    None, 
                    repo.save_transaction, 
                    user_id, p['ticker'], p['asset_type'], p['qty'], p['price'], p['total_val'], p['action']
                )
                await update.message.reply_html(f"✅ Ghi nhận: {text.upper()}" if success else msg, reply_markup=self.get_menu())

    def _register_handlers(self):
        """Đăng ký các lệnh cơ bản"""
        self.app.add_handler(CommandHandler('start', lambda u, c: u.message.reply_text("S
