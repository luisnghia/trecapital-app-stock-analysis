"""Weekly Plan V9 source-faithful scoring wording.

Keeps the V8 feature set while using the exact 1–5 quality descriptions from the
v1.2 specification, without adding interpretation to the scale.
"""
from __future__ import annotations

from typing import Callable, Optional

from khdn_apps import weekly_plan_v8 as v8


QUALITY_SCALE_V12 = [
    (5, "Vượt yêu cầu", "Kết quả tốt hơn dự kiến, không phải chỉnh sửa, có sáng kiến cải tiến"),
    (4, "Đạt đầy đủ yêu cầu", "Đúng hạn, chất lượng tốt"),
    (3, "Đạt yêu cầu cơ bản", "Còn phải chỉnh sửa nhỏ"),
    (2, "Chưa đạt một phần", "Phải làm lại hoặc có người hỗ trợ mới hoàn thành"),
    (1, "Không đạt yêu cầu", ""),
]


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    v8.QUALITY_SCALE = QUALITY_SCALE_V12
    return v8.weekly_plan_page(u, get_conn, page_title, pill_nav)
