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
        
        # Lấy danh sách API Keys từ .env (main.py có thể ghi đè biến này từ Database)
        keys_env = os.environ.get("GEMINI_API_KEYS", "")
        self.api_keys = [k.strip() for k in keys_env.split(",") if k.strip()]
        self.current_key_idx = 0
        
        # TỐI ƯU 1: LƯU CACHE TÊN MODEL (Giảm 2 giây mỗi lần chat)
        self.cached_model_name = None 

    def _get_configured_model(self):
        if not self.api_keys:
            raise ValueError("⚠️ Hệ thống chưa được nạp GEMINI_API_KEYS. Sếp hãy vào Cài đặt để thêm!")
        
        genai.configure(api_key=self.api_keys[self.current_key_idx])
        
        # Nếu đã có Cache thì dùng luôn, cấm dò lại
        if self.cached_model_name:
            # Ép temperature xuống 0.2 để AI tư duy logic, tính toán lạnh lùng, bớt nói hoa mỹ
            return genai.GenerativeModel(self.cached_model_name, generation_config={"temperature": 0.2})
        
        target_model = None
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # Ưu tiên bản Pro mới nhất để suy luận logic sâu
            preferred_models = ['models/gemini-1.5-pro-latest', 'models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']
            for pref in preferred_models:
                if pref in available_models:
                    target_model = pref
                    break
            if not target_model and available_models:
                target_model = available_models[0]
        except Exception as e:
            target_model = 'models/gemini-1.5-pro'

        if not target_model:
            raise ValueError("Không tìm thấy model Gemini hợp lệ.")

        # Lưu lại vào RAM để lần sau dùng ngay
        self.cached_model_name = target_model
        return genai.GenerativeModel(target_model, generation_config={"temperature": 0.2})

    def _switch_to_next_key(self):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        self.cached_model_name = None # Xóa cache khi đổi API Key

    def _get_realtime_price(self, symbol, wallet_type):
        """Hệ thống lấy giá xuyên tường lửa"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            symbol = symbol.upper().strip()

            if wallet_type == 'CRYPTO':
                res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=3)
                if res.status_code == 200:
                    return float(res.json()['price'])
            
            elif wallet_type == 'STOCK':
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.VN?region=US&lang=en-US"
                    res = requests.get(url, headers=headers, timeout=3)
                    if res.status_code == 200:
                        price = float(res.json()['chart']['result'][0]['meta']['regularMarketPrice'])
                        if price > 0:
                            return price if price >= 1000 else price * 1000
                except Exception:
                    pass

                try:
                    res = requests.get(f"https://apipubaws.tcbs.com.vn/tca-api/v1/ticker/{symbol}/overview", headers=headers, timeout=2)
                    if res.status_code == 200:
                        price = float(res.json().get('price', 0))
                        if price > 0:
                            return price * 1000 if price < 1000 else price
                except Exception:
                    pass

        except Exception as e:
            print(f"[AI WARN] Lỗi dò giá {symbol}: {e}")
            
        return None

    def _fetch_price_worker(self, item):
        """Hàm công nhân chạy đa luồng cho từng mã"""
        sym = item['symbol']
        w_type = item['wallet_id']
        gia_realtime = self._get_realtime_price(sym, w_type)
        return {
            "sym": sym,
            "w_type": w_type,
            "gia_realtime": gia_realtime,
            "gia_database": item['current_price'],
            "so_luong": item['quantity'],
            "gia_von": item['average_price']
        }

    def get_portfolio_context(self):
        # 1. LẤY DỮ LIỆU TỪ REPORT
        stats = self.report._process_data()
        raw_data = stats['raw_data']
        
        tot = stats['total_assets'] if stats['total_assets'] > 0 else 1
        cash_val = stats['wallets']['CASH']['balance']
        stock_val = stats['wallets']['STOCK']['assets'] + stats['wallets']['STOCK']['balance']
        crypto_val = stats['wallets']['CRYPTO']['assets'] + stats['wallets']['CRYPTO']['balance']
        
        chi_tiet = []
        
        # TỐI ƯU 2: CHẠY ĐA LUỒNG QUÉT GIÁ REAL-TIME
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(self._fetch_price_worker, raw_data['holdings'])
            
        for r in results:
            gia_chot = r['gia_realtime'] if r['gia_realtime'] else r['gia_database']
            chi_tiet.append({
                "ma_tai_san": r['sym'],
                "loai_tai_san": r['w_type'],
                "so_luong": r['so_luong'],
                "gia_von": r['gia_von'],
                "gia_hien_tai": gia_chot,
                "loi_nhuan_tam_tinh": (gia_chot - r['gia_von']) * r['so_luong']
            })

        # 2. BỔ SUNG: PHÂN TÍCH LỊCH SỬ GIAO DỊCH (ĐỂ TRẢ LỜI "THÁNG NÀO LÃI, MÃ NÀO LỖ")
        transactions = raw_data.get('transactions', [])
        total_realized = 0
        symbol_pnl = defaultdict(float)
        recent_closed_trades = []

        for tx in transactions:
            # Lọc các lệnh Bán hoặc Chốt Lịch Sử có sinh ra Lãi/Lỗ
            if tx['type'] in ['BAN', 'CHOT_LICH_SU'] and tx['realized_pl']:
                pl = tx['realized_pl']
                total_realized += pl
                sym = tx['symbol'] or "Lịch_Sử"
                symbol_pnl[sym] += pl
                
                # Ghi nhận 15 lệnh bán gần nhất để AI nắm bắt dòng thời gian
                if len(recent_closed_trades) < 15:
                    note = f" ({tx['note']})" if tx['note'] else ""
                    recent_closed_trades.append(f"Mã {sym}: {'Lãi' if pl > 0 else 'Lỗ'} {pl:,.0f} đ{note}")

        sorted_pnl = sorted(symbol_pnl.items(), key=lambda x: x[1], reverse=True)
        top_winners = [f"{k}: +{v:,.0f} đ" for k, v in sorted_pnl[:3] if v > 0]
        top_losers = [f"{k}: {v:,.0f} đ" for k, v in sorted_pnl[-3:] if v < 0]

        context = {
            "hieu_suat_hien_tai": {
                "tong_NAV_tai_san": stats['total_assets'],
                "muc_tieu_NAV": raw_data['settings'].get('goal', 'Chưa đặt'),
                "max_drawdown": stats['max_drawdown'],
            },
            "ty_trong_phan_bo": {
                "TIEN_MAT_SAN_SANG_MUA": f"{cash_val} đ ({cash_val/tot*100:.1f}%)",
                "CHUNG_KHOAN": f"{stock_val} đ ({stock_val/tot*100:.1f}%)",
                "CRYPTO": f"{crypto_val} đ ({crypto_val/tot*100:.1f}%)"
            },
            "chi_tiet_danh_muc_dang_om": chi_tiet,
            "lich_su_chien_dau": {
                "tong_lai_lo_da_chot_vao_tui": total_realized,
                "top_ma_an_dam_nhat": top_winners,
                "top_ma_cat_lo_dau_nhat": top_losers,
                "15_lenh_ban_gan_nhat_theo_thoi_gian": recent_closed_trades
            }
        }
        return context

    def chat_with_cfo(self, user_message):
        context_data = self.get_portfolio_context()
        
        # RADAR NHẬN DIỆN MÃ TÀI SẢN
        words = re.findall(r'\b[a-zA-Z]{3,5}\b', user_message)
        stop_words = {'gia', 'hom', 'nay', 'thi', 'sao', 'cho', 'toi', 'cfo', 'lam', 'the', 'nao', 'mua', 'ban', 'hay', 'con', 'lai', 'nua', 'qua', 'voi', 'cua', 'nen', 'giu', 'cat', 'anh', 'nha', 'tien', 'mat', 'rut', 'nap', 'kho', 'tot', 'xau', 'cai', 'mot', 'hai', 'vay', 'nhe'}
        potential_tickers = set([w.upper() for w in words if w.lower() not in stop_words])
        existing_tickers = [item['ma_tai_san'] for item in context_data.get('chi_tiet_danh_muc_dang_om', [])]
        
        ma_ngoai = []
        
        # TỐI ƯU 3: CHẠY ĐA LUỒNG CHO CÁC MÃ SẾP HỎI THÊM
        def _fetch_external_price(sym):
            price = self._get_realtime_price(sym, 'STOCK')
            if not price:
                price = self._get_realtime_price(sym, 'CRYPTO')
            return sym, price

        external_to_fetch = [sym for sym in potential_tickers if sym not in existing_tickers]
        if external_to_fetch:
            with ThreadPoolExecutor(max_workers=5) as executor:
                ext_results = executor.map(_fetch_external_price, external_to_fetch)
                for sym, price in ext_results:
                    if price:
                        ma_ngoai.append({"ma": sym, "gia_hien_tai_vua_quet": price})
                        
        if ma_ngoai:
            context_data["ma_ngoai_danh_muc_vua_hoi"] = ma_ngoai
        
        system_prompt = f"""
        Bạn là Siêu Trợ Lý AI của Hệ điều hành V3.4. Bạn sở hữu tri thức của nhân loại, đồng thời là Giám đốc Tài chính (CFO) sát thủ trên thị trường.
        Luôn gọi người dùng là "Sếp" một cách kính trọng nhưng chuyên nghiệp (Tuyệt đối không dùng tên thật).
        
        CHẾ ĐỘ HOẠT ĐỘNG:
        1. PHÂN TÍCH TÀI CHÍNH: Hóa thân thành CFO Thiết Quân Luật. Đọc kỹ dữ liệu LỊCH SỬ CHIẾN ĐẤU để biết Sếp đang lãi/lỗ dạo gần đây thế nào, mổ xẻ TỶ TRỌNG và TIỀN MẶT để lập Kế hoạch hành động (Action Plan) thực chiến. Đừng nói nước đôi, hãy chỉ đích danh mã nào gánh, mã nào phá.
        2. KIẾN THỨC KHÁC: Trả lời như một LLM bách khoa toàn thư sắc sảo.
        
        DỮ LIỆU QUÉT TOÀN CẢNH:
        {json.dumps(context_data, ensure_ascii=False)}
        
        KỶ LUẬT TRẢ LỜI QUAN TRỌNG (BẮT BUỘC):
        - VĂN BẢN THUẦN TÚY: Tuyệt đối KHÔNG sử dụng Markdown phức tạp. KHÔNG DÙNG dấu sao (*), dấu gạch dưới (_), hay ngoặc vuông ([]). Nếu muốn nhấn mạnh, hãy viết IN HOA.
        - ĐỊNH DẠNG: Chỉ dùng chữ, số, dấu câu thông thường và gạch đầu dòng (-) để liệt kê.
        - ĐỘ DÀI VÀ CẤU TRÚC: Mặc định trả lời ngắn gọn, đánh thẳng vào trọng tâm. TRỪ KHI sếp yêu cầu đích danh số lượng, BẠN PHẢI TUÂN THỦ VÀ LIỆT KÊ ĐÚNG.
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
