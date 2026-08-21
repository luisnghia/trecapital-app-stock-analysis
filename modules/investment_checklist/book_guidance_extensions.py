from __future__ import annotations

"""Small derived guidance overlays for app tables that extend Shearn's source tables."""

from .book_guidance import BOOK_GUIDANCE, _g


BOOK_GUIDANCE["Watchlist — Opportunity Inventory"] = {
    "source": "Chương 1 · Table 1.2 — Inventory of Ideas; CAGR columns are a Trecapital tracking extension",
    "purpose": (
        "Giữ một inventory các doanh nghiệp đã qua bộ lọc, theo dõi valuation và operating/financial history để biết "
        "nơi nào đáng dành thêm thời gian nghiên cứu. CAGR trong app bổ sung bối cảnh lịch sử, không phải forecast."
    ),
    "principles": BOOK_GUIDANCE["Table 1.2"]["principles"] + (
        "Historical CAGR chỉ mô tả quá khứ; Shearn nhấn mạnh không được ngoại suy thành future growth nếu chưa kiểm tra runway và economics.",
    ),
    "metrics": {
        **BOOK_GUIDANCE["Table 1.2"]["metrics"],
        "Mã CP": _g("Mã định danh doanh nghiệp trong inventory.", "Dùng để mở đúng research workspace.", "Metadata, không phải chỉ tiêu đầu tư."),
        "Doanh nghiệp": _g("Tên doanh nghiệp đang theo dõi.", "Luôn gắn metric với đúng business economics/industry.", "Metadata, không phải chỉ tiêu đầu tư."),
        "Kỳ dữ liệu": _g("Kỳ tài chính mới nhất mà Watchlist đang sử dụng.", "Kiểm tra độ mới trước khi so sánh giữa các mã.", "Hai doanh nghiệp khác kỳ dữ liệu có thể không comparable hoàn toàn."),
        "CAGR DT 5Y": _g("Tăng trưởng doanh thu kép lịch sử 5 năm.", "Kiểm tra nguồn tăng trưởng: volume/price/acquisition, profitability và runway còn lại.", "Historical CAGR không phải future growth rate; không ngoại suy máy móc."),
        "CAGR LN 5Y": _g("Tăng trưởng lợi nhuận kép lịch sử 5 năm.", "So với revenue CAGR, margins, ROIC, share count và operating driver để biết chất lượng tăng trưởng.", "Profit CAGR cao từ low base, cycle peak hoặc cost cutting có thể không bền."),
        "CAGR kỳ": _g("Khoảng FY dùng để tính CAGR.", "Đảm bảo endpoints comparable và đủ 5 năm.", "Metadata của phép tính, không phải investment signal."),
    },
}
