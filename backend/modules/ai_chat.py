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
        
        # Lấy danh sách API Keys từ .env
        keys_env = os.environ.get("GEMINI_API_KEYS", "")
        self.api_keys = [k.strip() for k in keys_env.split(",") if k.strip()]
        self.current_key_idx = 0

    def _get_configured_model(self):
        if not self.api_keys:
            raise ValueError("⚠️ Chưa cấu hình GEMINI_API_KEYS trong file .env")
        
        # Cấu hình API Key hiện hành
        genai.configure(api_key=self.api_keys[self.current_key_idx])
        
        # TỰ ĐỘNG DÒ TÌM MODEL PHÙ HỢP (AUTO-DISCOVERY)
        target_model = None
        try:
            # Lấy danh sách tất cả các model hỗ trợ sinh text (generateContent)
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            # Danh sách ưu tiên từ xịn/nhanh nhất trở xuống
            preferred_models = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro', 'models/gemini-1.0-pro']
            
            for pref in preferred_models:
                if pref in available_models:
                    target_model = pref
                    break
            
            # Nếu không có model nào trong list ưu tiên, lấy đại model đầu tiên hỗ trợ chat
            if not target_model and available_models:
                target_model = available_models[0]
                
        except Exception as e:
            # Fallback an toàn phòng khi hàm list_models bị chặn
            target_model = 'models/gemini-pro'

        if not target_model:
            raise ValueError("Không tìm thấy model Gemini hợp lệ cho API Key này.")

        print(f"[AI INFO] Đã kết nối thành công với model: {target_model}")
        return genai.GenerativeModel(target_model)

    def _switch_to_next_key(self):
        """Xoay vòng API Key nếu hết Quota"""
        old_idx = self.current_key_idx
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        print(f"[AI INFO] Chuyển từ API Key {old_idx} sang API Key {self.current_key_idx}")

    def get_portfolio_context(self):
        stats = self.report._process_data()
        context = {
            "tong_quan": {
                "tong_tai_san_hien_tai": stats['total_assets'],
                "tong_lai_lo": stats['total_pl'],
                "max_drawdown_phan_tram": stats['max_drawdown'],
                "ty_le_thang_win_rate_phan_tram": stats['win_rate']
            },
            "trang_thai_cac_vi": {
                "CASH": stats['wallets']['CASH']['balance'],
                "STOCK": stats['wallets']['STOCK']['assets'] + stats['wallets']['STOCK']['balance'],
                "CRYPTO": stats['wallets']['CRYPTO']['assets'] + stats['wallets']['CRYPTO']['balance']
            },
            "ma_dang_lo_nang": [{"ma": s[0], "lo_vnd": s[1]['total_pl']} for s in stats['top_losers']],
            "ma_dang_lai_tot": [{"ma": s[0], "lai_vnd": s[1]['total_pl']} for s in stats['top_winners']]
        }
        return context

    def chat_with_cfo(self, user_message):
        context_data = self.get_portfolio_context()
        
        system_prompt = f"""
        Bạn là Giám đốc Tài chính (CFO) AI của Hệ điều hành tài chính V3.4.
        Tính cách: Vô cùng khắt khe, châm biếm, chỉ nói chuyện bằng các con số thực tế, tuyệt đối không nịnh nọt hay an ủi. Gọi người dùng là "sếp".
        
        Quy tắc quản trị danh mục là: 40% STOCK - 40% CRYPTO - 20% CASH.
        
        DỮ LIỆU DANH MỤC THỰC TẾ (REAL-TIME):
        {json.dumps(context_data, ensure_ascii=False)}
        
        NHIỆM VỤ: Đọc câu hỏi/lệnh của sếp. Nhìn vào dữ liệu để phân tích thẳng thắn. Chỉ trích gay gắt nếu tỷ trọng mất cân bằng, gồng lỗ nặng (như con VPB), hoặc thiếu tiền mặt CASH.
        """

        for _ in range(len(self.api_keys)):
            try:
                model = self._get_configured_model()
                response = model.generate_content(f"{system_prompt}\n\n[Lệnh từ Sếp]: {user_message}")
                return response.text
            
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                    self._switch_to_next_key()
                    continue 
                else:
                    return f"❌ [Lỗi CFO] LLM gặp sự cố: {str(e)}"
                    
        return "❌ [Lỗi CFO] Toàn bộ kho API Keys đã cạn kiệt Quota ngày hôm nay!"
