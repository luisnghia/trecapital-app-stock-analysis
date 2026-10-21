"""Regression checks: two-line operational tables on all four permission routes."""
from __future__ import annotations

import re
import unittest
from unittest.mock import patch

import pandas as pd

from khdn_apps.operational_review_table import (
    TABLE_CSS, _task_column_layout, choose_row, render_readonly_table, selectable_task_table,
)


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.output = []

    def html(self, text):
        self.output.append(text)

    def caption(self, text):
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
        assert 1550 <= width <= 2300, "Task columns must fit content and scroll rather than squeeze"
        assert "<col style='width:92px'>" in cols, "CIF should be compact"
        assert "<col style='width:112px'>" in cols, "Numeric value should be compact"
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
                assert "<table class='ops-review-table' style='width:900px" not in doc
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

    def test_value_immediately_after_customer_on_every_role_route(self):
        base = pd.DataFrame([{
            "id": 17, "current_round": 1, "status": "OPEN",
            "cif": "7609338", "customer_name": self.customer,
            "amount_vnd": 4_590_000_000,
            "support_name": "LE DUC SON", "qlkh_name": "LE QUANG HOA",
            "task_type": "Mua bán ngoại tệ", "assigned_at": "2026-10-21 10:43:00",
            "start_time": None, "end_time": None, "status_label": "Đang thực hiện",
        }])
        st = _FakeStreamlit()
        app_ns = {
            "st": st, "enrich_tasks": lambda d: d,
            "_task_list_height": lambda n: 540, "fmt_dt": str,
            "_workflow_delay_targets": lambda: {},
            "_phase_delay_info": lambda row, targets: {
                "phase": "Đang xử lý", "elapsed": 3, "level": "Rất chậm"},
            "_minutes_human": lambda x: str(x),
        }
        for role_key in ("accept_task_table", "qlkh_assigned_table",
                         "leader_manage_table", "admin_task_table"):
            with self.subTest(role=role_key):
                for include_phase in (False, True):
                    with patch("khdn_apps.operational_review_table.choose_row",
                               side_effect=lambda _st, rows, display, key, **kwargs: display):
                        table = selectable_task_table(
                            app_ns, base, role_key, include_phase=include_phase)
                    assert list(table.columns[:4]) == [
                        "CIF", "Khách hàng", "Giá trị (tỷ đồng)", "Cán bộ hỗ trợ"]
                    assert table.iloc[0]["Giá trị (tỷ đồng)"] == "5"
                    assert table.iloc[0]["Công việc"] == "Mua bán ngoại tệ"


if __name__ == "__main__":
    unittest.main()
