# backend/modules/ai_chat.py
import os
import json
import requests
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

    def _get_realtime_price(self, symbol, wallet_type):
        """Hàm tự động kết nối Internet lấy giá thị trường Real-time"""
        try:
            if wallet_type == 'CRYPTO':
                # Gọi API Binance
                res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=3)
                if res.status_code == 200:
                    return float(res.json()['price'])
            
            elif wallet_type == 'STOCK':
                # Gọi API Chứng khoán VN (TCBS)
                headers = {'User-Agent': 'Mozilla/5.0'}
                res = requests.get(f"https://apipubaws.tcbs.com.vn/tca-api/v1/ticker/{symbol}/overview", headers=headers, timeout=3)
                if res.status_code == 200:
                    data = res.json()
                    price = data.get('price', 0)
                    # Xử lý giá nếu API trả về số nhỏ (TCBS thỉnh thoảng trả giá thực vd: 27000)
                    return float(price)
        except Exception as e:
            print(f"[AI WARN] Không thể lấy giá realtime cho {symbol}: {e}")
            
        return None # Trả về None nếu rớt mạng hoặc mã không tồn tại

    def get_portfolio_context(self):
        stats = self.report._process_data()
        raw_data = stats['raw_data']
        
        tot = stats['total_assets'] if stats['total_assets'] > 0 else 1
        cash_val = stats['wallets']['CASH']['balance']
        stock_val = stats['wallets']['STOCK']['assets'] + stats['wallets']['STOCK']['balance']
        crypto_val = stats['wallets']['CRYPTO']['assets'] + stats['wallets']['CRYPTO']['balance']
        
        # BÓC TÁCH CHI TIẾT & CHÈN GIÁ REAL-TIME VÀO BÁO CÁO CHO AI
        chi_tiet = []
        for h in raw_data['holdings']:
            sym = h['symbol']
            w_type = h['wallet_id']
            gia_database = h['current_price']
            
            # Cố gắng lấy giá trên mạng trước
            gia_realtime = self._get_realtime_price(sym, w_type)
            
            # Nếu trên mạng có giá thì dùng, nếu rớt mạng thì lôi giá cũ trong Database ra dùng tạm
            gia_chot = gia_realtime if gia_realtime else gia_database
            
            chi_tiet.append({
                "ma_tai_san": sym,
                "loai_tai_san": w_type,
                "so_luong": h['quantity'],
                "gia_von_trung_binh_sach": h['average_price'],
                "gia_thi_truong_hien_tai": gia_chot,
                "nguon_cap_gia": "Real-time Internet" if gia_realtime else "Database Offline"
            })
            
        context = {
            "hieu_suat": {
                "tong_NAV": stats['total_assets'],
                "max_drawdown": stats['max_drawdown'],
            },
            "ty_trong_hien_tai": {
                "CASH": f"{cash_val} ({cash_val/tot*100:.1f}%)",
                "STOCK": f"{stock_val} ({stock_val/tot*100:.1f}%)",
                "CRYPTO": f"{crypto_val} ({crypto_val/tot*100:.1f}%)"
            },
            "chi_tiet_danh_muc": chi_tiet
        }
        return context

    def chat_with_cfo(self, user_message):
        context_data = self.get_portfolio_context()
        
        system_prompt = f"""
        Bạn là Giám đốc Tài chính (CFO) kiêm Chuyên gia Phân tích Đầu tư của Hệ điều hành V3.4.
        Tính cách: Sắc bén, thực dụng, phân tích logic như Phố Wall. Gọi người dùng là "sếp".
        
        DỮ LIỆU DANH MỤC THỰC TẾ (Đã được Bot cập nhật giá Real-time từ Internet):
        {json.dumps(context_data, ensure_ascii=False)}
        
        KỶ LUẬT TRẢ LỜI (BẮT BUỘC):
        1. VĂN BẢN THUẦN TÚY: Tuyệt đối KHÔNG dùng Markdown (không dùng dấu sao *, gạch dưới _, ngoặc vuông []). Chỉ dùng chữ và gạch đầu dòng (-).
        2. NGẮN GỌN: Tối đa 3 đoạn. Đi thẳng vào vấn đề sếp hỏi.
        
        HƯỚNG DẪN PHÂN TÍCH:
        - So sánh ngay [gia_von_trung_binh_sach] với [gia_thi_truong_hien_tai] để xem sếp đang lỗ hay lãi. Tính ra % luôn.
        - Phân tích rủi ro của mã đó dựa trên hiểu biết tài chính của bạn (Ngân hàng, BĐS, Coin...).
        - Khuyên chiến lược hành động: Nắm giữ chờ hồi / Cắt lỗ hạ tỷ trọng / Mua trung bình giá.
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
