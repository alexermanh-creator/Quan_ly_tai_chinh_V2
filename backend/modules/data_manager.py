# backend/modules/data_manager.py
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.services.import_service import ImportService

class DataManagerModule:
    def __init__(self):
        self.import_service = ImportService()

    def get_menu_ui(self):
        msg = (
            "💾 **QUẢN LÝ DỮ LIỆU HỆ THỐNG**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Kéo thả file `.json` vào khung chat này để **Import / Chốt số đầu kỳ**.\n"
            "Dữ liệu của Sếp sẽ tự động cân bằng Lãi/Lỗ quá khứ."
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🗑 Xóa trắng dữ liệu (Reset)", callback_data="data_reset"))
        return msg, markup

    def handle_document(self, bot, message):
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            json_data = json.loads(downloaded_file.decode('utf-8'))
            
            success, response_msg = self.import_service.process_import_file(json_data)
            bot.reply_to(message, response_msg)
        except Exception as e:
            bot.reply_to(message, f"❌ File không hợp lệ hoặc lỗi định dạng: {str(e)}")
