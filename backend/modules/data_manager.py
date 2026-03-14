# backend/modules/data_manager.py
import shutil
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.database.repository import DatabaseRepo

class DataManagerModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_menu_ui(self):
        msg = (
            "💾 **QUẢN LÝ DỮ LIỆU HỆ THỐNG**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "1. Kéo thả file `.json` để Import sổ sách.\n"
            "2. Kéo thả file `.db` để khôi phục toàn bộ Database cũ."
        )
        markup = InlineKeyboardMarkup()
        return msg, markup

    def handle_document(self, bot, message):
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Xử lý file .db
            if message.document.file_name.endswith('.db'):
                temp_path = "temp_restore.db"
                with open(temp_path, 'wb') as f:
                    f.write(downloaded_file)
                
                self.db.replace_db(temp_path)
                bot.reply_to(message, "✅ **ĐÃ KHÔI PHỤC DATABASE THÀNH CÔNG!**\nBot sẽ tự khởi động lại để cập nhật sổ sách.")
                import os
                os.remove(temp_path)
                os._exit(0) # Thoát để service tự khởi động lại với DB mới
                
            # Xử lý file .json (như cũ)
            else:
                bot.reply_to(message, "⏳ Đang phân tích sổ sách tài chính...")
                # ... (giữ nguyên logic json cũ của sếp)
        except Exception as e:
            bot.reply_to(message, f"❌ Lỗi khôi phục: {str(e)}")