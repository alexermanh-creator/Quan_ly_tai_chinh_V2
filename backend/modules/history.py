# backend/modules/history.py
import math
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency  # Đã import hàm chuẩn từ utils

class HistoryModule:
    def __init__(self):
        self.db = DatabaseRepo()

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
                
                # Chi tiết Mua/Bán
                if sym:
                    msg += f"💎 **{sym}** "
                    if qty and price: 
                        msg += f"| SL: {qty:,.2f} | Giá: {price:,.2f}\n"
                    else: 
                        msg += "\n"
                
                # Số tiền biến động (Dùng format_currency chuẩn)
                if amt != 0:
                    sign = "+" if amt > 0 else ""
                    msg += f"💰 Giao dịch: {sign}{format_currency(amt)}\n"
                
                # Lãi/Lỗ chốt (Dùng format_currency chuẩn)
                if r_pl:
                    icon = "🟢" if r_pl >= 0 else "🔴"
                    sign = "+" if r_pl > 0 else ""
                    msg += f"💵 Lãi chốt: {sign}{format_currency(r_pl)} {icon}\n"
                
                if note: msg += f"📝 {note}\n"
                msg += "────────────\n"
            msg += "━━━━━━━━━━━━━━━━━━━\n"

        # TỰ ĐỘNG ẨN MÀN HÌNH NẾU CHỈ CÓ 1 TRANG
        markup = None
        if total_pages > 1:
            markup = InlineKeyboardMarkup(row_width=2)
            btn_prev = InlineKeyboardButton("⬅️ Trước", callback_data=f"his_p_{page-1}_{filter_type}_{symbol or 'NONE'}")
            btn_next = InlineKeyboardButton("Sau ➡️", callback_data=f"his_p_{page+1}_{filter_type}_{symbol or 'NONE'}")
            if page == 1: btn_prev = InlineKeyboardButton("🚫", callback_data="ignore")
            if page == total_pages: btn_next = InlineKeyboardButton("🚫", callback_data="ignore")
            markup.row(btn_prev, btn_next)

        return msg, markup
