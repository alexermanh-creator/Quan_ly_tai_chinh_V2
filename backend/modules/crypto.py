# backend/modules/crypto.py
from backend.interface import BaseModule
from backend.database.db_manager import db
from backend.core.registry import AssetResolver

class CryptoModule(BaseModule):
    def format_m(self, value):
        """Format số tiền theo dạng .M (Triệu) đúng yêu cầu CEO"""
        return f"{value / 1_000_000:,.1f}M"

    def run(self):
        # Lấy tỷ giá USD/VND do CEO nhập tay hoặc mặc định
        ex_rate = AssetResolver.get_custom_exchange_rate()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Lấy giá manual (USD)
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}
            
            # 2. Lấy số dư từ Portfolio
            cursor.execute("SELECT * FROM portfolio WHERE user_id = ? AND asset_type = 'CRYPTO'", (self.user_id,))
            rows = cursor.fetchall()
            
            if not rows: return "📊 <b>DANH MỤC CRYPTO</b>\n\nChưa có dữ liệu."

            # 3. Tính toán các chỉ số tổng của Ví Crypto
            total_cost_vnd = sum(r['total_qty'] * r['avg_price'] * ex_rate for r in rows)
            total_mkt_vnd = sum(r['total_qty'] * price_map.get(r['ticker'], r['avg_price']) * ex_rate for r in rows)
            
            crypto_details = []
            stats = []

            for r in rows:
                tk = r['ticker']
                curr_p_usd = price_map.get(tk, r['avg_price'])
                
                mkt_val_vnd = r['total_qty'] * curr_p_usd * ex_rate
                cost_val_vnd = r['total_qty'] * r['avg_price'] * ex_rate
                pnl_vnd = mkt_val_vnd - cost_val_vnd
                roi = (pnl_vnd / cost_val_vnd * 100) if cost_val_vnd > 0 else 0
                
                stats.append({'ticker': tk, 'roi': roi, 'value': mkt_val_vnd})
                
                # Layout chi tiết mã với dấu $ cho giá USD và .M cho giá trị VND
                detail = (
                    f"💎 <b>{tk}</b>\n"
                    f"• SL: {r['total_qty']:.6f} | Vốn TB: ${r['avg_price']:,.2f}\n"
                    f"• Hiện tại: ${curr_p_usd:,.2f} | GT: {self.format_m(mkt_val_vnd)}\n"
                    f"• Lãi: {self.format_m(pnl_vnd)} ({roi:+.1f}%)"
                )
                crypto_details.append(detail)

            best = max(stats, key=lambda x: x['roi'])
            worst = min(stats, key=lambda x: x['roi'])
            biggest = max(stats, key=lambda x: x['value'])

        # Giao diện đồng bộ với Stock
        lines = [
            "📊 <b>DANH MỤC CRYPTO</b>",
            "━━━━━━━━━━━━━━━━━━━",
            f"💰 Tổng giá trị: {self.format_m(total_mkt_vnd)}",
            f"💵 Tổng vốn: {self.format_m(total_cost_vnd)}",
            f"📈 Lãi/Lỗ: {self.format_m(total_mkt_vnd - total_cost_vnd)} ({((total_mkt_vnd-total_cost_vnd)/total_cost_vnd*100):+.1f}%)",
            f"⬆️ Tổng nạp ví: {self.format_m(total_cost_vnd)}",
            f"⬇️ Tổng rút ví: 0đ",
            f"🏆 Mã tốt nhất: {best['ticker']} ({best['roi']:+.1f}%)",
            f"📉 Mã kém nhất: {worst['ticker']} ({worst['roi']:+.1f}%)",
            f"📊 Tỉ trọng lớn nhất: {biggest['ticker']} ({(biggest['value']/total_mkt_vnd*100):.1f}%)",
            "────────────",
            "\n────────────\n".join(crypto_details),
            "━━━━━━━━━━━━━━━━━━━",
            f"🏠 <i>Tỷ giá quy đổi: {ex_rate:,.0f}đ</i>"
        ]
        return "\n".join(lines)
