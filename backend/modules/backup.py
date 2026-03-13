# backend/modules/backup.py
import os
import time
import threading
import shutil
from datetime import datetime
from backend.modules.settings import SettingsModule

class BackupModule:
    def __init__(self, bot, db_path):
        self.bot = bot
        self.db_path = db_path
        self.settings = SettingsModule()
        self.interval_seconds = 43200  # 12 tiếng

    def create_backup_file(self):
        if not os.path.exists(self.db_path):
            return None, None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_v3_{timestamp}.db"
        
        try:
            shutil.copy2(self.db_path, backup_filename)
            return backup_filename, timestamp
        except Exception as e:
            print(f"[Backup Error] Không thể copy db: {e}")
            return None, None

    def send_backup_to_user(self, chat_id, manual=False):
        backup_file, timestamp = self.create_backup_file()
        if not backup_file:
            if manual:
                self.bot.send_message(chat_id, "❌ Lỗi: Không tìm thấy file Database để sao lưu!")
            return
        
        try:
            with open(backup_file, 'rb') as f:
                if manual:
                    caption = f"📦 **BACKUP SỔ SÁCH THỦ CÔNG**\n⏱️ {timestamp}\n\n✅ File `.db` này chứa toàn bộ lịch sử giao dịch và cấu hình của Sếp."
                else:
                    caption = f"🛡️ **AUTO-BACKUP HỆ THỐNG (12H/LẦN)**\n⏱️ {timestamp}\n\n💡 Đây là bản sao lưu tự động mới nhất. Server có sự cố thì Sếp up lại file này là xong!"
                
                self.bot.send_document(chat_id, f, caption=caption, parse_mode="Markdown")
        except Exception as e:
            if manual:
                self.bot.send_message(chat_id, f"❌ Lỗi gửi file backup: {str(e)}")
            print(f"[Backup Error] Lỗi gửi file: {e}")
        finally:
            if os.path.exists(backup_file):
                os.remove(backup_file) # Gửi xong dọn dẹp luôn cho sạch Server

    def _auto_backup_worker(self):
        while True:
            time.sleep(self.interval_seconds)
            admin_id = self.settings.get_setting('admin_chat_id')
            if admin_id:
                self.send_backup_to_user(admin_id, manual=False)

    def start_auto_backup(self):
        thread = threading.Thread(target=self._auto_backup_worker, daemon=True)
        thread.start()
        print("🛡️ Module Auto-Backup (Telegram) đã kích hoạt (12h/lần).")
