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

    def get_stats(self, asset_type=None):
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
            
        deposit = results.get('DEPOSIT', 0) + results.get('IN', 0)
        withdraw = results.get('WITHDRAW', 0) + results.get('OUT', 0)
        return deposit, withdraw

    def run(self, page=0, asset_type=None, search_query=None):
        offset = page * self.items_per_page
        transactions = self.repo.get_latest_transactions(
            user_id=self.user_id, limit=self.items_per_page,
            offset=offset, asset_type=asset_type, search_query=search_query
        )
        dep, wit = self.get_stats(asset_type)
        
        title = "📜 <b>LỊCH SỬ GIAO DỊCH</b>"
        if asset_type: title = f"📜 <b>LỊCH SỬ: {asset_type}</b>"
        if search_query: title = f"🔍 <b>TÌM KIẾM: {search_query.upper()}</b>"

        lines = [title, f"📊 Tổng nạp: <b>{self.format_currency(dep)}</b>", f"📊 Tổng rút: <b>{self.format_currency(wit)}</b>", "━━━━━━━━━━━━━━━━━━━"]
        if not transactions: lines.append("<i>Chưa có dữ liệu giao dịch.</i>")
        
        current_date = ""
        for trx in transactions:
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

        keyboard = []
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"hist_page_{page-1}_{asset_type or 'ALL'}"))
        nav.append(InlineKeyboardButton(f"Trang {page + 1}", callback_data="none"))
        if len(transactions) >= self.items_per_page:
            nav.append(InlineKeyboardButton("Sau ➡️", callback_data=f"hist_page_{page+1}_{asset_type or 'ALL'}"))
        if nav: keyboard.append(nav)

        keyboard.append([InlineKeyboardButton("📊 Stock", callback_data="hist_filter_STOCK"), InlineKeyboardButton("🪙 Crypto", callback_data="hist_filter_CRYPTO"), InlineKeyboardButton("💵 Tiền", callback_data="hist_filter_CASH")])
        keyboard.append([InlineKeyboardButton("🔍 Tìm kiếm", callback_data="hist_search_prompt"), InlineKeyboardButton("🏠 Home", callback_data="go_home")])

        return "\n".join(lines), InlineKeyboardMarkup(keyboard)

    def get_detail_view(self, trx_id):
        trx = self.repo.get_transaction_by_id(trx_id)
        if not trx: return "❌ Không tìm thấy giao dịch.", None

        text = (f"📄 <b>CHI TIẾT GIAO DỊCH #{trx['id']}</b>\n━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Loại: {trx['type']} | Mã: {trx['ticker']}\n🔹 SL: {trx['qty']} | Giá: {trx['price']:,.0f}\n"
                f"💰 Tổng: <b>{self.format_currency(trx['total_value'])}</b>\n📅 Ngày: {trx['date']}\n"
                f"━━━━━━━━━━━━━━━━━━━\n✏️ <b>CEO MUỐN SỬA HAY XÓA?</b>")
        
        # BỔ SUNG NÚT SỬA NGÀY
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Sửa số lượng", callback_data=f"edit_qty_{trx_id}"),
             InlineKeyboardButton("✏️ Sửa giá", callback_data=f"edit_price_{trx_id}")],
            [InlineKeyboardButton("📅 Sửa ngày", callback_data=f"edit_date_{trx_id}"),
             InlineKeyboardButton("❌ XÓA GIAO DỊCH", callback_data=f"confirm_delete_{trx_id}")],
            [InlineKeyboardButton("🏠 Home", callback_data="go_home")]
        ])
        return text, kb
