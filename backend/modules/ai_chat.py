# backend/modules/ai_chat.py
import os
import json
import requests
import re
from google import genai # Dùng thư viện mới nhất để dứt điểm lỗi 404
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from backend.database.repository import DatabaseRepo
from backend.modules.report import ReportModule

class AIChatModule:
    def __init__(self):
        self.db = DatabaseRepo()
        self.report = ReportModule()
        
        keys_env = os.environ.get("GEMINI_API_KEYS", "")
        self.api_keys = [k.strip() for k in keys_env.split(",") if k.strip()]
        self.current_key_idx = 0
        self.chat_histories = defaultdict(list)

    def _get_client(self):
        """Khởi tạo Client theo công nghệ mới nhất của Google"""
        if not self.api_keys:
            raise ValueError("⚠️ Chưa nạp API Keys trong file .env!")
        return genai.Client(api_key=self.api_keys[self.current_key_idx])

    def _switch_to_next_key(self):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)

    def get_portfolio_context(self):
        """NÂNG CẤP: Lấy chi tiết tài sản và SỨC MUA để AI soi danh mục"""
        stats = self.report._process_data()
        raw_data = stats['raw_data']
        
        # 1. Tổng hợp sức mua (Cash) của từng ví
        wallets_cash = {}
        for w in raw_data['wallets']:
            wallets_cash[w['id']] = {
                "suc_mua_hien_tai": f"{w['balance']:,.0f} đ",
                "tong_von_nap_vao": f"{w['total_in']:,.0f} đ"
            }

        # 2. Chi tiết các mã đang ôm
        holdings = []
        for h in raw_data['holdings']:
            lai_lo = (h['current_price'] - h['average_price']) * h['quantity']
            holdings.append({
                "ma": h['symbol'],
                "vi": h['wallet_id'],
                "sl": h['quantity'],
                "gia_von": f"{h['average_price']:,.2f}",
                "gia_thi_truong": f"{h['current_price']:,.2f}",
                "lai_lo_vnd": f"{lai_lo:,.0f} đ"
            })

        return {
            "NAV_TONG": f"{stats['total_assets']:,.0f} đ",
            "LAI_LO_TONG": f"{stats['total_pl']:,.0f} đ",
            "SUC_MUA_CAC_VI": wallets_cash,
            "DANH_MUC_DANG_NAM_GIU": holdings
        }

    def chat_with_cfo(self, chat_id, user_message):
        for _ in range(len(self.api_keys)):
            try:
                # Lấy dữ liệu thực tế từ Database
                context_data = self.get_portfolio_context()
                client = self._get_client()
                
                system_prompt = f"""
                Bạn là CFO Quant Trader sát thủ. Bạn có quyền truy cập vào sổ sách của Sếp Cường.
                
                DỮ LIỆU TÀI CHÍNH THỰC TẾ:
                {json.dumps(context_data, ensure_ascii=False, indent=2)}
                
                NHIỆM VỤ CHIẾN THUẬT:
                1. SOI SỨC MUA: Nếu Sếp hỏi mua thêm gì đó mà mục 'suc_mua_hien_tai' trong ví tương ứng = 0đ, hãy 'mắng' Sếp vì tội không nạp tiền (nap) mà đòi mua.
                2. SOI DANH MỤC: Nhắc nhở Sếp về các mã đang lỗ nặng hoặc tỷ trọng quá lớn.
                3. PHONG CÁCH: Tuyệt đối không chào hỏi 'Chào Sếp', không 'Tôi có thể giúp gì'. Trả lời thẳng, sắc bén, chuyên nghiệp.
                """

                response = client.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=f"{system_prompt}\n\n[Sếp hỏi]: {user_message}"
                )
                
                return response.text
            
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    self._switch_to_next_key()
                    continue 
                return f"❌ [Lỗi Hệ Thống AI] Sự cố: {str(e)}"
                    
        return "❌ [Lỗi Hệ Thống AI] Toàn bộ kho API Keys đã cạn kiệt Quota ngày hôm nay!"