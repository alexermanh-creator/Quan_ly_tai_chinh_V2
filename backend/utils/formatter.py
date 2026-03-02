def format_currency(amount):
    """Chuyển đổi số thành chữ Triệu, Tỷ cho dễ đọc trên UI"""
    if amount == 0:
        return "0 đ"
    
    abs_amount = abs(amount)
    sign = "-" if amount < 0 else ""
    
    if abs_amount >= 1_000_000_000:
        return f"{sign}{abs_amount / 1_000_000_000:,.2f} tỷ"
    elif abs_amount >= 1_000_000:
        return f"{sign}{abs_amount / 1_000_000:,.1f} triệu"
    else:
        return f"{sign}{abs_amount:,.0f} đ"

def format_percent(percent):
    """Format phần trăm có dấu + - và màu sắc"""
    if percent > 0:
        return f"🟢 +{percent:.1f}%"
    elif percent < 0:
        return f"🔴 {percent:.1f}%"
    return "0.0%"

def draw_line(style="thick"):
    """Vẽ đường kẻ phân cách"""
    if style == "thick":
        return "━━━━━━━━━━━━━━━━━━━"
    return "────────────"
