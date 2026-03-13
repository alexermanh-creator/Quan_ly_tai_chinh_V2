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
        self.interval_seconds = 43200  # 12 tiếng (12 * 60 * 60)

    def create_backup_file(self):
        if not os.path.exists(self.db_path):
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_v3_{timestamp}.db"
        
        try:
            shutil.copy2(self.db_path, backup_filename)
            return backup_filename
        except Exception as e:
            print(f"[Backup Error] Không thể copy db: {e}")
            return None

    def send_backup_to_user(self, chat_id, manual=False):
        backup_file = self.create_backup_file()
        if not backup_file:
            if manual:
                self.bot.send_message(chat_id, "❌ Lỗi: Không tìm thấy file Database để sao lưu!")
            return
        
        try:
            with open(backup_file, 'rb') as f:
                if manual:
                    caption = "📦 **BACKUP SỔ SÁCH THỦ CÔNG**\n\n✅ File `.db` này chứa toàn bộ lịch sử giao dịch và cấu hình."
                else:
                    caption = "🛡️ **AUTO-BACKUP HỆ THỐNG (12H/LẦN)**\n\n💡 Đây là bản sao lưu tự động mới nhất. Giữ file này an toàn, server có sự cố thì up lại file này là xong!"
                
                self.bot.send_document(chat_id, f, caption=caption, parse_mode="Markdown")
        except Exception as e:
            if manual:
                self.bot.send_message(chat_id, f"❌ Lỗi gửi file backup: {str(e)}")
            print(f"[Backup Error] Lỗi gửi file: {e}")
        finally:
            if os.path.exists(backup_file):
                os.remove(backup_file)

    def _auto_backup_worker(self):
        while True:
            time.sleep(self.interval_seconds)
            admin_id = self.settings.get_setting('admin_chat_id')
            if admin_id:
                self.send_backup_to_user(admin_id, manual=False)

    def start_auto_backup(self):
        thread = threading.Thread(target=self._auto_backup_worker, daemon=True)
        thread.start()
        print("🛡️ Module Auto-Backup đã kích hoạt (12h/lần).")
