# Telegram/bot_client.py
import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from dotenv import load_dotenv

# Import database instance đã hợp nhất ở bước trước
from backend.database.db_manager import db

# Cấu hình log để dễ debug
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

class FinanceBot:
    def __init__(self):
        if not TOKEN:
            raise ValueError("❌ Không tìm thấy TELEGRAM_BOT_TOKEN trong file .env")
        
        self.application = ApplicationBuilder().token(TOKEN).build()
        self._register_handlers()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Xử lý lệnh /start - Chào mừng và lưu user nếu cần"""
        user = update.effective_user
        welcome_text = (
            f"Xin chào {user.first_name}! 👋\n\n"
            "Tôi là Trợ lý Quản lý Tài chính cá nhân của bạn.\n"
            "Tôi có thể giúp bạn theo dõi: \n"
            "📈 Chứng khoán\n"
            "💰 Crypto\n"
            "💵 Tiền mặt\n\n"
            "Gõ /help để xem danh sách các lệnh."
        )
        
        # Ghi log kết nối vào database để test (Giai đoạn 1)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Bạn có thể thêm logic lưu thông tin user vào bảng settings hoặc bảng riêng ở đây
            pass

        await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Hiển thị hướng dẫn"""
        help_text = (
            "📌 **Danh sách lệnh:**\n"
            "/start - Khởi động bot\n"
            "/balance - Xem số dư tài sản (Sẽ cập nhật ở Giai đoạn 2)\n"
            "/add [mã] [số lượng] [giá] - Thêm giao dịch"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text, parse_mode='Markdown')

    def _register_handlers(self):
        """Đăng ký các lệnh với Telegram"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))

    def run(self):
        """Chạy Bot"""
        print("🚀 Bot đang khởi động...")
        self.application.run_polling()

# Khởi tạo instance của Bot
bot_app = FinanceBot()
