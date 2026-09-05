from pathlib import Path

import pandas as pd

from modules.deep_company_analysis.table_format import format_numeric, infer_numeric_kind, sort_frame, static_table_html


def test_raw_numeric_sort_is_stable_and_does_not_mutate_input():
    original = pd.DataFrame({"Kỳ": ["2025", "2024", "TTM"], "CFO (tỷ)": [100.4, -20.2, 250.6]})
    before = original.copy(deep=True)
    out = sort_frame(original, "CFO (tỷ)", ascending=True)
    assert out["CFO (tỷ)"].tolist() == [-20.2, 100.4, 250.6]
    pd.testing.assert_frame_equal(original, before)


def test_locked_formats_remain_exact_after_sort_upgrade():
    assert infer_numeric_kind("CFO (tỷ)") == "amount_bil"
    assert infer_numeric_kind("EBIT Margin (%)") == "percent"
    assert infer_numeric_kind("CFO/NI (x)") == "ratio"
    assert infer_numeric_kind("CCC ngày") == "days"
    assert format_numeric(1234.56, "amount_bil") == "1,235"
    assert format_numeric(12.345, "percent") == "12.3%"
    assert format_numeric(2.345, "ratio") == "2.3x"
    assert format_numeric(45.67, "days") == "45.7"
    html = static_table_html(pd.DataFrame([{"CFO (tỷ)": -123.6, "EBIT Margin (%)": 10.25}]))
    assert "table-layout:fixed" in html
    assert "white-space:normal" in html
    assert "overflow-wrap:anywhere" in html
    assert "rgba(185,28,28" in html


def test_no_direct_data_editor_or_dataframe_remains_in_production_deep_analysis():
    root = Path(__file__).resolve().parent
    for path in root.glob("*.py"):
        if path.name.startswith("test_") or path.name == "table_format.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "st.data_editor(" not in text, path.name
        assert "st.dataframe(" not in text, path.name
    table_format = (root / "table_format.py").read_text(encoding="utf-8")
    assert "def sortable_data_editor" in table_format
    assert "def interactive_sort_frame" in table_format
    assert "Sort theo cột" in table_format
    chapter1 = (root / "chapter1.py").read_text(encoding="utf-8")
    assert "interactive_sort_frame(subset" in chapter1
