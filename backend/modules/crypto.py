# backend/modules/crypto.py
from backend.interface import BaseModule
from backend.database.db_manager import db

class CryptoModule(BaseModule):
    def format_currency(self, value):
        """Định dạng tiền tệ VNĐ: triệu hoặc đồng"""
        abs_val = abs(value)
        sign = "+" if value > 0 else "-" if value < 0 else ""
        if abs_val >= 10**6:
            return f"{sign}{abs_val / 10**6:,.1f} triệu"
        return f"{sign}{abs_val:,.0f}đ"

    def get_group_report(self):
        """📈 BÁO CÁO HIỆU SUẤT CRYPTO - LEVEL CHUYÊN GIA"""
        EX_RATE = 26300  # Tỷ giá quy đổi USDT/VND
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Lấy giá manual (USD)
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}

            # 2. Lấy số dư từ Portfolio
            cursor.execute("SELECT * FROM portfolio WHERE user_id = ? AND asset_type = 'CRYPTO'", (self.user_id,))
            rows = cursor.fetchall()

            if not rows: return "❌ <b>Chưa có dữ liệu giao dịch CRYPTO.</b>"

            total_mkt_val_vnd = 0
            total_cost_vnd = 0
            ticker_stats = []

            for r in rows:
                if r['total_qty'] <= 0: continue
                
                # Giá hiện tại ưu tiên manual, không có lấy giá vốn trung bình (đã là USD)
                curr_p_usd = price_map.get(r['ticker'], r['avg_price'])
                
                mkt_val_vnd = r['total_qty'] * curr_p_usd * EX_RATE
                cost_vnd = r['total_qty'] * r['avg_price'] * EX_RATE # Giả định avg_price lưu dạng USD
                
                total_mkt_val_vnd += mkt_val_vnd
                total_cost_vnd += cost_vnd
                ticker_stats.append({'tk': r['ticker'], 'val': mkt_val_vnd})

            profit_vnd = total_mkt_val_vnd - total_cost_vnd
            roi = (profit_vnd / total_cost_vnd * 100) if total_cost_vnd > 0 else 0
            status = "🔥 TĂNG TRƯỞNG MẠNH" if roi > 15 else "🟢 TÍCH CỰC" if roi >= 0 else "⚠️ CẦN RÀ SOÁT"

            ticker_stats.sort(key=lambda x: x['val'], reverse=True)
            lines = [
                "📈 <b>BÁO CÁO HIỆU SUẤT CRYPTO</b>",
                "━━━━━━━━━━━━━━━━━━━",
                f"💵 <b>Giá trị hiện tại:</b> {self.format_currency(total_mkt_val_vnd).replace('+', '')}",
                f"💰 <b>Vốn ròng thực tế:</b> {self.format_currency(total_cost_vnd).replace('+', '')}",
                f"📊 <b>Tổng lãi/lỗ ròng:</b> <b>{self.format_currency(profit_vnd)}</b>",
                f"🚀 <b>Tỷ suất (ROI):</b> <b>{roi:+.2f}%</b>",
                "", "💎 <b>PHÂN BỔ TỈ TRỌNG:</b>"
            ]

            for item in ticker_stats:
                pct = (item['val'] / total_mkt_val_vnd * 100) if total_mkt_val_vnd > 0 else 0
                bar = "🔵" * int(pct/10) + "⚪" * (10 - int(pct/10))
                lines.append(f"• {item['tk']}: {pct:.1f}%\n  {bar}")

            lines.extend([
                "", 
                "━━━━━━━━━━━━━━━━━━━", 
                f"🔥 <b>TRẠNG THÁI:</b> {status}", 
                f"🏠 <i>Tỷ giá quy đổi: {EX_RATE:,.0f}đ</i>"
            ])
            return "\n".join(lines)

    def run(self):
        """📊 LAYOUT DANH MỤC CRYPTO CHI TIẾT"""
        EX_RATE = 26300
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, current_price FROM manual_prices")
            price_map = {row['ticker']: row['current_price'] for row in cursor.fetchall()}
            
            cursor.execute("SELECT * FROM portfolio WHERE user_id = ? AND asset_type = 'CRYPTO'", (self.user_id,))
            rows = cursor.fetchall()

            if not rows: return "📊 <b>DANH MỤC CRYPTO</b>\n\nChưa có dữ liệu."

            crypto_details = []
            total_val_vnd = 0
            total_cost_vnd = 0
            stats = []

            for r in rows:
                if r['total_qty'] <= 0: continue
                
                curr_p_usd = price_map.get(r['ticker'], r['avg_price'])
                val_vnd = r['total_qty'] * curr_p_usd * EX_RATE
                cost_v_vnd = r['total_qty'] * r['avg_price'] * EX_RATE
                profit_vnd = val_vnd - cost_v_vnd
                roi = (profit_vnd / cost_v_vnd * 100) if cost_v_vnd > 0 else 0
                
                total_val_vnd += val_vnd
                total_cost_vnd += cost_v_vnd
                stats.append({'ticker': r['ticker'], 'roi': roi, 'value': val_vnd})

                crypto_details.append(
                    f"<b>{r['ticker']}</b>\nSL: {r['total_qty']}\nGiá vốn TB: ${r['avg_price']:,.2f}\n"
                    f"Giá hiện tại: ${curr_p_usd:,.2f}\nGiá trị: {self.format_currency(val_vnd).replace('+', '')}\n"
                    f"Lãi: {self.format_currency(profit_vnd)} ({roi:+.1f}%)"
                )

            best = max(stats, key=lambda x: x['roi'])
            biggest = max(stats, key=lambda x: x['value'])

            lines = [
                "📊 <b>DANH MỤC CRYPTO</b>",
                f"💰 Tổng giá trị: {self.format_currency(total_val_vnd).replace('+', '')}",
                f"📈 Lãi tổng: {self.format_currency(total_val_vnd - total_cost_vnd)} ({((total_val_vnd-total_cost_vnd)/total_cost_vnd*100):+.1f}%)",
                f"🏆 Tốt nhất: {best['ticker']} ({best['roi']:+.1f}%)",
                f"📊 Tỉ trọng lớn: {biggest['ticker']}",
                "────────────", 
                "\n────────────\n".join(crypto_details), 
                "────────────"
            ]
            return "\n".join(lines)
