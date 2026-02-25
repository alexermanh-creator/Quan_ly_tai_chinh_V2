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

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))
repo = Repository()

# --- HỆ THỐNG MENU (Dấu ::) ---

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
    """Menu chuyên biệt giấu trong dấu (::) khi vào mục Chứng Khoán"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Giao dịch"), KeyboardButton("🔄 Cập nhật giá")],
        [KeyboardButton("📈 Báo cáo nhóm"), KeyboardButton("❌ Xóa mã")],
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

    # 1. XỬ LÝ DANH MỤC CỔ PHIẾU
    if text == "📊 Chứng Khoán":
        stock_mod = StockModule(user_id)
        await update.message.reply_html(stock_mod.run(), reply_markup=get_stock_menu())
        return

    # 2. QUAY VỀ TRANG CHỦ
    if text == "💼 Tài sản của bạn" or text == "🏠 Trang chủ":
        dash = DashboardModule(user_id)
        await update.message.reply_html(dash.run(), reply_markup=get_ceo_menu())
        return

    # 3. BÁO CÁO NHÓM (Tính năng mới)
    if text == "📈 Báo cáo nhóm":
        stock_mod = StockModule(user_id)
        await update.message.reply_html(stock_mod.get_group_report())
        return

    # 4. XỬ LÝ LỆNH XÓA (xoa VNM) (Tính năng mới)
    if text.lower().startswith("xoa "):
        parts = text.split()
        if len(parts) == 2:
            ticker_del = parts[1].upper()
            with db.get_connection() as conn:
                conn.execute("DELETE FROM transactions WHERE ticker = ? AND asset_type = 'STOCK'", (ticker_del,))
                conn.execute("DELETE FROM manual_prices WHERE ticker = ?", (ticker_del,))
                conn.commit()
            await update.message.reply_html(f"🗑 Đã xóa toàn bộ dữ liệu mã <b>{ticker_del}</b>.")
            stock_mod = StockModule(user_id)
            await update.message.reply_html(stock_mod.run())
            return

    # 5. HƯỚNG DẪN CÁC NÚT TRONG STOCK
    if text == "➕ Giao dịch":
        await update.message.reply_html("➕ <b>GIAO DỊCH:</b> Hãy gõ theo cú pháp:\n<code>S [Mã] [Số lượng] [Giá]</code>\nVí dụ: <code>S HPG 1000 28.5</code>")
        return
    
    if text == "🔄 Cập nhật giá":
        await update.message.reply_html("🔄 <b>CẬP NHẬT GIÁ:</b> Hãy gõ theo cú pháp:\n<code>gia [Mã] [Giá mới]</code>\nVí dụ: <code>gia VPB 30.2</code>")
        return

    if text == "❌ Xóa mã":
        await update.message.reply_html("🗑 <b>XÓA MÃ:</b> Gõ <code>xoa [Mã]</code> để xóa sạch lịch sử.\nVí dụ: <code>xoa VNM</code>")
        return

    # 6. XỬ LÝ CẬP NHẬT GIÁ (gia [Mã] [Giá])
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

    # 7. XỬ LÝ LÀM MỚI
    if text == "🔄 Làm mới":
        dash = DashboardModule(user_id)
        await update.message.reply_html(f"🔄 <b>Dữ liệu đã được làm mới:</b>\n\n{dash.run()}")
        return

    # 8. XỬ LÝ LỆNH NHẬP LIỆU (Parser)
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
                f"💰 Giá trị: <b>{val_format}đ</b>"
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
    
    print("🚀 Bot Finance đang khởi động với Menu chuyên biệt...")
    application.run_polling(drop_pending_updates=True)
