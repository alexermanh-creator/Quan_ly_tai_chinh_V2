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

    def _get_model(self):
        if not self.api_keys:
            raise ValueError("⚠️ Hệ thống chưa được nạp GEMINI_API_KEYS. Sếp hãy vào Cài đặt để thêm!")
        
        genai.configure(api_key=self.api_keys[self.current_key_idx])
        # SỬA LỖI: Dùng model 'gemini-1.5-flash' để đảm bảo tính tương thích và tốc độ
        return genai.GenerativeModel('gemini-1.5-flash', generation_config={"temperature": 0.3})

    def _switch_to_next_key(self):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)

    def _get_realtime_price(self, symbol, wallet_type):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            symbol = symbol.upper().strip()

            if wallet_type == 'CRYPTO':
                if symbol in ['USDT', 'USDC', 'FDUSD', 'BUSD']: return 1.0
                sources = [
                    f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}-USDT",
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}-USD?region=US&lang=en-US",
                    f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
                ]
                for url in sources:
                    try:
                        res = requests.get(url, headers=headers, timeout=3)
                        if res.status_code == 200:
                            data = res.json()
                            if 'kucoin' in url: return float(data['data']['price'])
                            if 'yahoo' in url: return float(data['chart']['result'][0]['meta']['regularMarketPrice'])
                            if 'binance' in url: return float(data['price'])
                    except: continue
            
            elif wallet_type == 'STOCK':
                sources = [
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.VN?region=US&lang=en-US",
                    f"https://apipubaws.tcbs.com.vn/tca-api/v1/ticker/{symbol}/overview"
                ]
                for url in sources:
                    try:
                        res = requests.get(url, headers=headers, timeout=3)
                        if res.status_code == 200:
                            data = res.json()
                            if 'yahoo' in url:
                                price = float(data['chart']['result'][0]['meta']['regularMarketPrice'])
                                return price if price >= 1000 else price * 1000
                            if 'tcbs' in url:
                                price = float(data.get('price', 0))
                                return price * 1000 if price < 1000 else price
                    except: continue
        except: pass
        return None

    def _get_ta_data(self, symbol, wallet_type):
        try:
            prices = []
            headers = {'User-Agent': 'Mozilla/5.0'}
            if wallet_type == 'CRYPTO':
                if symbol in ['USDT', 'USDC']: return "Stablecoin: Tỷ giá neo cứng ở 1 USD"
                try:
                    res = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1d&limit=30", timeout=3)
                    if res.status_code == 200: prices = [float(k[4]) for k in res.json()]
                except: pass
            elif wallet_type == 'STOCK':
                try:
                    res = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.VN?interval=1d&range=2mo", headers=headers, timeout=3)
                    if res.status_code == 200: prices = [p for p in res.json()['chart']['result'][0]['indicators']['quote'][0]['close'] if p]
                except: pass
            
            if len(prices) >= 20:
                ma20 = sum(prices[-20:]) / 20
                deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
                gains = [d for d in deltas[-14:] if d > 0]
                losses = [-d for d in deltas[-14:] if d < 0]
                avg_gain = sum(gains) / 14 if gains else 0
                avg_loss = sum(losses) / 14 if losses else 1
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                trend = "Tăng" if prices[-1] > ma20 else "Giảm"
                rsi_status = "Quá Bán" if rsi < 30 else "Quá Mua" if rsi > 70 else "Trung tính"
                return f"MA20: {ma20:,.2f} ({trend}) | RSI(14): {rsi:.1f} ({rsi_status})"
        except: pass
        return "Không có dữ liệu TA."

    def get_portfolio_context(self):
        stats = self.report._process_data()
        raw_data = stats['raw_data']
        
        # NÂNG CẤP "TẦM NHÌN" CHO AI
        context = {
            "Tong_quan_tai_san": {
                "Tong_NAV": f"{stats['total_assets']:,.0f} đ",
                "Tong_loi_nhuan": f"{stats['total_pl']:,.0f} đ",
                "Von_goc_rong": f"{stats['net_cashflow']:,.0f} đ",
            },
            "Chi_tiet_cac_vi": {
                w['id']: {
                    "Suc_mua_tien_mat": f"{w['balance']:,.0f} đ",
                    "Tong_von_nap_vao_vi": f"{w['total_in']:,.0f} đ",
                } for w in raw_data['wallets']
            },
            "Danh_muc_dang_nong": [
                {
                    "ma": h['symbol'],
                    "thuoc_vi": h['wallet_id'],
                    "so_luong": h['quantity'],
                    "gia_von_trung_binh": h['average_price'],
                    "gia_thi_truong_hien_tai": h['current_price'],
                    "von_goc_vnd": h['cost_basis_vnd'],
                } for h in raw_data['holdings']
            ]
        }
        return context

    def chat_with_cfo(self, chat_id, user_message):
        for _ in range(len(self.api_keys)):
            try:
                context_data = self.get_portfolio_context()
                model = self._get_model()
                
                # Tự động dò mã trong câu hỏi của Sếp để lấy thêm dữ liệu TA
                potential_tickers = set(re.findall(r'\b[A-Z]{2,5}\b', user_message.upper()))
                if potential_tickers:
                    radar_data = {}
                    for ticker in potential_tickers:
                        ta_stock = self._get_ta_data(ticker, 'STOCK')
                        if "Không có" not in ta_stock: 
                            radar_data[ticker] = ta_stock
                            continue
                        ta_crypto = self._get_ta_data(ticker, 'CRYPTO')
                        if "Không có" not in ta_crypto:
                            radar_data[ticker] = ta_crypto
                    if radar_data:
                        context_data["Phan_tich_ky_thuat_theo_yeu_cau"] = radar_data
                
                history_text = "\n".join([f"- Sếp: {turn['user']}\n- CFO: {turn['cfo']}" for turn in self.chat_histories[chat_id]])

                system_prompt = f"""
                Bạn là CFO AI, một chuyên gia phân tích đầu tư sắc sảo và thực tế.
                
                QUY TẮC TUYỆT ĐỐI:
                1. Đi thẳng vào vấn đề, không "Chào Sếp".
                2. Dùng dữ liệu JSON bên dưới để trả lời, đặc biệt là mục "Suc_mua_tien_mat" để xem Sếp còn tiền không.
                3. Khi Sếp hỏi về một mã cụ thể, phải dùng dữ liệu "Phan_tich_ky_thuat_theo_yeu_cau" để tư vấn mua/bán.
                
                Lịch sử chat gần đây:
                {history_text}
                
                Dữ liệu tài chính của Sếp tại thời điểm này:
                {json.dumps(context_data, ensure_ascii=False, indent=2)}
                """

                response = model.generate_content(f"{system_prompt}\n\n[Sếp hỏi]: {user_message}")
                
                self.chat_histories[chat_id].append({"user": user_message, "cfo": response.text})
                if len(self.chat_histories[chat_id]) > 5: self.chat_histories[chat_id].pop(0)
                    
                return response.text
            
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                    self._switch_to_next_key()
                    continue 
                else:
                    return f"❌ [Lỗi Hệ Thống AI] LLM gặp sự cố: {str(e)}"
                    
        return "❌ [Lỗi Hệ Thống AI] Toàn bộ kho API Keys đã cạn kiệt Quota."