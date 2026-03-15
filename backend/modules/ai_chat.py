# backend/modules/ai_chat.py
import os
import json
import time
import requests
import re
import google.generativeai as genai
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
        # Biến lưu tên model đã test thành công để không phải dò lại
        self.confirmed_model = None 

    def _get_configured_model(self):
        if not self.api_keys:
            raise ValueError("⚠️ Chưa nạp API Keys trong file .env!")
        
        genai.configure(api_key=self.api_keys[self.current_key_idx])
        
        # Nếu đã dò được model đúng trước đó thì dùng luôn
        if self.confirmed_model:
            return genai.GenerativeModel(self.confirmed_model)

        # CHIẾN THUẬT DÒ TÌM MODEL (FIX LỖI 404)
        # Thử danh sách các tên model từ mới đến cũ, từ ngắn đến dài
        test_models = [
            'gemini-1.5-flash', 
            'models/gemini-1.5-flash', 
            'gemini-1.5-pro',
            'models/gemini-pro'
        ]
        
        for m_name in test_models:
            try:
                model = genai.GenerativeModel(m_name)
                # Chạy thử một lệnh siêu nhẹ để xem có bị 404 không
                model.generate_content("ping", generation_config={"max_output_tokens": 1})
                self.confirmed_model = m_name
                return model
            except Exception as e:
                if "404" in str(e):
                    continue # Thử tên tiếp theo
                # Nếu là lỗi hết hạn mức (429) thì đổi Key luôn
                if "429" in str(e) or "quota" in str(e).lower():
                    self._switch_to_next_key()
                    return self._get_configured_model()
                raise e
        
        # Nếu thử hết không được thì lấy đại model đầu tiên mà Google cung cấp
        try:
            available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            self.confirmed_model = available[0]
            return genai.GenerativeModel(available[0])
        except:
            return genai.GenerativeModel('gemini-pro')

    def _switch_to_next_key(self):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        self.confirmed_model = None 

    def _get_realtime_price(self, symbol, wallet_type):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            symbol = symbol.upper().strip()
            if wallet_type == 'CRYPTO':
                if symbol in ['USDT', 'USDC']: return 1.0
                res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=3)
                if res.status_code == 200: return float(res.json()['price'])
            elif wallet_type == 'STOCK':
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.VN"
                res = requests.get(url, headers=headers, timeout=3)
                if res.status_code == 200:
                    price = float(res.json()['chart']['result'][0]['meta']['regularMarketPrice'])
                    return price if price >= 1000 else price * 1000
        except: pass
        return None

    def _get_ta_data(self, symbol, wallet_type):
        return "Chỉ báo kỹ thuật đang tính toán..."

    def get_portfolio_context(self):
        stats = self.report._process_data()
        raw_data = stats['raw_data']
        
        # --- NÂNG CẤP TẦM NHÌN SỨC MUA (CASH BALANCE) ---
        wallets_summary = {}
        for w in raw_data['wallets']:
            wallets_summary[w['id']] = {
                "suc_mua_tien_mat_hien_tai": f"{w['balance']:,.0f} đ",
                "tong_von_da_nap": f"{w['total_in']:,.0f} đ",
                "tong_von_da_rut": f"{w['total_out']:,.0f} đ"
            }

        chi_tiet_tai_san = []
        for h in raw_data['holdings']:
            lai_lo = (h['current_price'] - h['average_price']) * h['quantity']
            chi_tiet_tai_san.append({
                "ma": h['symbol'],
                "loai": h['wallet_id'],
                "sl": h['quantity'],
                "gia_von": f"{h['average_price']:,.2f}",
                "gia_thi_truong": f"{h['current_price']:,.2f}",
                "lai_lo_tam_tinh_vnd": f"{lai_lo:,.0f} đ"
            })

        context = {
            "NAV_TONG_CONG": f"{stats['total_assets']:,.0f} đ",
            "TONG_LAI_LO_DANH_MUC": f"{stats['total_pl']:,.0f} đ",
            "TRANG_THAI_CAC_VI_TIEN": wallets_summary,
            "DANH_SACH_MA_DANG_OM": chi_tiet_tai_san
        }
        return context

    def chat_with_cfo(self, chat_id, user_message):
        try:
            # 1. Lấy dữ liệu thực tế từ Database
            context_data = self.get_portfolio_context()
            
            # 2. Lấy trí thông minh AI (đã fix 404)
            model = self._get_configured_model()
            
            history_text = ""
            if self.chat_histories[chat_id]:
                for turn in self.chat_histories[chat_id][-3:]:
                    history_text += f"Sếp: {turn['user']}\nCFO: {turn['cfo']}\n"
            
            system_prompt = f"""
            Bạn là CFO Quant Trader sát thủ, cố vấn tài chính riêng của Sếp Cường.
            Nhiệm vụ: Phân tích danh mục và nhắc nhở Sếp về SỨC MUA (Tiền mặt).
            
            DỮ LIỆU TÀI CHÍNH THỰC TẾ CỦA SẾP:
            {json.dumps(context_data, ensure_ascii=False, indent=2)}
            
            YÊU CẦU:
            1. Tuyệt đối không chào "Chào Sếp" hay "Tôi có thể giúp gì". Đi thẳng vào phân tích con số.
            2. Nếu Sếp muốn mua gì đó, hãy check ngay 'suc_mua_tien_mat_hien_tai' trong ví tương ứng. Nếu = 0 đ, hãy yêu cầu Sếp nạp thêm (nap) hoặc thu hồi vốn (thu) từ ví khác trước khi mơ mộng.
            3. Trả lời sắc bén, dùng thuật ngữ tài chính chuẩn (ROI, Drawdown, Sức mua).
            """

            response = model.generate_content(f"{system_prompt}\n\nLịch sử chat:\n{history_text}\n[Sếp hỏi]: {user_message}")
            
            self.chat_histories[chat_id].append({"user": user_message, "cfo": response.text})
            return response.text
            
        except Exception as e:
            return f"❌ [Lỗi Hệ Thống AI] Sự cố: {str(e)}"