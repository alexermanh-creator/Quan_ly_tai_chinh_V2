# main.py
import os
import re
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, constants, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from backend.core.parser import CommandParser
from backend.database.repository import Repository
from backend.database.db_manager import db
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.crypto import CryptoModule 
from backend.modules.history import HistoryModule

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))
repo = Repository()

# --- HỆ THỐNG MENU (GIỮ NGUYÊN 100% GỐC) ---
def get_ceo_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💼 Tài sản của bạn")],
        [KeyboardButton("📊 Chứng Khoán"), KeyboardButton("🪙 Crypto")],
        [KeyboardButton("🥇 Tài sản khác"), KeyboardButton("📜 Lịch sử")],
        [KeyboardButton("📊 Báo cáo"), KeyboardButton("🤖 AI Chat")],
        [KeyboardButton("⚙️ Cài đặt"), KeyboardButton("📥 EXPORT/IMPORT")],
        [KeyboardButton("📸 SNAPSHOT"), KeyboardButton("🔄 Làm mới")]
    ], resize_keyboard=True)

def get_stock_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Giao dịch"), KeyboardButton("🔄 Cập nhật giá")],
        [KeyboardButton("📈 Báo cáo nhóm"), KeyboardButton("❌ Xóa mã")],
        [KeyboardButton("🏠 Trang chủ")]
    ], resize_keyboard=True)

def get_crypto_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Giao dịch Crypto"), KeyboardButton("🔄 Cập nhật giá Crypto")],
        [KeyboardButton("📈 Báo cáo Crypto"), KeyboardButton("❌ Xóa mã Crypto")],
        [KeyboardButton("🏠 Trang chủ")]
    ], resize_keyboard=True)

# --- XỬ LÝ CALLBACK (CHO NÚT BẤM INLINE) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    hist = HistoryModule(user_id)

    if data.startswith("hist_page_") or data.startswith("hist_filter_"):
        parts = data.split("_")
        page = int(parts[2]) if "page" in data else 0
        a_type = parts[-1] if parts[-1] != 'ALL' else None
        text, kb = hist.run(page=page, asset_type=a_type)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=constants.ParseMode.HTML)

    elif data == "go_home":
        dash = DashboardModule(user_id)
        await query.message.reply_html(dash.run(), reply_markup=get_ceo_menu())

    elif data.startswith("confirm_delete_"):
        trx_id = data.split("_")[-1]
        text = f"⚠️ <b>XÁC NHẬN XÓA?</b>\n\nBạn chắc chắn muốn xóa vĩnh viễn giao dịch #{trx_id}?"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ CÓ, XÓA NGAY", callback_data=f"execute_delete_{trx_id}")],
            [InlineKeyboardButton("❌ HỦY", callback_data=f"go_home")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode=constants.ParseMode.HTML)

    elif data.startswith("execute_delete_"):
        trx_id = data.split("_")[-1]
        if repo.delete_transaction(trx_id):
            await query.edit_message_text(f"✅ Đã xóa thành công giao dịch #{trx_id}!")
        else:
            await query.edit_message_text("❌ Lỗi: Không thể xóa.")

