from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.table_format as table_format
from modules.deep_company_analysis.table_format import prefer_ttm_latest, static_table_html


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"


def test_latest_period_is_default_first_with_real_ttm_first():
    frame = pd.DataFrame(
        {
            "Kỳ": ["2023", "Q4/2025", "2024", "TTM", "Q2/2025"],
            "CFO (tỷ)": [50, 100, 70, 120, 90],
        }
    )
    out = prefer_ttm_latest(frame)
    assert out["Kỳ"].tolist() == ["TTM", "Q4/2025", "Q2/2025", "2024", "2023"]


def test_latest_period_is_first_even_without_ttm():
    frame = pd.DataFrame({"period": ["2023", "2025", "2024"], "ROIC %": [9, 12, 10]})
    out = prefer_ttm_latest(frame)
    assert out["period"].tolist() == ["2025", "2024", "2023"]


def test_period_sort_is_display_only_and_does_not_fabricate_ttm():
    frame = pd.DataFrame({"Kỳ": ["2024", "2025"], "FCF (tỷ)": [10, 20]})
    out = prefer_ttm_latest(frame)
    assert set(out["Kỳ"]) == {"2024", "2025"}
    assert not out["Kỳ"].astype(str).str.contains("TTM", case=False).any()


def test_all_explicit_financial_numeric_kinds_receive_heatmap():
    for column in (
        "Revenue (tỷ)",
        "ROIC %",
        "Debt/EBITDA (x)",
        "CCC ngày",
        "Shares outstanding",
    ):
        assert table_format.infer_numeric_kind(column) != "text", column
        assert table_format._heat_eligible(column), column

    html = static_table_html(
        pd.DataFrame(
            {
                "Kỳ": ["TTM", "2025", "2024"],
                "CFO (tỷ)": [300.0, 100.0, -200.0],
                "ROIC %": [18.25, 10.0, -5.5],
                "Debt/EBITDA (x)": [0.5, 1.0, -0.2],
            }
        )
    )
    assert "rgba(4,120,87" in html
    assert "rgba(185,28,28" in html
    assert "18,2%" in html
    assert "0,5x" in html
    assert "300" in html and "-200" in html


def test_dynamic_editor_uses_native_dynamic_rows_inside_form_without_forced_rerun():
    source = inspect.getsource(table_format._dynamic_editor)
    assert "st.form(" in source
    assert 'num_rows="dynamic"' in source
    assert "st.form_submit_button(" in source
    assert "st.rerun(" not in source
    assert "__add_row" not in source
    assert "__delete_rows" not in source
    assert "Áp dụng thay đổi bảng" in source


def test_unified_page_executes_only_selected_chapter_not_all_tabs():
    source = PAGE.read_text(encoding="utf-8")
    assert "CHAPTER_OPTIONS = (" in source
    assert "active_chapter = st.radio(" in source
    assert "st.tabs(" not in source
    for index in range(8):
        assert f"if active_chapter == CHAPTER_OPTIONS[{index}]:" in source
    assert "Only the selected chapter is executed" in source


def test_all_eight_chapter_labels_remain_in_unified_workspace():
    source = PAGE.read_text(encoding="utf-8")
    labels = (
        "📗 Chương 1 — Cơ hội đầu tư",
        "📘 Chương 2 — Hiểu doanh nghiệp",
        "📙 Chương 3 — Góc nhìn khách hàng",
        "📕 Chương 4 — Lợi thế & ngành",
        "📒 Chương 5 — Hoạt động & tài chính",
        "📓 Chương 6 — Earnings & dòng tiền",
        "👥 Chương 7 — Ban điều hành",
        "🧭 Chương 8 — Năng lực vận hành",
    )
    for label in labels:
        assert label in source
    # Legacy compatibility test still checks this marker while Chapter 8 remains embedded.
    assert "chapter8_tab" in source
