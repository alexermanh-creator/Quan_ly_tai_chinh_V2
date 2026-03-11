# backend/modules/settings.py
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.database.repository import DatabaseRepo

class SettingsModule:
    def __init__(self):
        self.db = DatabaseRepo()
        self._init_default_settings()

    def _init_default_settings(self):
        defaults = {
            'crypto_rate': '25000',
            'target_nav': '200000000',
            'gemini_keys': '',
            'auto_sync_interval': '30'
        }
        for k, v in defaults.items():
            row = self.db.execute_query("SELECT value FROM settings WHERE key = ?", (k,), fetch_one=True)
            if not row:
                self.db.execute_query("INSERT INTO settings (key, value) VALUES (?, ?)", (k, v))

    def get_setting(self, key):
        row = self.db.execute_query("SELECT value FROM settings WHERE key = ?", (key,), fetch_one=True)
        return row['value'] if row else None

    def update_setting(self, key, value):
        self.db.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

    def get_main_menu(self):
        rate = float(self.get_setting('crypto_rate') or 25000)
        target = float(self.get_setting('target_nav') or 0)
        sync_int = self.get_setting('auto_sync_interval')
        keys_str = self.get_setting('gemini_keys')
        keys_count = len([k for k in keys_str.split(',') if k.strip()]) if keys_str else "Dùng file .env"

        text = (
            "⚙️ **TRUNG TÂM CÀI ĐẶT HỆ ĐIỀU HÀNH V3.4**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"💱 **Tỷ giá Crypto:** 1 USD = {rate:,.0f} đ\n"
            f"⏱️ **Tự động quét giá:** {sync_int} phút/lần\n"
            f"🎯 **Mục tiêu NAV:** {target:,.0f} đ\n"
            f"🤖 **AI API Keys:** {keys_count}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "👇 *Vui lòng chọn thông số Sếp muốn thay đổi:*"
        )

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("💱 Cập nhật Tỷ giá", callback_data="set_rate"),
            InlineKeyboardButton("🎯 Đổi Mục tiêu", callback_data="set_target")
        )
        markup.add(
            InlineKeyboardButton("🤖 Quản lý AI Keys", callback_data="set_ai_keys"),
            InlineKeyboardButton("⏱️ Cài Auto-Sync", callback_data="set_sync")
        )
        markup.add(InlineKeyboardButton("📖 Hướng dẫn Dùng Lệnh", callback_data="set_guide"))
        markup.add(InlineKeyboardButton("⚠️ KHÔI PHỤC CÀI ĐẶT GỐC", callback_data="set_factory_reset"))
        markup.add(InlineKeyboardButton("🔙 Đóng Menu", callback_data="set_close"))
        
        return text, markup

    def get_guide_text(self):
        text = (
            "📖 **CẨM NANG DÙNG LỆNH V3.4** 📖\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Sếp có thể gõ trực tiếp các lệnh sau vào khung chat để thao tác siêu tốc:\n\n"
            "💵 **1. DÒNG TIỀN (VÍ MẸ)**\n"
            "• `nap [Số tiền]` : Nạp tiền (VD: `nap 50000000`)\n"
            "• `rut [Số tiền]` : Rút tiền (VD: `rut 10000000`)\n\n"
            "📈 **2. CHỨNG KHOÁN (STOCK)**\n"
            "• Mua: `s [Mã] [SL] [Giá]` (VD: `s VPB 1000 25.5`)\n"
            "• Bán: `s [Mã] -[SL] [Giá]` (Thêm dấu `-` trước SL)\n"
            "• Cổ tức Tiền: `ct tien [Mã] [Số tiền]` (VD: `ct tien VPB 500k`)\n"
            "• Cổ tức Cổ phiếu: `ct cp [Mã] [SL]` (VD: `ct cp VPB 150`)\n\n"
            "🟡 **3. CRYPTO (COIN)**\n"
            "• Mua: `c [Mã] [SL] [Giá USD]` (VD: `c ETH 0.5 2000`)\n"
            "• Bán: `c [Mã] -[SL] [Giá USD]`\n\n"
            "🛠 **4. TIỆN ÍCH KHÁC**\n"
            "• `up [Mã] [Giá]` : Sửa giá tay (VD: `up VPB 26`)\n"
            "• `del [Mã]` : Xóa mã (VD: `del VPB`)\n"
            "• `del #[ID]` : Hoàn tác lệnh Bán (VD: `del #154`)\n"
            "• `his [Mã/Ví]` : Lịch sử (VD: `his VPB` hoặc `his nap`)\n"
            "• `? [Câu hỏi]` : Hỏi AI CFO (VD: `? Phân tích danh mục`)\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Quay lại Cài đặt", callback_data="set_main"))
        return text, markup

    def get_ai_keys_menu(self):
        keys_str = self.get_setting('gemini_keys')
        keys = [k.strip() for k in keys_str.split(',') if k.strip()] if keys_str else []
        
        text = "🔑 **DANH SÁCH API KEYS HIỆN TẠI:**\n━━━━━━━━━━━━━━━━━━━\n"
        if not keys:
            text += "Sếp đang dùng API Key cấu hình cứng trong file `.env`.\n"
        else:
            for i, k in enumerate(keys):
                masked = k[:8] + "..." + k[-4:] if len(k) > 12 else k
                text += f"{i+1}. `{masked}`\n"
        
        text += "━━━━━━━━━━━━━━━━━━━\n*Sếp muốn làm gì tiếp theo?*"
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("➕ Thêm Key Mới", callback_data="ai_add_key"),
            InlineKeyboardButton("🗑️ Xóa toàn bộ Key", callback_data="ai_clear_keys")
        )
        markup.add(InlineKeyboardButton("🔙 Quay lại Cài đặt", callback_data="set_main"))
        return text, markup

    def get_factory_reset_warning(self):
        text = (
            "⚠️ **CẢNH BÁO NGUY HIỂM** ⚠️\n\n"
            "Hành động này sẽ **XÓA SẠCH** toàn bộ Lịch sử và Danh mục.\n"
            "Sếp có CHẮC CHẮN muốn đập đi xây lại sổ sách không?"
        )
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✅ CHẮC CHẮN XÓA", callback_data="confirm_reset_yes"),
            InlineKeyboardButton("❌ Hủy bỏ", callback_data="set_main")
        )
        return text, markup
