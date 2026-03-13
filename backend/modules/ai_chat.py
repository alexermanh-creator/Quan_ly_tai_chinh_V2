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
        
        self.cached_model_name = None 
        self.chat_histories = defaultdict(list)

    def _get_configured_model(self):
        if not self.api_keys:
            raise ValueError("⚠️ Hệ thống chưa được nạp GEMINI_API_KEYS. Sếp hãy vào Cài đặt để thêm!")
        
        genai.configure(api_key=self.api_keys[self.current_key_idx])
        
        if self.cached_model_name:
            return genai.GenerativeModel(self.cached_model_name, generation_config={"temperature": 0.2})
        
        target_model = None
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
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

        self.cached_model_name = target_model
        return genai.GenerativeModel(target_model, generation_config={"temperature": 0.2})

    def _switch_to_next_key(self):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        self.cached_model_name = None 

    def _get_realtime_price(self, symbol, wallet_type):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            symbol = symbol.upper().strip()

            if wallet_type == 'CRYPTO':
                if symbol in ['USDT', 'USDC', 'FDUSD', 'BUSD']:
                    return 1.0

                try:
                    res = requests.get(f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}-USDT", timeout=3)
                    if res.status_code == 200 and res.json().get('data'):
                        return float(res.json()['data']['price'])
                except Exception:
                    pass

                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}-USD?region=US&lang=en-US"
                    res = requests.get(url, headers=headers, timeout=3)
                    if res.status_code == 200:
                        price = float(res.json()['chart']['result'][0]['meta']['regularMarketPrice'])
                        if price > 0: return price
                except Exception:
                    pass

                try:
                    res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=3)
                    if res.status_code == 200:
                        return float(res.json()['price'])
                except Exception:
                    pass
            
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
            pass
            
        return None

    def _get_ta_data(self, symbol, wallet_type):
        try:
            prices = []
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            symbol = symbol.upper().strip()
            
            if wallet_type == 'CRYPTO':
                if symbol in ['USDT', 'USDC']:
                    return "Stablecoin: Tỷ giá neo cứng ở 1 USD"
                    
                try:
                    res = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}-USD?interval=1d&range=2mo", headers=headers, timeout=3)
                    if res.status_code == 200:
                        prices = res.json()['chart']['result'][0]['indicators']['quote'][0]['close']
                        prices = [p for p in prices if p is not None]
                except Exception:
                    pass

                if not prices:
                    try:
                        res = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1d&limit=30", timeout=3)
                        if res.status_code == 200:
                            prices = [float(k[4]) for k in res.json()]
                    except Exception:
                        pass

            elif wallet_type == 'STOCK':
                res = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.VN?interval=1d&range=2mo", headers=headers, timeout=3)
                if res.status_code == 200:
                    prices = res.json()['chart']['result'][0]['indicators']['quote'][0]['close']
                    prices = [p for p in prices if p is not None]
            
            if len(prices) >= 20:
                ma20 = sum(prices[-20:]) / 20
                
                deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
                gains = [d if d > 0 else 0 for d in deltas[-14:]]
                losses = [-d if d < 0 else 0 for d in deltas[-14:]]
                avg_gain = sum(gains) / 14 if len(gains) > 0 else 0
                avg_loss = sum(losses) / 14 if len(losses) > 0 else 0
                
                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                
                trend = "Tăng" if prices[-1] > ma20 else "Giảm (Mất nền MA20)"
                rsi_status = "Quá Bán (Hoảng loạn)" if rsi < 30 else "Quá Mua (Fomo)" if rsi > 70 else "Trung tính"
                
                return f"MA20: {ma20:,.2f} ({trend}) | RSI(14): {rsi:.1f} ({rsi_status})"
        except Exception:
            pass
        return "TA Data: Chưa rõ xu hướng"

    def _fetch_price_worker(self, item):
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
        stats = self.report._process_data()
        raw_data = stats['raw_data']
        
        tot = stats['total_assets'] if stats['total_assets'] > 0 else 1
        cash_val = stats['wallets']['CASH']['balance']
        stock_val = stats['wallets']['STOCK']['assets'] + stats['wallets']['STOCK']['balance']
        crypto_val = stats['wallets']['CRYPTO']['assets'] + stats['wallets']['CRYPTO']['balance']
        
        chi_tiet = []
        
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

        transactions = raw_data.get('transactions', [])
        total_realized = 0
        symbol_pnl = defaultdict(float)
        recent_closed_trades = []

        for tx in transactions:
            if tx['type'] in ['BAN', 'CHOT_LICH_SU'] and tx['realized_pl']:
                pl = tx['realized_pl']
                total_realized += pl
                sym = tx['symbol'] or "Lịch_Sử"
                symbol_pnl[sym] += pl
                
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

    def chat_with_cfo(self, chat_id, user_message):
        context_data = self.get_portfolio_context()
        
        words = re.findall(r'\b[a-zA-Z]{3,5}\b', user_message)
        stop_words = {'gia', 'hom', 'nay', 'thi', 'sao', 'cho', 'toi', 'cfo', 'lam', 'the', 'nao', 'mua', 'ban', 'hay', 'con', 'lai', 'nua', 'qua', 'voi', 'cua', 'nen', 'giu', 'cat', 'anh', 'nha', 'tien', 'mat', 'rut', 'nap', 'kho', 'tot', 'xau', 'cai', 'mot', 'hai', 'vay', 'nhe'}
        potential_tickers = set([w.upper() for w in words if w.lower() not in stop_words])
        
        radar_ta_data = []
        
        def _fetch_external_ta(sym):
            price = self._get_realtime_price(sym, 'STOCK')
            w_type = 'STOCK'
            if not price:
                price = self._get_realtime_price(sym, 'CRYPTO')
                w_type = 'CRYPTO'
            if price:
                ta_info = self._get_ta_data(sym, w_type)
                return {"ma": sym, "gia_hien_tai": price, "chi_bao_ky_thuat": ta_info}
            return None

        if potential_tickers:
            with ThreadPoolExecutor(max_workers=5) as executor:
                ext_results = executor.map(_fetch_external_ta, potential_tickers)
                for res in ext_results:
                    if res:
                        radar_ta_data.append(res)
                        
        if radar_ta_data:
            context_data["radar_phan_tich_ky_thuat_cac_ma_vua_hoi"] = radar_ta_data
            
        history_text = "LỊCH SỬ HỘI THOẠI TRƯỚC ĐÓ:\n"
        if self.chat_histories[chat_id]:
            for turn in self.chat_histories[chat_id]:
                history_text += f"- Sếp: {turn['user']}\n- CFO: {turn['cfo']}\n"
        else:
            history_text += "(Đây là câu hỏi đầu tiên của phiên)\n"
        
        system_prompt = f"""
        Bạn là CFO Quant Trader sát thủ. Nhiệm vụ của bạn là tư vấn quản lý tài sản và danh mục đầu tư.
        
        LỆNH TẨY NÃO (BẮT BUỘC TUÂN THỦ 100%):
        1. KHÔNG BAO GIỜ DÙNG TỪ "Chào Sếp" hay lặp lại các câu chào hỏi sáo rỗng. Hãy đi thẳng vào vấn đề.
        2. KHÔNG ĐƯỢC VIẾT HOA TOÀN BỘ CÂU HOẶC ĐOẠN VĂN. Chỉ được viết hoa tên mã cổ phiếu/coin hoặc thuật ngữ (VD: VPB, RSI, FED).
        3. KHÔNG ĐỌC ĐỊNH NGHĨA WIKIPEDIA (VD: Không được giải thích HPG là tập đoàn sản xuất thép). 
        4. BẮT BUỘC SỬ DỤNG SỐ LIỆU PHÂN TÍCH KỸ THUẬT (RSI, MA20) ở dưới để tư vấn Mua/Bán. Nếu RSI Quá Bán thì khuyên dò đáy, nếu Quá Mua thì khuyên chốt lời.
        
        {history_text}
        
        DỮ LIỆU CẬP NHẬT TẠI THỜI ĐIỂM NÀY:
        {json.dumps(context_data, ensure_ascii=False)}
        """

        for _ in range(len(self.api_keys)):
            try:
                model = self._get_configured_model()
                response = model.generate_content(f"{system_prompt}\n\n[Sếp hỏi]: {user_message}")
                
                self.chat_histories[chat_id].append({"user": user_message, "cfo": response.text})
                if len(self.chat_histories[chat_id]) > 5:
                    self.chat_histories[chat_id].pop(0)
                    
                return response.text
            
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                    self._switch_to_next_key()
                    continue 
                else:
                    return f"❌ [Lỗi Hệ Thống AI] LLM gặp sự cố: {str(e)}"
                    
        return "❌ [Lỗi Hệ Thống AI] Toàn bộ kho API Keys đã cạn kiệt Quota ngày hôm nay!"
