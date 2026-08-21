import pandas as pd

import modules.investment_checklist.ui as checklist_ui  # noqa: F401 - applies package timeline policy
from modules.investment_checklist.ui import page


def test_ttm_sort_key_is_always_newer_than_review_dates():
    assert page._period_sort_date("TTM", "TTM") > page._period_sort_date("2099-12-31")
    assert page._period_sort_date("T12M", "2026-08-21") > page._period_sort_date("2026-08-21")


def test_mixed_proxy_review_timeline_places_ttm_first_then_newest_dates():
    rows = pd.DataFrame([
        {"period": "2025", "kind": 0, "version": 0},
        {"period": "TTM", "kind": 0, "version": 0},
        {"period": "2026-08-21", "kind": 1, "version": 2},
        {"period": "2026-08-21", "kind": 1, "version": 1},
        {"period": "2024", "kind": 0, "version": 0},
    ])
    rows["sort_date"] = rows["period"].map(lambda x: page._period_sort_date(x, "TTM"))
    out = rows.sort_values(["sort_date", "kind", "version"], ascending=[False, False, False], kind="stable")
    assert out["period"].tolist() == ["TTM", "2026-08-21", "2026-08-21", "2025", "2024"]
    assert out[out["period"].eq("2026-08-21")]["version"].tolist() == [2, 1]