# --- XỬ LÝ MESSAGE ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("🌟 <b>Hệ điều hành tài chính v2.0</b>", reply_markup=get_ceo_menu(), parse_mode=constants.ParseMode.HTML)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text
    user_id = update.effective_user.id

    # --- ĐĂNG KÝ LỆNH /VIEW ĐỂ NÚT ✏️ PHẢN HỒI ---
    if text.startswith("/view_"):
        trx_id = text.split("_")[1]
        hist = HistoryModule(user_id)
        content, kb = hist.get_detail_view(trx_id)
        await update.message.reply_html(content, reply_markup=kb)
        return

    # --- NHÓM 1: ƯU TIÊN NÚT BẤM (EXACT MATCH) ---
    if text == "📊 Chứng Khoán":
        await update.message.reply_html(StockModule(user_id).run(), reply_markup=get_stock_menu()); return
    if text == "🪙 Crypto":
        await update.message.reply_html(CryptoModule(user_id).run(), reply_markup=get_crypto_menu()); return
    if text in ["💼 Tài sản của bạn", "🏠 Trang chủ"]:
        await update.message.reply_html(DashboardModule(user_id).run(), reply_markup=get_ceo_menu()); return
    if text == "📜 Lịch sử":
        content, kb = HistoryModule(user_id).run()
        await update.message.reply_html(content, reply_markup=kb); return
    if text in ["📈 Báo cáo nhóm", "📈 Báo cáo Crypto"]:
        mod = CryptoModule(user_id) if "Crypto" in text else StockModule(user_id)
        await update.message.reply_html(mod.get_group_report()); return
    if text in ["➕ Giao dịch", "➕ Giao dịch Crypto"]:
        p = "S" if text == "➕ Giao dịch" else "C"
        await update.message.reply_html(f"➕ <b>GIAO DỊCH {p}:</b>\n<code>{p} [Mã] [SL] [Giá]</code>"); return
    if text in ["🔄 Cập nhật giá", "🔄 Cập nhật giá Crypto"]:
        await update.message.reply_html("🔄 <b>CẬP NHẬT GIÁ:</b>\n<code>gia [Mã] [Giá mới]</code>"); return
    if text in ["❌ Xóa mã", "❌ Xóa mã Crypto"]:
        await update.message.reply_html("🗑 <b>XÓA MÃ:</b> Gõ <code>xoa [Mã]</code>"); return
    if text == "🔄 Làm mới":
        await update.message.reply_html(f"🔄 <b>Làm mới:</b>\n\n{DashboardModule(user_id).run()}"); return

    # --- NHÓM 2: LỆNH GÕ (PREFIX) & TÌM KIẾM ---
    if text.lower().startswith("xoa "):
        ticker = text.split()[1].upper()
        with db.get_connection() as conn:
            conn.execute("DELETE FROM transactions WHERE ticker = ?", (ticker,))
            conn.execute("DELETE FROM manual_prices WHERE ticker = ?", (ticker,))
        await update.message.reply_html(f"🗑 Đã xóa mã <b>{ticker}</b>."); return

    if text.lower().startswith("gia "):
        match = re.match(r'^gia\s+([a-z0-9]+)\s+([\d\.,]+)$', text.lower().strip())
        if match:
            t, p = match.group(1).upper(), float(match.group(2).replace(',', '.'))
            with db.get_connection() as conn:
                conn.execute("INSERT INTO manual_prices (ticker, current_price, updated_at) VALUES (?, ?, datetime('now', 'localtime')) ON CONFLICT(ticker) DO UPDATE SET current_price=excluded.current_price, updated_at=excluded.updated_at", (t, p))
            await update.message.reply_html(f"✅ Đã cập nhật <b>{t}</b>: <code>{p}</code>"); return

    # TÌM KIẾM NHANH (vd: vpb)
    if len(text.split()) == 1 and text.isalpha() and text.lower() not in ["gia", "xoa", "nap", "rut"]:
        content, kb = HistoryModule(user_id).run(search_query=text)
        await update.message.reply_html(content, reply_markup=kb); return

    # PARSER GIAO DỊCH
    parsed = CommandParser.parse_transaction(text)
    if parsed:
        repo.save_transaction(user_id, parsed['ticker'], parsed['asset_type'], parsed['qty'], parsed['price'], parsed['total_val'], parsed['action'])
        await update.message.reply_html(f"✅ <b>Ghi nhận:</b> <code>{text.upper()}</code>\n💰: <b>{parsed['total_val']:,.0f}đ</b>"); return

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("🚀 Bot Finance v2.0 - System Online."); application.run_polling(drop_pending_updates=True)
