# backend/interface.py
from backend.database.repository import repo

class BaseModule:
    def __init__(self, user_id):
        self.user_id = user_id
        # Sử dụng instance repo duy nhất đã được khởi tạo
        self.repo = repo

    def run(self):
        """Các module con sẽ viết đè hàm này"""
        raise NotImplementedError("Module con phải triển khai hàm run()")
