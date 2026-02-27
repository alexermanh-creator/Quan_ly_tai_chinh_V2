# backend/modules/history.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import repo # Sử dụng instance repo đã hợp nhất
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class HistoryModule(BaseModule):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.items_per_page = 10

    def format_currency(self, value):
        abs_val = abs(value)
        if abs_val >= 10**6:
            return f"{value / 10**6:,.1f} triệu"
        return f"{value:,.0f}đ"

    def get_stats(self, asset_type=None):
        """Thống kê nhanh dòng tiền trong lịch sử đang xem"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT type, SUM(total_value) as total FROM transactions WHERE user_id = ?"
            params = [self.user_id]
            if asset_type:
                query += " AND asset_type = ?"
                params.append(asset_type)
            query += " GROUP BY type"
            cursor.execute(query, params)
            results = {row['type']: row['total'] for row in cursor.fetchall()}
            
        # Hợp nhất các loại lệnh nạp/rút tương đương
        deposit = results.get('DEPOSIT', 0) + results.get('IN', 0) + results.get('BUY', 0)
        withdraw = results.get('WITHDRAW', 0) + results.get('OUT', 0) + results.get('SELL', 0)
        return deposit, withdraw

    def run(self, page=0, asset_type=None, search_query=None):
        """Hiển thị danh sách giao dịch phân trang"""
        offset = page * self.items_per_page
        # Sử dụng hàm get_latest_transactions từ repo
        transactions = repo.get_latest_transactions(
            user_id=self.user_id, 
            limit=self.items_per_page,
            offset=offset, 
            asset_type=asset_type, 
            search_query=search_query
        )
        dep, wit = self.get_stats(asset_type)
        
        # Tiêu đề động theo bộ lọc
        title = "📜 <b>LỊCH SỬ GIAO DỊCH</b>"
        if asset_type: title = f"📜 <b>LỊCH SỬ: {asset_type}</b>"
        if search_query: title = f"🔍 <b>TÌM KIẾM: {search_query.upper()}</b>"

        lines = [
            title, 
            f"➕ Tổng chi: <b>{self.format_currency(dep)}</b>", 
            f"➖ Tổng thu: <b>{self.format_currency(wit)}</b>", 
            "━━━━━━━━━━━━━━━━━━━"
        ]
        
        if not transactions: 
            lines.append("<i>Chưa có dữ liệu giao dịch.</i>")
        
        current_date = ""
        for trx in transactions:
            # Tách ngày để tạo tiêu đề nhóm theo ngày
            date_str = trx['date'].split()[0]
            if date_str != current_date:
                lines.append(f"📅 <b>{date_str}</b>")
                current_date = date_str
            
            icon = "🟢" if trx['type'] in ['BUY', 'IN', 'DEPOSIT'] else "🔴"
            line = (f"{icon} <b>{trx['type']} — {trx['ticker']}</b>\n"
                    f"SL: {trx['qty']} | Giá: {trx['price']:,.0f}\n"
                    f"Tổng: <b>{self.format_currency(trx['total_value'])}</b> | ✏️ /{trx['id']}\n"
                    f"────────────")
            lines.append(line)

        # Xây dựng bàn phím điều hướng (Navigation)
        keyboard = []
        nav_row = []
        if page > 0: 
            nav_row.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"hist_page_{page-1}_{asset_type or 'ALL'}"))
        
        nav_row.append(InlineKeyboardButton(f"Trang {page + 1}", callback_data="none"))
        
        if len(transactions) >= self.items_per_page:
            nav_row.append(InlineKeyboardButton("Sau ➡️", callback_data=f"hist_page_{page+1}_{asset_type or 'ALL'}"))
        
        if nav_row: keyboard.append(nav_row)

        # Các phím chức năng nhanh
        keyboard.append([
            InlineKeyboardButton("📊 Stock", callback_data="hist_filter_STOCK"), 
            InlineKeyboardButton("🪙 Crypto", callback_data="hist_filter_CRYPTO"), 
            InlineKeyboardButton("💵 Tiền", callback_data="hist_filter_CASH")
        ])
        keyboard.append([
            InlineKeyboardButton("🔍 Tìm kiếm", callback_data="hist_search_prompt"), 
            InlineKeyboardButton("🏠 Home", callback_data="go_home")
        ])

        return "\n".join(lines), InlineKeyboardMarkup(keyboard)

    def get_detail_view(self, trx_id):
        """Hiển thị chi tiết khi click vào mã /ID"""
        trx = repo.get_transaction_by_id(trx_id)
        if not trx: return "❌ Không tìm thấy giao dịch.", None

        text = (f"📄 <b>CHI TIẾT GIAO DỊCH #{trx['id']}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Loại: {trx['type']} | Mã: {trx['ticker']}\n"
                f"🔹 SL: {trx['qty']} | Giá: {trx['price']:,.0f}\n"
                f"💰 Tổng: <b>{self.format_currency(trx['total_value'])}</b>\n"
                f"📅 Ngày: {trx['date']}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"✏️ <b>CEO MUỐN SỬA HAY XÓA?</b>")
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Sửa SL", callback_data=f"edit_qty_{trx_id}"),
             InlineKeyboardButton("✏️ Sửa Giá", callback_data=f"edit_price_{trx_id}")],
            [InlineKeyboardButton("📅 Sửa Ngày", callback_data=f"edit_date_{trx_id}"),
             InlineKeyboardButton("❌ XÓA", callback_data=f"confirm_delete_{trx_id}")],
            [InlineKeyboardButton("🏠 Home", callback_data="go_home")]
        ])
        return text, kb
