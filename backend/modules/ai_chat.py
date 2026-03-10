# backend/modules/ai_chat.py
import os
import json
import time
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
        """Động cơ dò giá 4 màng lọc - Bất tử trước mọi tường lửa"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*'
            }
            symbol = symbol.upper().strip()

            if wallet_type == 'CRYPTO':
                # Gọi API Binance
                res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=5)
                if res.status_code == 200:
                    return float(res.json()['price'])
            
            elif wallet_type == 'STOCK':
                # --- TẦNG 1: VNDirect (Ổn định nhất) ---
                try:
                    res = requests.get(f"https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date:desc&q=code:{symbol}&size=1", headers=headers, timeout=4)
                    if res.status_code == 200:
                        data = res.json().get('data', [])
                        if data:
                            price = float(data[0]['close'])
                            return price * 1000 if price < 1000 else price
                except Exception:
                    pass

                # --- TẦNG 2: TCBS ---
                try:
                    res = requests.get(f"https://apipubaws.tcbs.com.vn/tca-api/v1/ticker/{symbol}/overview", headers=headers, timeout=4)
                    if res.status_code == 200:
                        price = float(res.json().get('price', 0))
                        if price > 0:
                            return price * 1000 if price < 1000 else price
                except Exception:
                    pass

                # --- TẦNG 3: DNSE (TradingView Backend) ---
                try:
                    to_time = int(time.time())
                    from_time = to_time - (10 * 86400) # Lấy data 10 ngày
                    url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={from_time}&to={to_time}&symbol={symbol}&resolution=1D"
                    res = requests.get(url, headers=headers, timeout=4)
                    if res.status_code == 200:
                        data = res.json()
                        if 'c' in data and len(data['c']) > 0:
                            price = float(data['c'][-1])
                            return price * 1000 if price < 1000 else price
                except Exception:
                    pass

                # --- TẦNG 4: Simplize ---
                try:
                    res = requests.get(f"https://api.simplize.vn/api/company/ticker-info/{symbol}", headers=headers, timeout=4)
                    if res.status_code == 200:
                        price = float(res.json().get('data', {}).get('priceClose', 0))
                        if price > 0:
                            return price * 1000 if price < 1000 else price
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"[AI WARN] Lỗi hệ thống dò giá: {e}")
            
        return None # Rớt cả 4 mạng thì mới chịu dùng Offline

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
            
            # Quét giá mạng Real-time
            gia_realtime = self._get_realtime_price(sym, w_type)
            gia_chot = gia_realtime if gia_realtime else gia_database
            nguon = "TRỰC TIẾP TRÊN SÀN (Real-time)" if gia_realtime else "Sổ sách Offline"
            
            chi_tiet.append({
                "ma_tai_san": sym,
                "loai_tai_san": w_type,
                "so_luong": h['quantity'],
                "gia_von_trung_binh_sach": h['average_price'],
                "gia_thi_truong_hien_tai": gia_chot,
                "nguon_cap_gia": nguon
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
        Bạn là Giám đốc Tài chính (CFO) kiêm Chuyên gia Đầu tư của Hệ điều hành V3.4.
        Tính cách: Sắc bén, thực dụng, phân tích logic như Phố Wall. Gọi người dùng là "sếp".
        
        DỮ LIỆU DANH MỤC THỰC TẾ (Đã được cập nhật Giá trị Real-time):
        {json.dumps(context_data, ensure_ascii=False)}
        
        KỶ LUẬT TRẢ LỜI (BẮT BUỘC):
        1. VĂN BẢN THUẦN TÚY: Tuyệt đối KHÔNG dùng Markdown (không dùng dấu sao *, gạch dưới _, ngoặc vuông []). Chỉ dùng chữ và gạch đầu dòng (-).
        2. NGẮN GỌN: Tối đa 3 đoạn. Đi thẳng vào vấn đề sếp hỏi.
        
        HƯỚNG DẪN PHÂN TÍCH:
        - So sánh ngay [gia_von_trung_binh_sach] với [gia_thi_truong_hien_tai] để xem sếp đang lỗ hay lãi (Kèm theo số % cụ thể).
        - Đưa ra góc nhìn thực chiến về rủi ro của mã đó để quyết định nên Gồng hay Cắt.
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
