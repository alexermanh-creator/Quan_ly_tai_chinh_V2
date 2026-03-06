# backend/modules/history.py
import math
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.database.repository import DatabaseRepo

class HistoryModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def format_money(self, amount):
        if not amount or amount == 0: return "0 đ"
        if abs(amount) >= 1000000: return f"{amount / 1000000:,.1f} triệu"
        return f"{amount:,.0f} đ"

    def get_history_ui(self, page=1, filter_type='ALL', symbol=None):
        limit = 5
        offset = (page - 1) * limit
        
        # Tính toán phân trang
        total_items = self.db.get_transactions_count(filter_type, symbol)
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
        if page > total_pages: page = total_pages
        if page < 1: page = 1
        
        transactions = self.db.get_transactions_paginated(limit, offset, filter_type, symbol)
        
        # Đặt Tiêu đề
        header = "TỔNG HỢP"
        if symbol: header = f"MÃ {symbol.upper()}"
        elif filter_type == 'CASH': header = "NẠP/RÚT VỐN (CASH)"
        elif filter_type == 'STOCK': header = "CHỨNG KHOÁN"
        elif filter_type == 'CRYPTO': header = "CRYPTO"
        elif filter_type == 'OTHER': header = "TÀI SẢN KHÁC"

        msg = f"📜 **LỊCH SỬ GIAO DỊCH: {header} (Trang {page}/{total_pages})**\n━━━━━━━━━━━━━━━━━━━\n"
        
        if not transactions:
            msg += "Chưa có giao dịch nào.\n━━━━━━━━━━━━━━━━━━━\n"
        else:
            for t in transactions:
                t_id = t['id']
                t_type = t['type']
                amt = t['amount'] or 0
                sym = t.get('symbol', None)
                qty = t.get('quantity', None)
                price = t.get('price', None)
                r_pl = t.get('realized_pl', None)
                note = t.get('note', '')
                
                msg += f"🔹 **ID: #{t_id}** | `{t_type}`\n"
                
                # Chi tiết Mua/Bán (nếu có)
                if sym:
                    msg += f"💎 **{sym}** "
                    if qty and price: 
                        msg += f"| SL: {qty:,.2f} | Giá: {price:,.2f}\n"
                    else: 
                        msg += "\n"
                
                # Số tiền biến động
                if amt != 0:
                    sign = "+" if amt > 0 else ""
                    msg += f"💰 Giao dịch: {sign}{self.format_money(amt)}\n"
                
                # Lãi/Lỗ chốt
                if r_pl:
                    icon = "🟢" if r_pl >= 0 else "🔴"
                    sign = "+" if r_pl > 0 else ""
                    msg += f"💵 Lãi chốt: {sign}{self.format_money(r_pl)} {icon}\n"
                
                # Ghi chú
                if note:
                    msg += f"📝 {note}\n"
                    
                msg += "────────────\n"
            msg += "━━━━━━━━━━━━━━━━━━━\n"

        # Vẽ Bàn phím điều hướng (Inline Keyboard)
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Row 1: Phân trang
        btn_prev = InlineKeyboardButton("⬅️ Trước", callback_data=f"his_p_{page-1}_{filter_type}_{symbol or 'NONE'}")
        btn_next = InlineKeyboardButton("Sau ➡️", callback_data=f"his_p_{page+1}_{filter_type}_{symbol or 'NONE'}")
        if page == 1: btn_prev = InlineKeyboardButton("🚫", callback_data="ignore")
        if page == total_pages: btn_next = InlineKeyboardButton("🚫", callback_data="ignore")
        markup.row(btn_prev, btn_next)

        # Row 2 & 3: Lọc dữ liệu
        if not symbol:
            markup.add(
                InlineKeyboardButton("💵 Nạp/Rút", callback_data="his_f_CASH"),
                InlineKeyboardButton("📊 Chứng khoán", callback_data="his_f_STOCK"),
                InlineKeyboardButton("🪙 Crypto", callback_data="his_f_CRYPTO"),
                InlineKeyboardButton("🥇 Tài sản Khác", callback_data="his_f_OTHER"),
                InlineKeyboardButton("🔍 Tìm kiếm", callback_data="his_search"),
                InlineKeyboardButton("🔄 Xem Tất Cả", callback_data="his_f_ALL")
            )
        else:
            markup.add(InlineKeyboardButton("🔙 Quay lại Tất cả", callback_data="his_f_ALL"))

        return msg, markup
