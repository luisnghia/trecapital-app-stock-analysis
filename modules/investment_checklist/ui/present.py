from __future__ import annotations

ASSESSMENT_LABELS = {
    -2: "🔴 -2 Rất xấu",
    -1: "🟠 -1 Đáng lo",
     0: "⚪ 0 Trung tính",
     1: "🟢 +1 Tốt",
     2: "🟢 +2 Rất tốt",
}
STATUS_LABELS = {
    "answered": "Đã trả lời",
    "research_gap": "Research Gap / Chưa đủ thông tin",
    "needs_review": "Cần xem lại",
    "na": "N/A",
    "not_reviewed": "Chưa review",
}
SCREENING_SYMBOL = {"yes": "✓", "no": "X", "unknown": "—", "na": "N/A"}
THESIS_SYMBOL = {"up": "↑", "flat": "→", "down": "↓", "unknown": "?"}

def fmt_ratio(v):
    return "—" if v is None else f"{v:.1f}x"

def fmt_pct(v):
    return "—" if v is None else f"{v*100:.1f}%"

def fmt_vnd_bn(v):
    return "—" if v is None else f"{v:,.0f}"

def fmt_price(v):
    return "—" if v is None else f"{v:,.0f}"
