# backend/modules/ai_chat.py
import os
import json
import time
import requests
import yfinance as yf
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
        """Hệ thống dò giá đa tầng (Binance + Yahoo Finance + TradingView/DNSE)"""
        try:
            if wallet_type == 'CRYPTO':
                # Gọi API Binance
                res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=5)
                if res.status_code == 200:
                    return float(res.json()['price'])
            
            elif wallet_type == 'STOCK':
                # CÁCH 1: Dùng Yahoo Finance (Global - Không bị chặn IP)
                try:
                    ticker = yf.Ticker(f"{symbol}.VN")
                    # Lấy giá realtime phiên gần nhất
                    price = float(ticker.fast_info['last_price'])
                    if price > 0:
                        # Chuẩn hóa giá: Nếu Yahoo trả 25.5 thì x1000 = 25500
                        return price * 1000 if price < 1000 else price
                except Exception:
                    pass # Chuyển sang cách 2 nếu Yahoo chậm

                # CÁCH 2: Dùng API TradingView của DNSE (Siêu mở, không chặn IP quốc tế)
                try:
                    # Lấy timestamp 10 ngày gần nhất để đảm bảo có nến
                    to_time = int(time.time())
                    from_time = to_time - (10 * 86400)
                    url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={from_time}&to={to_time}&symbol={symbol}&resolution=1D"
                    res = requests.get(url, timeout=3)
                    if res.status_code == 200:
                        data = res.json()
                        # Lấy giá đóng cửa/hiện tại của nến cuối cùng (c = close)
                        if 'c' in data and len(data['c']) > 0:
                            price = float(data['c'][-1])
                            return price * 1000 if price < 1000 else price
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"[AI WARN] Hệ thống dò giá bó tay với mã {symbol}: {e}")
            
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
            
            # Cố gắng lấy giá trên mạng trước (Qua 2-3 tầng bảo vệ)
            gia_realtime = self._get_realtime_price(sym, w_type)
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
