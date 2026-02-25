# main.py
import os
import re
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from backend.core.parser import CommandParser
from backend.database.repository import Repository
from backend.database.db_manager import db
from backend.modules.dashboard import DashboardModule
from backend.modules.stock import StockModule
from backend.modules.crypto import CryptoModule 

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))
repo = Repository()

# --- HỆ THỐNG MENU ---

def get_ceo_menu():
    """Menu chính khi ở ngoài Dashboard tổng"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("💼 Tài sản của bạn")],
        [KeyboardButton("📊 Chứng Khoán"), KeyboardButton("🪙 Crypto")],
        [KeyboardButton("🥇 Tài sản khác"), KeyboardButton("📜 Lịch sử")],
        [KeyboardButton("📊 Báo cáo"), KeyboardButton("🤖 AI Chat")],
        [KeyboardButton("⚙️ Cài đặt"), KeyboardButton("📥 EXPORT/IMPORT")],
        [KeyboardButton("📸 SNAPSHOT"), KeyboardButton("🔄 Làm mới")]
    ], resize_keyboard=True)

def get_stock_menu():
    """Menu chuyên biệt khi vào mục Chứng Khoán"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Giao dịch"), KeyboardButton("🔄 Cập nhật giá")],
        [KeyboardButton("📈 Báo cáo nhóm"), KeyboardButton("❌ Xóa mã")],
        [KeyboardButton("🏠 Trang chủ")]
    ], resize_keyboard=True)

def get_crypto_menu():
    """2. Menu Crypto đầy đủ tính năng như Stock (ĐÃ CẬP NHẬT)"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Giao dịch Crypto"), KeyboardButton("🔄 Cập nhật giá")],
        [KeyboardButton("📈 Báo cáo Crypto"), KeyboardButton("❌ Xóa mã")],
        [KeyboardButton("🏠 Trang chủ")]
    ], resize_keyboard=True)

# --- XỬ LÝ MESSAGE ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(
        "🌟 <b>Hệ điều hành tài chính v2.0</b>\nẤn biểu tượng (::) để quản lý tài sản.",
        reply_markup=get_ceo_menu(),
        parse_mode=constants.ParseMode.HTML
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text
    user_id = update.effective_user.id

    # --- NHÓM 1: ƯU TIÊN CÁC NÚT BẤM (EXACT MATCH) ---
    
    if text == "📊 Chứng Khoán":
        try:
            stock_mod = StockModule(user_id)
            await update.message.reply_html(stock_mod.run(), reply_markup=get_stock_menu())
            context.user_data['last_module'] = 'STOCK' 
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi Stock Module: {e}")
        return

    if text == "🪙 Crypto": 
        try:
            crypto_mod = CryptoModule(user_id)
            await update.message.reply_html(crypto_mod.run(), reply_markup=get_crypto_menu())
            context.user_data['last_module'] = 'CRYPTO'
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi Crypto Module: {e}")
        return

    if text in ["💼 Tài sản của bạn", "🏠 Trang chủ"]:
        try:
            dash = DashboardModule(user_id)
            await update.message.reply_html(dash.run(), reply_markup=get_ceo_menu())
            context.user_data['last_module'] = None
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi Dashboard: {e}")
        return

    if text in ["📈 Báo cáo nhóm", "📈 Báo cáo Crypto"]: 
        try:
            current_mod = context.user_data.get('last_module')
            mod = CryptoModule(user_id) if current_mod == 'CRYPTO' else StockModule(user_id)
            await update.message.reply_html(mod.get_group_report())
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi Báo cáo: {e}")
        return

    if text == "➕ Giao dịch":
        await update.message.reply_html("➕ <b>GIAO DỊCH STOCK:</b>\n<code>S [Mã] [SL] [Giá]</code>\nVí dụ: <code>S HPG 1000 28.5</code>")
        return

    if text == "➕ Giao dịch Crypto": # THÊM NÚT HƯỚNG DẪN CRYPTO
        await update.message.reply_html("🪙 <b>GIAO DỊCH CRYPTO:</b>\n<code>C [Mã] [SL] [Giá USD]</code>\nVí dụ: <code>C BTC 0.1 65000</code>")
        return
    
    if text == "🔄 Cập nhật giá":
        await update.message.reply_html("🔄 <b>CẬP NHẬT GIÁ:</b>\n<code>gia [Mã] [Giá mới]</code>")
        return

    if text == "❌ Xóa mã": # THÊM NÚT HƯỚNG DẪN XÓA
        await update.message.reply_html("🗑 <b>XÓA MÃ:</b> Gõ <code>xoa [Mã]</code> để xóa sạch lịch sử.\nVí dụ: <code>xoa VNM</code> hoặc <code>xoa BTC</code>")
        return

    if text == "🔄 Làm mới":
        try:
            dash = DashboardModule(user_id)
            await update.message.reply_html(f"🔄 <b>Dữ liệu đã được làm mới:</b>\n\n{dash.run()}")
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi Refresh: {e}")
        return

    # --- NHÓM 2: XỬ LÝ LỆNH GÕ (PREFIX MATCH) ---

    if text.lower().startswith("xoa "):
        parts = text.split()
        if len(parts) == 2:
            ticker_del = parts[1].upper()
            with db.get_connection() as conn:
                conn.execute("DELETE FROM transactions WHERE ticker = ?", (ticker_del,))
                conn.execute("DELETE FROM manual_prices WHERE ticker = ?", (ticker_del,))
                conn.commit()
            await update.message.reply_html(f"🗑 Đã xóa toàn bộ dữ liệu mã <b>{ticker_del}</b>.")
        return

    if text.lower().startswith("gia "):
        match = re.match(r'^gia\s+([a-z0-9]+)\s+([\d\.,]+)$', text.lower().strip())
        if match:
            ticker = match.group(1).upper()
            price = float(match.group(2).replace(',', '.'))
            with db.get_connection() as conn:
                conn.execute('''
                    INSERT INTO manual_prices (ticker, current_price, updated_at)
                    VALUES (?, ?, datetime('now', 'localtime'))
                    ON CONFLICT(ticker) DO UPDATE SET 
                        current_price=excluded.current_price, 
                        updated_at=excluded.updated_at
                ''', (ticker, price))
                conn.commit()
            await update.message.reply_html(f"✅ Đã cập nhật giá mới cho <b>{ticker}</b>: <code>{price}</code>")
        return

    # --- NHÓM 3: PARSER CHO GIAO DỊCH (S, C, nap, rut) ---
    parsed_data = CommandParser.parse_transaction(text)
    if parsed_data:
        try:
            repo.save_transaction(
                user_id=user_id,
                ticker=parsed_data['ticker'],
                asset_type=parsed_data['asset_type'],
                qty=parsed_data['qty'],
                price=parsed_data['price'],
                total_value=parsed_data['total_val'],
                type=parsed_data['action']
            )
            val_format = f"{parsed_data['total_val']:,.0f}".replace(',', '.')
            await update.message.reply_html(
                f"✅ <b>Ghi nhận thành công:</b>\n"
                f"📝 Lệnh: <code>{text.upper()}</code>\n"
                f"💰 Giá trị (VNĐ): <b>{val_format}đ</b>"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi Database: {e}")
    else:
        if len(text.split()) > 1:
            await update.message.reply_text("❓ Lệnh không hợp lệ. Hãy kiểm tra lại cú pháp.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 Bot Finance v2.0 đang polling...")
    application.run_polling(drop_pending_updates=True)
