"""Regression checks: two-line operational tables on all four permission routes."""
from __future__ import annotations

import re
import unittest
from unittest.mock import patch

import pandas as pd

from khdn_apps.operational_review_table import (
    TABLE_CSS, _task_column_layout, choose_row, render_readonly_table,
)


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.output = []

    def html(self, text):
        self.output.append(text)


class OperationalTaskTableLayoutQA(unittest.TestCase):
    def setUp(self):
        self.customer = "8774554 - CÔNG TY CỔ PHẦN LÂM ĐẶC SẢN XUẤT KHẨU QUẢNG NAM"
        self.rows = pd.DataFrame([{"id": 17, "current_round": 1, "status": "OPEN"}])
        self.display = pd.DataFrame([{
            "CIF": "8774554", "Khách hàng": self.customer,
            "Cán bộ hỗ trợ": "NGUYEN HA DUNG",
            "Cán bộ quản lý khách hàng": "NGUYEN VAN THANH",
            "Công việc": "Khác", "Giá trị (tỷ đồng)": "52",
            "Thời gian giao": "08:08 18/10/2026",
            "Bắt đầu": "14:52 18/10/2026", "Kết thúc": "—",
            "Mốc đang chờ": "Đang xử lý", "Thời gian đang chờ": "3n 18g",
            "Mức độ trễ": "Rất chậm", "Trạng thái": "Đang thực hiện",
        }])

    def test_widths_fit_two_lines_with_scroll(self):
        cols, width = _task_column_layout(self.display)
        assert cols.count("<col style=") == len(self.display.columns)
        assert width >= 2000, "13-column task table must scroll, not squeeze columns"
        assert "-webkit-line-clamp:2" in TABLE_CSS
        assert ".ops-review-table[data-ops-table] .ops-cell-text" in TABLE_CSS
        assert "overflow-x:auto" in TABLE_CSS
        assert "ops-history-table{min-width:0}" in TABLE_CSS

    def test_all_permission_views_share_the_same_safe_layout(self):
        for key in ("accept_task_table", "qlkh_assigned_table",
                    "leader_manage_table", "admin_task_table"):
            with self.subTest(permission=key):
                st = _FakeStreamlit()
                with patch("khdn_apps.operational_review_table._row_click_event", return_value=None):
                    result = choose_row(st, self.rows, self.display, key)
                assert result is None
                doc = st.output[-1]
                assert "class='ops-review-table' style='width:" in doc
                assert "<colgroup>" in doc
                assert "min-width:100%" in doc
                assert "data-ops-row='17'" in doc
                assert doc.count("class='ops-cell-text'") == len(self.display.columns) * 2
                assert self.customer in doc, "Full customer data must remain in the DOM"
                assert "title='" + self.customer + "'" in doc
                assert "width:900px" not in doc
                assert "-webkit-line-clamp:2" in doc

    def test_dynamic_width_is_bounded_and_history_remains_unclamped(self):
        frame = self.display.copy()
        original_width = _task_column_layout(frame)[1]
        frame.loc[0, "Khách hàng"] = "C" * 500
        new_width = _task_column_layout(frame)[1]
        assert original_width <= new_width <= original_width + 230
        st = _FakeStreamlit()
        render_readonly_table(st, pd.DataFrame([{"Thời gian": "10:00", "Người thực hiện": "CBHT",
                                                 "Hành động": "Đánh giá", "Chi tiết": "A" * 500}]))
        doc = st.output[-1]
        assert "ops-history-table" in doc
        assert "A" * 500 in doc
        assert not re.search(r"<table class='ops-review-table' style='width:", doc)


if __name__ == "__main__":
    unittest.main()
