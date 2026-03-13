# backend/modules/price_updater.py
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor
from backend.database.repository import DatabaseRepo
from backend.modules.report import ReportModule
from backend.modules.settings import SettingsModule

class PriceUpdaterModule:
    def __init__(self, interval_minutes=30):
        self.db = DatabaseRepo()
        self.report = ReportModule()
        self.settings = SettingsModule()
        self.interval_seconds = interval_minutes * 60
        self.is_running = False

    def fetch_usd_vnd_rate(self):
        """Cào tỷ giá USD/VND từ Yahoo Finance (Uy tín, không bị chặn)"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/VND=X?region=US&lang=en-US", headers=headers, timeout=5)
            if res.status_code == 200:
                rate = float(res.json()['chart']['result'][0]['meta']['regularMarketPrice'])
                if rate > 20000:
                    self.settings.update_setting('crypto_rate', rate)
                    return rate
        except Exception as e:
            print(f"[SYNC WARN] Lỗi lấy tỷ giá USD/VND: {e}")
        return None

    def _get_realtime_price(self, symbol, wallet_type):
        """Động cơ dò giá 4 màng lọc - Đã nâng cấp chống Block IP"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*'
            }
            symbol = symbol.upper().strip()

            if wallet_type == 'CRYPTO':
                if symbol in ['USDT', 'USDC', 'FDUSD', 'BUSD']:
                    return 1.0  # Stablecoin mặc định = 1 USD

                # 1. Thử KuCoin (Vượt tường lửa Render cực mượt)
                try:
                    res = requests.get(f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}-USDT", timeout=4)
                    if res.status_code == 200 and res.json().get('data'):
                        return float(res.json()['data']['price'])
                except Exception:
                    pass
                
                # 2. Thử Yahoo Finance (Nguồn uy tín, không giới hạn IP)
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}-USD?region=US&lang=en-US"
                    res = requests.get(url, headers=headers, timeout=4)
                    if res.status_code == 200:
                        price = float(res.json()['chart']['result'][0]['meta']['regularMarketPrice'])
                        if price > 0: return price
                except Exception:
                    pass

                # 3. Thử Binance (Dự phòng cuối)
                try:
                    res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=3)
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
            return f"✅ {sym}: {price:,.2f} {'đ' if w_type == 'STOCK' else 'USD'}"
        return f"⚠️ {sym}: Không lấy được giá (Bị chặn/Sai mã)"

    def sync_all_prices(self):
        print(f"[{time.strftime('%H:%M:%S')}] 🔄 Bắt đầu tiến trình đồng bộ giá thị trường...")
        try:
            # Tự động cập nhật tỷ giá USD/VND ngầm
            self.fetch_usd_vnd_rate()
            
            stats = self.report._process_data()
            holdings = stats['raw_data']['holdings']
            
            if not holdings or len(holdings) == 0:
                print("[SYNC INFO] Danh mục trống, không cần đồng bộ.")
                return

            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(self._sync_single_symbol, holdings))
            
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
