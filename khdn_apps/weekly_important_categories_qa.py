"""Business cases for distinct weekly focus categories and the live submit gate."""
from __future__ import annotations

from datetime import date, timedelta

from khdn_apps import weekly_priority_policy_patch as policy


def _items(category_ids):
    return [
        {
            "id": index + 1,
            "title": f"Công việc khách hàng {index + 1}",
            "work_date": (date(2026, 10, 5) + timedelta(days=index % 7)).isoformat(),
            "status": "PLANNED",
            "priority_quadrant": 2,
            "focus_category_id": category_id,
            "is_emergent": 0,
        }
        for index, category_id in enumerate(category_ids)
    ]


def run():
    cases = {
        "empty": ([], 0),
        "different_tasks_same_category": (_items([10, 10, 10]), 1),
        "different_days_same_category": (_items([10] * 7), 1),
        "three_categories_with_duplicate_tasks": (_items([10, 10, 20, 30]), 3),
        "same_task_title_different_categories": (
            [dict(x, title="Gặp khách hàng") for x in _items([10, 20, 30])], 3
        ),
        "numeric_category_id_normalization": (_items([10, "10", 20]), 2),
        "completed_category_counts": (
            [dict(x, status="DONE") for x in _items([10, 20, 30])], 3
        ),
        "cancelled_category_excluded": (
            _items([10, 20]) + [dict(_items([30])[0], status="CANCELLED")], 2
        ),
        "missing_category_excluded": (_items([None, None, 0]), 0),
        "non_q2_excluded": (
            [dict(x, priority_quadrant=q) for x, q in zip(_items([10, 20, 30]), [1, 3, 4])], 0
        ),
    }
    for name, (items, expected) in cases.items():
        actual = policy._q2_focus_count(items)
        assert actual == expected, (name, actual, expected)

    from streamlit.testing.v1 import AppTest

    ui_cases = [
        ("duplicate_tasks_blocked", _items([10, 10, 10]), "1 mục", True),
        ("two_categories_blocked", _items([10, 10, 20]), "2 mục", True),
        ("three_categories_allowed", _items([10, 10, 20, 30]), "3 mục", False),
        ("cancelled_third_category_blocked", cases["cancelled_category_excluded"][0], "2 mục", True),
        ("uncategorized_q2_blocked", _items([None, None, None]), "0 mục", True),
        ("seven_task_limit_preserved", _items([10, 20, 30, 40, 50, 60, 70, 80]), "8 mục", True),
    ]
    for name, items, expected_value, disabled in ui_cases:
        # Render the actual policy renderer with the final summary installed.
        # Unrelated cards/add forms are omitted; no database or push is touched.
        script = f"""
import streamlit as st
from datetime import date
from unittest.mock import patch
from khdn_apps import weekly_plan as core
from khdn_apps import weekly_priority_policy_patch as policy
from khdn_apps import weekly_plan_form_refinement_patch as form
form.install(policy, core, None)
with patch.object(policy, '_drift_warning'), patch.object(policy, '_add_item_form'), \
     patch.object(policy, '_carry_forward_ui'), patch.object(policy, '_item_card'):
    policy._render_staff_week(
        st, {{'id': 2}}, core, None, date(2026, 10, 5),
        {{'id': 1, 'workflow_status': 'NHAP'}}, {items!r}, []
    )
"""
        page = AppTest.from_string(script, default_timeout=15).run()
        assert not page.exception, (name, [x.message for x in page.exception])
        metric = next(x for x in page.metric if x.label == policy.PRIORITY_SHORT[2])
        assert metric.value == expected_value, (name, metric.value)
        assert f"{sum(x['status'] != 'CANCELLED' for x in items)} việc" in metric.delta, (name, metric.delta)
        assert "100% số việc" in metric.delta, (name, metric.delta)
        submit = next(x for x in page.button if x.label == "📤 Nộp kế hoạch")
        assert submit.disabled == disabled, (name, submit.disabled)
        if policy._q2_focus_count(items) < 3:
            assert any("3 mục công việc trọng tâm Q2 khác nhau" in x.value for x in page.error), name
        else:
            assert not page.error, (name, [x.value for x in page.error])

    print("WEEKLY_IMPORTANT_CATEGORIES_QA_PASS", {"business_cases": len(cases), "submit_and_summary_cases": len(ui_cases)})


if __name__ == "__main__":
    run()
