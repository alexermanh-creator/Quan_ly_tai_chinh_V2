# backend/interface.py
from backend.core.engine import UniversalEngine
from backend.database.repository import Repository

class BaseModule:
    def __init__(self, user_id):
        self.user_id = user_id
        # Mỗi module đều có sẵn "Kế toán trưởng" (Engine) và "Thủ kho" (Repo)
        self.engine = UniversalEngine(user_id)
        self.repo = Repository()

    def get_summary_data(self, asset_type):
        """Hàm dùng chung để lấy dữ liệu đã tính toán từ Engine"""
        return self.engine.get_portfolio(asset_type)

    def get_history(self, limit=10):
        """Hàm dùng chung để lấy lịch sử giao dịch"""
        return self.repo.get_latest_transactions(self.user_id, limit)

    def run(self):
        """Các module con sẽ viết đè (override) hàm này để hiển thị giao diện riêng"""
        raise NotImplementedError("Module con phải triển khai hàm run()")
