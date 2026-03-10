# backend/modules/ai_chat.py
import os
import json
import time
import requests
import re
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
        """Hệ thống lấy giá xuyên tường lửa (Sử dụng API Global)"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            symbol = symbol.upper().strip()

            if wallet_type == 'CRYPTO':
                res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=4)
                if res.status_code == 200:
                    return float(res.json()['price'])
            
            elif wallet_type == 'STOCK':
                # YAHOO FINANCE
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.VN?region=US&lang=en-US"
                    res = requests.get(url, headers=headers, timeout=4)
                    if res.status_code == 200:
                        price = float(res.json()['chart']['result'][0]['meta']['regularMarketPrice'])
                        if price > 0:
                            return price if price >= 1000 else price * 1000
                except Exception:
                    pass

                # TCBS API
                try:
                    res = requests.get(f"https://apipubaws.tcbs.com.vn/tca-api/v1/ticker/{symbol}/overview", headers=headers, timeout=3)
                    if res.status_code == 200:
                        price = float(res.json().get('price', 0))
                        if price > 0:
                            return price * 1000 if price < 1000 else price
                except Exception:
                    pass

        except Exception as e:
            print(f"[AI WARN] Lỗi dò giá {symbol}: {e}")
            
        return None

    def get_portfolio_context(self):
        stats = self.report._process_data()
        raw_data = stats['raw_data']
        
        tot = stats['total_assets'] if stats['total_assets'] > 0 else 1
        cash_val = stats['wallets']['CASH']['balance']
        stock_val = stats['wallets']['STOCK']['assets'] + stats['wallets']['STOCK']['balance']
        crypto_val = stats['wallets']['CRYPTO']['assets'] + stats['wallets']['CRYPTO']['balance']
        
        chi_tiet = []
        for h in raw_data['holdings']:
            sym = h['symbol']
            w_type = h['wallet_id']
            gia_database = h['current_price']
            
            gia_realtime = self._get_realtime_price(sym, w_type)
            gia_chot = gia_realtime if gia_realtime else gia_database
            
            chi_tiet.append({
                "ma_tai_san": sym,
                "loai_tai_san": w_type,
                "so_luong": h['quantity'],
                "gia_von": h['average_price'],
                "gia_hien_tai": gia_chot
            })
            
        context = {
            "hieu_suat": {
                "tong_NAV": stats['total_assets'],
                "max_drawdown": stats['max_drawdown'],
            },
            "ty_trong": {
                "CASH": f"{cash_val} ({cash_val/tot*100:.1f}%)",
                "STOCK": f"{stock_val} ({stock_val/tot*100:.1f}%)",
                "CRYPTO": f"{crypto_val} ({crypto_val/tot*100:.1f}%)"
            },
            "chi_tiet_danh_muc": chi_tiet
        }
        return context

    def chat_with_cfo(self, user_message):
        context_data = self.get_portfolio_context()
        
        # RADAR NHẬN DIỆN MÃ TÀI SẢN
        words = re.findall(r'\b[a-zA-Z]{3,5}\b', user_message)
        stop_words = {'gia', 'hom', 'nay', 'thi', 'sao', 'cho', 'toi', 'cfo', 'lam', 'the', 'nao', 'mua', 'ban', 'hay', 'con', 'lai', 'nua', 'qua', 'voi', 'cua', 'nen', 'giu', 'cat', 'anh', 'nha', 'tien', 'mat', 'rut', 'nap', 'kho', 'tot', 'xau', 'cai', 'mot', 'hai', 'vay', 'nhe'}
        potential_tickers = set([w.upper() for w in words if w.lower() not in stop_words])
        
        existing_tickers = [item['ma_tai_san'] for item in context_data.get('chi_tiet_danh_muc', [])]
        
        ma_ngoai = []
        for sym in potential_tickers:
            if sym not in existing_tickers:
                price = self._get_realtime_price(sym, 'STOCK')
                if not price:
                    price = self._get_realtime_price(sym, 'CRYPTO')
                
                if price:
                    ma_ngoai.append({"ma": sym, "gia_hien_tai_vua_quet": price})
                    
        if ma_ngoai:
            context_data["ma_ngoai_danh_muc_vua_hoi"] = ma_ngoai
        
        system_prompt = f"""
        Bạn là Siêu Trợ Lý AI của Hệ điều hành V3.4. Bạn sở hữu toàn bộ tri thức của nhân loại, đồng thời là một Giám đốc Tài chính (CFO) xuất chúng.
        Luôn gọi người dùng là "sếp" một cách kính trọng nhưng chuyên nghiệp.
        
        CHẾ ĐỘ HOẠT ĐỘNG:
        1. NẾU SẾP HỎI VỀ TÀI CHÍNH/DANH MỤC: Hóa thân thành CFO Thiết Quân Luật. So sánh giá vốn với giá thị trường, phân tích rủi ro và khuyên hành động thực chiến.
        2. NẾU SẾP HỎI CHỦ ĐỀ KHÁC: Trả lời như một LLM bách khoa toàn thư.
        
        DỮ LIỆU DANH MỤC HIỆN TẠI:
        {json.dumps(context_data, ensure_ascii=False)}
        
        KỶ LUẬT TRẢ LỜI QUAN TRỌNG (BẮT BUỘC):
        - VĂN BẢN THUẦN TÚY: Tuyệt đối KHÔNG sử dụng Markdown phức tạp. KHÔNG DÙNG dấu sao (*), dấu gạch dưới (_), hay ngoặc vuông ([]).
        - ĐỊNH DẠNG: Chỉ dùng chữ, số, dấu câu thông thường và gạch đầu dòng (-) để liệt kê.
        - ĐỘ DÀI VÀ CẤU TRÚC: Mặc định trả lời ngắn gọn (3-4 đoạn). TUY NHIÊN, nếu sếp yêu cầu đích danh số lượng (ví dụ: "cho 3 lời khuyên", "phân tích chi tiết"), BẠN PHẢI TUÂN THỦ VÀ LIỆT KÊ ĐÚNG SỐ LƯỢNG MÀ SẾP YÊU CẦU.
        """

        for _ in range(len(self.api_keys)):
            try:
                model = self._get_configured_model()
                response = model.generate_content(f"{system_prompt}\n\n[Lệnh/Câu hỏi từ Sếp]: {user_message}")
                return response.text
            
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                    self._switch_to_next_key()
                    continue 
                else:
                    return f"❌ [Lỗi Hệ Thống AI] LLM gặp sự cố: {str(e)}"
                    
        return "❌ [Lỗi Hệ Thống AI] Toàn bộ kho API Keys đã cạn kiệt Quota ngày hôm nay!"
