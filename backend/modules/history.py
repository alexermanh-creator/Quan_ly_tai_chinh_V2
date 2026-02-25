# backend/modules/history.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.database.repository import Repository
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class HistoryModule(BaseModule):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.repo = Repository()
        self.items_per_page = 10

    def format_currency(self, value):
        abs_val = abs(value)
        if abs_val >= 10**6:
            return f"{value / 10**6:,.1f} triệu"
        return f"{value:,.0f}đ"

    def run(self, page=0, asset_type=None, search_query=None):
        """📜 HIỂN THỊ DANH SÁCH GIAO DỊCH"""
        offset = page * self.items_per_page
        transactions = self.repo.get_latest_transactions(
            user_id=self.user_id,
            limit=self.items_per_page,
            offset=offset,
            asset_type=asset_type,
            search_query=search_query
        )

        if not transactions and page == 0:
            return "📜 <b>LỊCH SỬ GIAO DỊCH</b>\n\nChưa có dữ liệu giao dịch nào.", None

        # --- 1. Header & Thống kê nhanh ---
        title = "📜 <b>LỊCH SỬ GIAO DỊCH</b>"
        if asset_type: title = f"📜 <b>LỊCH SỬ: {asset_type}</b>"
        if search_query: title = f"🔍 <b>TÌM KIẾM: {search_query.upper()}</b>"

        lines = [title, "━━━━━━━━━━━━━━━━━━━"]
        
        # --- 2. Danh sách giao dịch ---
        current_date = ""
        for trx in transactions:
            date_str = trx['date'].split()[0]
            if date_str != current_date:
                lines.append(f"📅 <b>{date_str}</b>")
                current_date = date_str
            
            icon = "🟢" if trx['type'] in ['BUY', 'IN', 'DEPOSIT'] else "🔴"
            val_str = self.format_currency(trx['total_value'])
            
            # Deep Link: Khi bấm vào ID sẽ gọi hàm xem chi tiết
            line = (
                f"{icon} <b>{trx['type']} — {trx['ticker']}</b>\n"
                f"SL: {trx['qty']} | Giá: {trx['price']:,.2f}\n"
                f"Tổng: <b>{val_str}</b> | Sửa: /view_{trx['id']}\n"
                f"────────────"
            )
            lines.append(line)

        # --- 3. Điều hướng Phân trang (Inline Buttons) ---
        keyboard = []
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"hist_page_{page-1}_{asset_type or 'ALL'}"))
        
        nav_buttons.append(InlineKeyboardButton(f"Trang {page + 1}", callback_data="none"))
        
        if len(transactions) >= self.items_per_page:
            nav_buttons.append(InlineKeyboardButton("Sau ➡️", callback_data=f"hist_page_{page+1}_{asset_type or 'ALL'}"))
        
        keyboard.append(nav_buttons)
        
        # Nút lọc nhanh
        keyboard.append([
            InlineKeyboardButton("📊 Stock", callback_data="hist_filter_STOCK"),
            InlineKeyboardButton("🪙 Crypto", callback_data="hist_filter_CRYPTO"),
            InlineKeyboardButton("💵 Tiền", callback_data="hist_filter_CASH")
        ])
        keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="go_home")])

        return "\n".join(lines), InlineKeyboardMarkup(keyboard)

    def get_detail_view(self, trx_id):
        """📄 CHI TIẾT GIAO DỊCH ĐỂ XÁC NHẬN XÓA/SỬA"""
        trx = self.repo.get_transaction_by_id(trx_id)
        if not trx: return "❌ Không tìm thấy giao dịch này.", None

        text = (
            f"📄 <b>CHI TIẾT GIAO DỊCH #{trx['id']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔸 Mã: <b>{trx['ticker']}</b> ({trx['asset_type']})\n"
            f"🔸 Loại: <b>{trx['type']}</b>\n"
            f"🔸 Số lượng: {trx['qty']}\n"
            f"🔸 Giá: {trx['price']:,.2f}\n"
            f"🔸 Tổng: <b>{self.format_currency(trx['total_value'])}</b>\n"
            f"📅 Ngày: {trx['date']}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <i>CEO muốn thực hiện thao tác gì?</i>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Sửa số lượng", callback_data=f"edit_qty_{trx_id}"),
             InlineKeyboardButton("✏️ Sửa giá", callback_data=f"edit_price_{trx_id}")],
            [InlineKeyboardButton("❌ XÓA GIAO DỊCH", callback_data=f"confirm_delete_{trx_id}")],
            [InlineKeyboardButton("🏠 Home", callback_data="go_home")]
        ])
        
        return text, keyboard
