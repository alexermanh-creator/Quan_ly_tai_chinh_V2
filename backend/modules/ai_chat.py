# backend/modules/ai_chat.py
import os
import json
import requests
import re
from backend.database.repository import DatabaseRepo
from backend.modules.report import ReportModule

class AIChatModule:
    def __init__(self):
        self.db = DatabaseRepo()
        self.report = ReportModule()
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = "llama-3.3-70b-versatile"

    def get_portfolio_context(self):
        """MẮT THẦN: Trích xuất toàn bộ 'nội tạng' tài chính của Sếp"""
        stats = self.report._process_data()
        raw = stats['raw_data']
        
        # 1. Trạng thái Sức mua (Tiền mặt thực tế)
        cash_status = {w['id']: {
            "tien_mat_kha_dung": f"{w['balance']:,.0f} đ",
            "tong_von_da_bom": f"{w['total_in']:,.0f} đ",
            "suc_mua": "CẠN KIỆT" if w['balance'] <= 0 else "ỔN ĐỊNH"
        } for w in raw['wallets']}

        # 2. Phân tích danh mục chi tiết
        holdings = []
        for h in raw['holdings']:
            pnl_val = (h['current_price'] - h['average_price']) * h['quantity']
            pnl_pct = (pnl_val / (h['average_price'] * h['quantity']) * 100) if h['average_price'] > 0 else 0
            holdings.append({
                "ma": h['symbol'],
                "vi": h['wallet_id'],
                "sl": h['quantity'],
                "gia_von": f"{h['average_price']:,.2f}",
                "gia_thi_truong": f"{h['current_price']:,.2f}",
                "lai_lo_vnd": f"{pnl_val:,.0f} đ",
                "roi_pct": f"{pnl_pct:.1f}%",
                "canh_bao": "NGUY HIỂM" if pnl_pct < -10 else "AN TOÀN"
            })

        return {
            "TONG_NAV": f"{stats['total_assets']:,.0f} đ",
            "TONG_LAI_LO": f"{stats['total_pl']:,.0f} đ",
            "HIEU_SUAT_NAV": f"{(stats['total_pl']/stats['net_cashflow']*100 if stats['net_cashflow']>0 else 0):.1f}%",
            "STATUS_VI_TIEN": cash_status,
            "CHI_TIET_DANH_MUC": holdings
        }

    def chat_with_cfo(self, chat_id, user_message):
        if not self.api_key:
            return "❌ Sếp ơi, chưa có GROQ_API_KEY trong file .env!"

        data = self.get_portfolio_context()
        
        # PROMPT THIẾT KẾ CHO MỘT GIÁM ĐỐC TÀI CHÍNH SÁT THỦ
        system_instruction = f"""
        Bạn là CFO Quant Trader sát thủ. Bạn không phải chatbot hỗ trợ khách hàng. 
        Bạn là người quản lý tài sản trực tiếp cho Sếp Cường.
        
        DỮ LIỆU TÀI CHÍNH THỜI TIẾM THỰC:
        {json.dumps(data, ensure_ascii=False, indent=2)}
        
        QUY TẮC PHẢN HỒI (BẮT BUỘC):
        1. PHONG CÁCH: Lạnh lùng, sắc bén, đi thẳng vào số liệu. Tuyệt đối không chào hỏi 'Chào Sếp' hay 'Chúc một ngày tốt lành'.
        2. TƯ DUY SỨC MUA: Khi Sếp hỏi về việc mua thêm mã nào, hãy soi ngay 'tien_mat_kha_dung' trong ví đó. Nếu đang là 0 đ, hãy mắng Sếp và yêu cầu Sếp dùng lệnh 'nap' tiền mặt vào ví mẹ, hoặc dùng lệnh 'thu' để thu hồi vốn từ ví khác về trước khi mơ mộng mua thêm.
        3. TƯ DUY CẮT LỖ: Nếu thấy mã nào có roi_pct < -10%, hãy yêu cầu Sếp hành động ngay (Cắt lỗ hoặc Trung bình giá).
        4. KẾT LUẬN: Mỗi câu trả lời phải kết thúc bằng một LỜI KHUYÊN HÀNH ĐỘNG cụ thể (VD: 'Nạp thêm 100tr vào STOCK', 'Bán hết mã X vì quá rủi ro').
        5. NGÔN NGỮ: Tiếng Việt chuyên ngành tài chính (Quant, Margin, Entry, Drawdown, ROI).
        """

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.2 # Thấp để AI trả lời chính xác số liệu, không bốc phét
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content']
            else:
                return f"❌ Lỗi CFO AI: {res.text}"
        except Exception as e:
            return f"❌ Lỗi kết nối: {str(e)}"