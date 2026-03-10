# backend/modules/ai_chat.py
import os
import json
import google.generativeai as genai
from backend.database.repository import DatabaseRepo
from backend.modules.report import ReportModule

class AIChatModule:
    def __init__(self):
        self.db = DatabaseRepo()
        self.report = ReportModule()
        
        # Lấy danh sách API Keys từ .env và tạo cơ chế Pool (danh sách)
        keys_env = os.environ.get("GEMINI_API_KEYS", "")
        self.api_keys = [k.strip() for k in keys_env.split(",") if k.strip()]
        self.current_key_idx = 0

    def _get_configured_model(self):
        if not self.api_keys:
            raise ValueError("⚠️ Chưa cấu hình GEMINI_API_KEYS trong file .env (VD: key1,key2,key3)")
        
        # Cấu hình API Key hiện hành
        genai.configure(api_key=self.api_keys[self.current_key_idx])
        
        # Sử dụng model flash: phản hồi cực nhanh, rẻ, phù hợp làm chat bot
        return genai.GenerativeModel('gemini-1.5-flash')

    def _switch_to_next_key(self):
        """Tự động xoay vòng sang API Key tiếp theo nếu Key hiện tại hết hạn mức"""
        old_idx = self.current_key_idx
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        print(f"[AI INFO] API Key {old_idx} lỗi/hết hạn mức. Đã chuyển sang API Key {self.current_key_idx}")

    def get_portfolio_context(self):
        """Lấy và nén dữ liệu báo cáo để AI có cái nhìn toàn cảnh về tài sản"""
        stats = self.report._process_data()
        
        # Trích xuất các dữ liệu trọng yếu nhất để đưa cho AI
        context = {
            "tong_quan": {
                "tong_tai_san_hien_tai": stats['total_assets'],
                "tong_lai_lo": stats['total_pl'],
                "max_drawdown_phan_tram": stats['max_drawdown'],
                "ty_le_thang_win_rate_phan_tram": stats['win_rate']
            },
            "trang_thai_cac_vi": {
                "CASH (Tiền mặt dự phòng)": stats['wallets']['CASH']['balance'],
                "STOCK (Chứng khoán)": stats['wallets']['STOCK']['assets'] + stats['wallets']['STOCK']['balance'],
                "CRYPTO (Tiền mã hóa)": stats['wallets']['CRYPTO']['assets'] + stats['wallets']['CRYPTO']['balance']
            },
            "cac_ma_dang_lo_nang_nhat": [{"ma": s[0], "lo_vnd": s[1]['total_pl']} for s in stats['top_losers']],
            "cac_ma_dang_lai_tot_nhat": [{"ma": s[0], "lai_vnd": s[1]['total_pl']} for s in stats['top_winners']]
        }
        return context

    def chat_with_cfo(self, user_message):
        """Gửi prompt và dữ liệu lên Gemini với cơ chế tự động Fallback API Key"""
        context_data = self.get_portfolio_context()
        
        system_prompt = f"""
        Bạn là Giám đốc Tài chính (CFO) AI của Hệ điều hành tài chính V3.4.
        Tính cách: Vô cùng khắt khe, lạnh lùng, chỉ nói chuyện bằng các con số thực tế, tuyệt đối không nịnh nọt hay an ủi. Gọi người dùng là "sếp".
        
        Quy tắc quản trị danh mục (Plug & Play) của hệ thống này là: 40% STOCK - 40% CRYPTO - 20% CASH.
        
        DỮ LIỆU DANH MỤC THỰC TẾ (REAL-TIME):
        {json.dumps(context_data, ensure_ascii=False)}
        
        NHIỆM VỤ CỦA BẠN:
        1. Đọc yêu cầu/câu hỏi của sếp.
        2. Nhìn vào dữ liệu thực tế ở trên để phân tích.
        3. CHỈ TRÍCH THẲNG MẶT nếu thấy các dấu hiệu nguy hiểm sau:
           - Tỷ trọng phân bổ lệch quá xa mức chuẩn (Ví dụ nhồi quá nhiều vào STOCK mà bỏ trống CASH).
           - Có mã đang gồng lỗ quá nặng.
           - Max Drawdown quá cao nhưng sếp vẫn không chịu cắt lỗ.
        4. Trả lời bằng tiếng Việt, in đậm các con số quan trọng, gạch đầu dòng rõ ràng để đọc trên Telegram.
        """

        # Vòng lặp xoay vòng Key: Thử tối đa số lượng key đang có
        for _ in range(len(self.api_keys)):
            try:
                model = self._get_configured_model()
                response = model.generate_content(
                    f"{system_prompt}\n\n[Lệnh từ Sếp]: {user_message}"
                )
                return response.text
            
            except Exception as e:
                error_msg = str(e).lower()
                # Bắt các lỗi liên quan đến Quota (429), Rate Limit để chuyển Key
                if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                    self._switch_to_next_key()
                    continue 
                else:
                    return f"❌ [Hệ thống CFO] Báo cáo sếp, hệ thống lõi gặp sự cố: {str(e)}"
                    
        return "❌ [Hệ thống CFO] Toàn bộ kho API Keys đã cạn kiệt Quota. Sếp vui lòng nạp thêm Key mới vào file .env!"
