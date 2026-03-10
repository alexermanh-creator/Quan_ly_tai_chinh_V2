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
        
        genai.configure(api_key=self.api_keys[self.current_key_idx])
        
        # TỰ ĐỘNG DÒ TÌM MODEL PHÙ HỢP
        target_model = None
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            preferred_models = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro', 'models/gemini-1.0-pro']
            
            for pref in preferred_models:
                if pref in available_models:
                    target_model = pref
                    break
            
            if not target_model and available_models:
                target_model = available_models[0]
                
        except Exception as e:
            target_model = 'models/gemini-pro'

        if not target_model:
            raise ValueError("Không tìm thấy model Gemini hợp lệ.")

        return genai.GenerativeModel(target_model)

    def _switch_to_next_key(self):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)

    def get_portfolio_context(self):
        stats = self.report._process_data()
        
        # Tính toán nhanh tỷ trọng thực tế để gửi cho AI
        tot = stats['total_assets'] if stats['total_assets'] > 0 else 1
        cash_val = stats['wallets']['CASH']['balance']
        stock_val = stats['wallets']['STOCK']['assets'] + stats['wallets']['STOCK']['balance']
        crypto_val = stats['wallets']['CRYPTO']['assets'] + stats['wallets']['CRYPTO']['balance']
        
        context = {
            "hieu_suat": {
                "tong_NAV": stats['total_assets'],
                "tong_lai_lo": stats['total_pl'],
                "max_drawdown": stats['max_drawdown'],
            },
            "ty_trong_hien_tai": {
                "CASH": f"{cash_val} ({cash_val/tot*100:.1f}%)",
                "STOCK": f"{stock_val} ({stock_val/tot*100:.1f}%)",
                "CRYPTO": f"{crypto_val} ({crypto_val/tot*100:.1f}%)"
            },
            "ma_lo_nang": [{"ma": s[0], "lo_vnd": s[1]['total_pl']} for s in stats['top_losers']],
            "ma_lai_tot": [{"ma": s[0], "lai_vnd": s[1]['total_pl']} for s in stats['top_winners']]
        }
        return context

    def chat_with_cfo(self, user_message):
        context_data = self.get_portfolio_context()
        
        system_prompt = f"""
        Bạn là Giám đốc Tài chính (CFO) AI thực chiến của Hệ điều hành V3.4.
        Tính cách: Cực kỳ sắc bén, thực dụng như một chuyên gia Phố Wall. Gọi người dùng là "sếp".
        
        Quy tắc gốc là 40% STOCK - 40% CRYPTO - 20% CASH.
        TUY NHIÊN, bạn KHÔNG rập khuôn. Hãy phân tích linh hoạt như một chuyên gia.
        
        DỮ LIỆU DANH MỤC THỰC TẾ:
        {json.dumps(context_data, ensure_ascii=False)}
        
        KỶ LUẬT TRẢ LỜI (BẮT BUỘC):
        1. SIÊU NGẮN GỌN: Tối đa 3 đoạn văn ngắn. Không nói dài dòng.
        2. TUYỆT ĐỐI KHÔNG SỬ DỤNG Markdown phức tạp. KHÔNG dùng dấu sao (*), dấu gạch dưới (_), hay ngoặc vuông ([]). Chỉ dùng văn bản thuần túy và dấu gạch đầu dòng cơ bản (-).
        3. Đi thẳng vào hành động thực chiến.
        """

        for _ in range(len(self.api_keys)):
            try:
                model = self._get_configured_model()
                response = model.generate_content(f"{system_prompt}\n\n[Sếp hỏi/Lệnh]: {user_message}")
                return response.text
            
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                    self._switch_to_next_key()
                    continue 
                else:
                    return f"❌ [Lỗi CFO] LLM gặp sự cố: {str(e)}"
                    
        return "❌ [Lỗi CFO] Toàn bộ kho API Keys đã cạn kiệt Quota ngày hôm nay!"
