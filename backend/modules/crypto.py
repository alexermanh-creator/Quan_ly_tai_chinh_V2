# backend/modules/crypto.py
from backend.database.repository import DatabaseRepo
from backend.utils.formatter import format_currency, format_percent, draw_line

class CryptoModule:
    def __init__(self):
        self.db = DatabaseRepo()

    def get_dashboard(self):
        try:
            data = self.db.get_dashboard_data()
            w = next((x for x in data['wallets'] if x['id'] == 'CRYPTO'), {'total_in':0, 'total_out':0, 'balance':0})
            holdings = [h for h in data['holdings'] if h['wallet_id'] == 'CRYPTO']
            
            rate_row = self.db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
            rate = float(rate_row['value']) if rate_row else 25000.0

            # 1. Tính toán giá trị bằng VNĐ (Sức mua w['balance'] đã là VNĐ)
            gt_thi_truong_vnd = sum(h['quantity'] * (h['current_price'] or h['average_price']) * rate for h in holdings)
            nav_vnd = w['balance'] + gt_thi_truong_vnd
            von_rong_vnd = w['total_in'] - w['total_out']
            
            # Lãi Lỗ tính theo VNĐ
            real_pl_vnd = data['realized'].get('CRYPTO', 0)
            float_pl_vnd = gt_thi_truong_vnd - sum(h['quantity'] * h['average_price'] * rate for h in holdings)
            pl_tong_vnd = real_pl_vnd + float_pl_vnd

            # 2. Quy đổi sang USD để hiển thị thêm
            nav_usd = nav_vnd / rate if rate > 0 else 0
            von_rong_usd = von_rong_vnd / rate if rate > 0 else 0
            balance_usd = w['balance'] / rate if rate > 0 else 0 # Chia tỷ giá để ra USDT

            # 3. Lọc mã tốt/kém (Chỉ lấy mã của ví CRYPTO)
            best_info, worst_info, max_sym, max_pct = "--", "--", "--", 0
            perf_list = []
            
            # Lọc chỉ lấy perf_symbols của CRYPTO
            perf_map = {p['symbol']: {'pl': p['realized'], 'inv': p['total_invested']} 
                        for p in data['perf_symbols'] if p['wallet_id'] == 'CRYPTO'}
            
            for h in holdings:
                f_pl = h['quantity'] * ((h['current_price'] or h['average_price']) - h['average_price']) * rate
                if h['symbol'] in perf_map: perf_map[h['symbol']]['pl'] += f_pl
                else: perf_map[h['symbol']] = {'pl': f_pl, 'inv': h['quantity'] * h['average_price'] * rate}

            if perf_map:
                for s, v in perf_map.items():
                    roi = (v['pl']/v['inv']*100 if v['inv']>0 else 0)
                    perf_list.append({'sym': s, 'roi': roi, 'amt': v['pl']})
                
                if perf_list:
                    best = max(perf_list, key=lambda x: x['roi'])
                    best_info = f"{best['sym']} ({format_percent(best['roi'])}) ({'+' if best['amt']>0 else ''}{format_currency(best['amt'])})"
                    worst = min(perf_list, key=lambda x: x['roi'])
                    worst_info = f"{worst['sym']} ({format_percent(worst['roi'])})"
                
                if holdings:
                    max_h = max(holdings, key=lambda x: x['quantity'] * (x['current_price'] or x['average_price']))
                    p_current = max_h['current_price'] or max_h['average_price']
                    max_pct = (max_h['quantity'] * p_current * rate / nav_vnd * 100) if nav_vnd > 0 else 0
                    max_sym = max_h['symbol']

            lines = [
                f"🪙 DANH MỤC TIỀN ĐIỆN TỬ (Rate: {rate:,.0f}đ)", draw_line("thick"),
                f"💰 Tổng giá trị: {format_currency(nav_vnd)} (~{nav_usd:,.0f} USDT)",
                f"🏦 Tổng vốn: {format_currency(von_rong_vnd)} (~{von_rong_usd:,.0f} USDT)",
                f"💸 Sức mua: {format_currency(w['balance'])} (~{balance_usd:,.0f} USDT)",
                f"📈 Lãi/Lỗ: {format_currency(pl_tong_vnd)} ({format_percent(pl_tong_vnd/von_rong_vnd*100 if von_rong_vnd>0 else 0)})",
                f"⬆️ Tổng nạp ví: {format_currency(w['total_in'])}",
                f"⬇️ Tổng rút ví: {format_currency(w['total_out'])}",
                f"🏆 Mã tốt nhất: {best_info}",
                f"📉 Mã kém nhất: {worst_info}",
                f"📊 Tỉ trọng lớn nhất: {max_sym} ({max_pct:.1f}%)",
                draw_line("thin")
            ]

            if not holdings:
                lines.append("• Danh mục hiện tại đang trống.")
            else:
                for h in holdings:
                    p_now = h['current_price'] or h['average_price']
                    roi = ((p_now / h['average_price']) - 1) * 100
                    gt_vnd = h['quantity'] * p_now * rate
                    lines += [
                        f"💎 {h['symbol']}",
                        f"• SL: {h['quantity']:.4f} | Vốn TB: {h['average_price']:,.2f} $",
                        f"• Hiện tại: {p_now:,.2f} $ | GT: {format_currency(gt_vnd)}",
                        f"• Lãi: {format_currency(gt_vnd - (h['quantity']*h['average_price']*rate))} ({format_percent(roi)})",
                        draw_line("thin")
                    ]
            lines.append(draw_line("thick"))
            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Crypto: {str(e)}"

    def get_group_report(self):
        try:
            data = self.db.get_dashboard_data()
            w = next((x for x in data['wallets'] if x['id'] == 'CRYPTO'), {'total_in':0, 'total_out':0, 'balance':0})
            holdings = [h for h in data['holdings'] if h['wallet_id'] == 'CRYPTO']
            
            rate_row = self.db.execute_query("SELECT value FROM settings WHERE key = 'crypto_rate'", fetch_one=True)
            rate = float(rate_row['value']) if rate_row else 25000.0

            gt_thi_truong_vnd = sum(h['quantity'] * (h['current_price'] or h['average_price']) * rate for h in holdings)
            nav = w['balance'] + gt_thi_truong_vnd # Đã sửa bỏ nhân rate
            von_rong = w['total_in'] - w['total_out']
            real_pl = data['realized'].get('CRYPTO', 0)
            float_pl = gt_thi_truong_vnd - sum(h['quantity'] * h['average_price'] * rate for h in holdings)
            pl_tong = real_pl + float_pl

            # Lọc chỉ lấy lịch sử của CRYPTO
            perf_symbols = [p for p in data.get('perf_symbols', []) if p['wallet_id'] == 'CRYPTO']
            win_list = sorted([p for p in perf_symbols if p['realized'] > 0], key=lambda x: x['realized'], reverse=True)
            loss_list = sorted([p for p in perf_symbols if p['realized'] < 0], key=lambda x: x['realized'])

            all_tx = self.db.execute_query("SELECT type, amount FROM transactions WHERE wallet_id = 'CRYPTO'", fetch_all=True)
            total_buy = abs(sum(t['amount'] for t in all_tx if t['type'] == 'MUA'))
            total_sell = sum(t['amount'] for t in all_tx if t['type'] == 'BAN')

            max_sym, max_pct = "--", 0
            best_info, worst_info = "--", "--"
            if holdings:
                max_h = max(holdings, key=lambda x: x['quantity'] * (x['current_price'] or x['average_price']))
                max_sym = max_h['symbol']
                max_pct = (max_h['quantity'] * (max_h['current_price'] or max_h['average_price']) * rate / nav * 100) if nav > 0 else 0
                
                h_perf = []
                for h in holdings:
                    roi = (((h['current_price'] or h['average_price']) / h['average_price']) - 1) * 100
                    h_perf.append({'s': h['symbol'], 'r': roi})
                b_h = max(h_perf, key=lambda x: x['r'])
                w_h = min(h_perf, key=lambda x: x['r'])
                best_info = f"{b_h['s']} ({format_percent(b_h['r'])})"
                worst_info = f"{w_h['s']} ({format_percent(w_h['r'])})"

            lines = [
                "📑 BÁO CÁO TÀI CHÍNH: CRYPTO", draw_line("thick"),
                "📊 DANH MỤC COIN",
                f"💰 Tổng giá trị: {format_currency(nav)}",
                f"💵 Tổng vốn: {format_currency(von_rong)}",
                f"💸 Sức mua (VNĐ): {format_currency(w['balance'])}",
                f"📈 Lãi/Lỗ: {format_currency(pl_tong)} ({format_percent(pl_tong/von_rong*100 if von_rong>0 else 0)})",
                f"⬆️ Tổng nạp ví: {format_currency(w['total_in'])}",
                f"⬇️ Tổng rút ví: {format_currency(w['total_out'])}",
                f"🏆 Mã tốt nhất: {best_info}",
                f"📉 Mã kém nhất: {worst_info}",
                f"📊 Tỉ trọng lớn nhất: {max_sym} ({max_pct:.1f}%)",
                draw_line("thin"),
                "🔄 HOẠT ĐỘNG GIAO DỊCH (VNĐ):",
                f"🛒 Tổng mua: {format_currency(total_buy)}",
                f"💰 Tổng bán: {format_currency(total_sell)}",
                "",
                "🏆 Top Đóng Góp (Lãi chốt):"
            ]

            if win_list:
                for i, p in enumerate(win_list[:3], 1):
                    lines.append(f"{i}. {p['symbol']}: +{format_currency(p['realized'])}")
            else:
                lines.append("• Chưa có dữ liệu lãi.")

            lines.append("⚠️ Top Kéo Lùi (Lỗ chốt):")
            if loss_list:
                for p in loss_list[:3]:
                    lines.append(f"• {p['symbol']}: {format_currency(p['realized'])}")
            else:
                lines.append("• Chưa có dữ liệu lỗ.")

            lines += [draw_line("thin"), "📊 CHI TIẾT DANH MỤC HIỆN TẠI:"]
            if not holdings:
                lines.append("• Trống")
            else:
                for h in holdings:
                    roi = (((h['current_price'] or h['average_price']) / h['average_price']) - 1) * 100
                    gt_vnd = h['quantity']*(h['current_price'] or h['average_price']) * rate
                    lines.append(f"• {h['symbol']}: ROI {format_percent(roi)} | GT: {format_currency(gt_vnd)}")

            return "\n".join(lines)
        except Exception as e: return f"❌ Lỗi Báo cáo Crypto: {str(e)}"
