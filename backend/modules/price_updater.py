# backend/modules/price_updater.py
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor
from backend.database.repository import DatabaseRepo

class PriceUpdaterModule:
    def __init__(self, interval_minutes=30):
        self.db = DatabaseRepo()
        self.interval_seconds = interval_minutes * 60
        self.is_running = False

    def _get_realtime_price(self, symbol, wallet_type):
        """Động cơ dò giá 4 màng lọc (Tái sử dụng siêu việt)"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*'
            }
            symbol = symbol.upper().strip()

            if wallet_type == 'CRYPTO':
                try:
                    res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=5)
                    if res.status_code == 200:
                        return float(res.json()['price'])
                except Exception:
                    pass
            
            elif wallet_type == 'STOCK':
                # Yahoo Finance
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.VN?region=US&lang=en-US"
                    res = requests.get(url, headers=headers, timeout=5)
                    if res.status_code == 200:
                        price = float(res.json()['chart']['result'][0]['meta']['regularMarketPrice'])
                        if price > 0:
                            return price if price >= 1000 else price * 1000
                except Exception:
                    pass

                # VNDirect
                try:
                    res = requests.get(f"https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date:desc&q=code:{symbol}&size=1", headers=headers, timeout=4)
                    if res.status_code == 200:
                        data = res.json().get('data', [])
                        if data:
                            price = float(data[0]['close'])
                            return price * 1000 if price < 1000 else price
                except Exception:
                    pass

                # TCBS
                try:
                    res = requests.get(f"https://apipubaws.tcbs.com.vn/tca-api/v1/ticker/{symbol}/overview", headers=headers, timeout=4)
                    if res.status_code == 200:
                        price = float(res.json().get('price', 0))
                        if price > 0:
                            return price * 1000 if price < 1000 else price
                except Exception:
                    pass

        except Exception as e:
            print(f"[SYNC WARN] Lỗi hệ thống khi quét giá {symbol}: {e}")
            
        return None

    def _sync_single_symbol(self, item):
        sym = item['symbol']
        w_type = item['wallet_id']
        price = self._get_realtime_price(sym, w_type)
        
        if price:
            self.db.update_market_price(sym, price)
            return f"✅ {sym}: {price:,.0f} đ"
        return f"❌ {sym}: Lỗi kết nối / Mã không tồn tại"

    def sync_all_prices(self):
        print(f"[{time.strftime('%H:%M:%S')}] 🔄 Bắt đầu tiến trình đồng bộ giá thị trường...")
        try:
            # FIX LỖI DANH MỤC TRỐNG: Lấy toàn bộ mã trong sổ, không quan tâm quantity
            rows = self.db.execute_query("SELECT DISTINCT symbol, wallet_id FROM holdings", fetch_one=False)
            
            if not rows or len(rows) == 0:
                print("[SYNC INFO] Danh mục trống, không cần đồng bộ.")
                return

            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(self._sync_single_symbol, rows))
            
            for res in results:
                print(f"[SYNC RESULT] {res}")
            print("[SYNC SUCCESS] Đã cập nhật xong bảng giá Database!")
            
        except Exception as e:
            print(f"[SYNC ERROR] Lỗi trong quá trình đồng bộ: {e}")

    def _worker(self):
        """Hàm chạy ngầm vô tận"""
        while self.is_running:
            self.sync_all_prices()
            time.sleep(self.interval_seconds)

    def start_background_sync(self):
        """Kích hoạt tiến trình chạy ngầm"""
        if not self.is_running:
            self.is_running = True
            thread = threading.Thread(target=self._worker, daemon=True)
            thread.start()
            print(f"🚀 [HỆ THỐNG] Đã khởi động Module Auto-Sync Giá (Mỗi {self.interval_seconds // 60} phút/lần).")
