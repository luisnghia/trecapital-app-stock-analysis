from __future__ import annotations

"""Formula/assumption registry for the Watchlist + analyst correction extension.

This file exists because Trecapital project rules require every calculation extension to have an
explicit formula/audit explanation. It does not replace the core Table 1.2 formula registry.
"""

WATCHLIST_FORMULA_ROWS = [
    {
        "Nhóm": "Watchlist",
        "Chỉ tiêu": "CAGR Doanh thu 5 năm",
        "Công thức/logic": "CAGR DT 5Y = (Revenue FY_latest / Revenue FY_latest-5)^(1/5) − 1.",
        "Giả định / giới hạn": "Chỉ dùng hai FY canonical cách nhau đúng 5 năm; không dùng TTM làm endpoint. Nếu thiếu một endpoint hoặc endpoint ≤ 0 thì để Unknown.",
        "Nguồn": "Trecapital implementation; dữ liệu từ canonical annual Data Layer",
    },
    {
        "Nhóm": "Watchlist",
        "Chỉ tiêu": "CAGR Lợi nhuận 5 năm",
        "Công thức/logic": "CAGR LN 5Y = (Net Profit FY_latest / Net Profit FY_latest-5)^(1/5) − 1.",
        "Giả định / giới hạn": "Không tính CAGR chuẩn khi một trong hai endpoint lợi nhuận ≤ 0 hoặc đổi dấu; để Unknown thay vì tạo phần trăm gây hiểu nhầm.",
        "Nguồn": "Trecapital implementation; dữ liệu từ canonical annual Data Layer",
    },
    {
        "Nhóm": "Watchlist",
        "Chỉ tiêu": "Kỳ Table 1.2 hiệu lực",
        "Công thức/logic": "Watchlist lấy Table 1.2 snapshot/version mới nhất thuộc đúng research review mới nhất của từng doanh nghiệp.",
        "Giả định / giới hạn": "Nếu review mới nhất chưa có Table 1.2 thì để trống; không lấy lùi snapshot review cũ và giả là dữ liệu của review mới.",
        "Nguồn": "Trecapital workflow + Shearn Opportunity Inventory",
    },
    {
        "Nhóm": "Analyst correction",
        "Chỉ tiêu": "Effective cell",
        "Công thức/logic": "Effective value = Analyst correction mới nhất nếu có; nếu không có = Trecapital automatic/source value.",
        "Giả định / giới hạn": "Correction là append-only overlay có version + reason + actor; không mutate canonical Data Layer hoặc immutable completed review. Ô correction tô vàng hoa mai.",
        "Nguồn": "Trecapital analyst workflow extension",
    },
]
