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
        # Khởi tạo Application từ Token trong biến môi trường
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("❌ Không tìm thấy TELEGRAM_BOT_TOKEN trong biến môi trường Railway!")
            
        self.app = ApplicationBuilder().token(token).build()
        self._register_handlers()

    def get_menu(self, menu_type="HOME"):
        """Xây dựng Menu chuẩn cho từng trạng thái"""
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
        if not update.message or not update.message.text:
            return

        text = update.message.text
        user_id = update.effective_user.id
        loop = asyncio.get_running_loop()

        # 1. Dashboard & Home
        if text in ["💼 Tài sản của bạn", "🏠 Trang chủ"]:
            module = DashboardModule(user_id)
            response_text = await loop.run_in_executor(None, module.run)
            await update.message.reply_html(response_text, reply_markup=self.get_menu("HOME"))

        # 2. Module Chứng Khoán
        elif text == "📊 Chứng Khoán":
            module = StockModule(user_id)
            response_text = await loop.run_in_executor(None, module.run)
            await update.message.reply_html(response_text, reply_markup=self.get_menu("STOCK"))

        # 3. Báo cáo nhóm (Phân tích tỉ trọng)
        elif text == "📈 Báo cáo nhóm":
            module = StockModule(user_id)
            # Truyền tham số mode="ANALYZE" để gọi đúng logic phân tích
            response_text = await loop.run_in_executor(None, module.run, "ANALYZE")
            await update.message.reply_html(response_text, reply_markup=self.get_menu("STOCK"))

        # 4. Các nút hướng dẫn nhanh
        elif text == "➕ Giao dịch":
            guide = "📝 <b>Lệnh mẫu:</b>\n• Stock: <code>s HPG 1000 28.5</code>\n• Crypto: <code>c BTC 0.1 50000</code>"
            await update.message.reply_html(guide, reply_markup=self.get_menu("STOCK"))
            
        elif text == "🔄 Cập nhật giá":
            await update.message.reply_html("🔍 Đang đồng bộ giá thị trường...", reply_markup=self.get_menu("STOCK"))

        # 5. Xử lý Parser cho các lệnh giao dịch thủ công
        else:
            p = CommandParser.parse_transaction(text)
            if p:
                # Thực thi ghi DB trong luồng riêng (Non-blocking)
                success, msg = await loop.run_in_executor(
                    None, 
                    repo.save_transaction, 
                    user_id, p['ticker'], p['asset_type'], p['qty'], p['price'], p['total_val'], p['action']
                )
                await update.message.reply_html(f"✅ Ghi nhận: {text.upper()}" if success else msg)

    def _register_handlers(self):
        """Đăng ký các Handler cho Bot"""
        # Sửa lỗi SyntaxError dòng 76 bằng cách tách hàm lambda và đóng chuỗi chuẩn xác
        start_handler = CommandHandler('start', self.start_command)
        message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        
        self.app.add_handler(start_handler)
        self.app.add_handler(message_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Hàm xử lý lệnh /start"""
        await update.message.reply_text("Sẵn sàng!", reply_markup=self.get_menu("HOME"))

    def run(self):
        """Khởi động Polling"""
        print("🤖 Bot Tài chính V2.0 đang khởi chạy...")
        self.app.run_polling()

# Khởi tạo instance duy nhất
bot_app = FinanceBot()
