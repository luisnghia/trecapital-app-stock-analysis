from pathlib import Path
import inspect

import pandas as pd

import modules.deep_company_analysis.table_format as table_format
from modules.deep_company_analysis.table_format import (
    default_latest_period,
    default_latest_period_index,
    format_numeric,
    infer_numeric_kind,
    prefer_ttm_latest,
    static_table_html,
)


def test_locked_formats_remain_exact_after_header_sort_upgrade():
    assert infer_numeric_kind("CFO (tỷ)") == "amount_bil"
    assert infer_numeric_kind("EBIT Margin (%)") == "percent"
    assert infer_numeric_kind("CFO/NI (x)") == "ratio"
    assert infer_numeric_kind("CCC ngày") == "days"
    assert format_numeric(1234.56, "amount_bil") == "1.235"
    assert format_numeric(12.345, "percent") == "12,3%"
    assert format_numeric(2.345, "ratio") == "2,3x"
    assert format_numeric(45.67, "days") == "45,7"
    html = static_table_html(pd.DataFrame([{"CFO (tỷ)": -123.6, "EBIT Margin (%)": 10.25}]))
    assert "table-layout:fixed" in html
    assert "white-space:normal" in html
    assert "overflow-wrap:anywhere" in html
    assert "rgba(185,28,28" in html


def test_no_direct_dataframe_editor_or_table_remains_in_production_deep_analysis():
    root = Path(__file__).resolve().parent
    for path in root.glob("*.py"):
        if path.name.startswith("test_") or path.name == "table_format.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "st.data_editor(" not in text, path.name
        assert "st.dataframe(" not in text, path.name
        assert "st.table(" not in text, path.name

    source = (root / "table_format.py").read_text(encoding="utf-8")
    assert "def sortable_data_editor" in source
    assert "def render_static_table" in source
    assert "st.dataframe(" in source
    assert "st.data_editor(" in source


def test_dynamic_editors_are_form_batched_without_forced_rerun():
    source = inspect.getsource(table_format._dynamic_editor)
    assert "st.form(" in source
    assert 'num_rows="dynamic"' in source
    assert "st.form_submit_button(" in source
    assert "st.rerun(" not in source
    assert "__add_row" not in source
    assert "__delete_rows" not in source

def test_ttm_is_default_latest_period_without_fabrication():
    frame = pd.DataFrame({"Kỳ": ["TTM", "2024", "2025"], "CFO (tỷ)": [130, 90, 110]})
    out = prefer_ttm_latest(frame)
    assert out["Kỳ"].tolist() == ["TTM", "2025", "2024"]

    no_ttm = pd.DataFrame({"Kỳ": ["2024", "2025"], "CFO (tỷ)": [90, 110]})
    out2 = prefer_ttm_latest(no_ttm)
    assert out2["Kỳ"].tolist() == ["2025", "2024"]

    options = ["2023", "2024", "2025", "TTM"]
    assert default_latest_period_index(options) == 3
    assert default_latest_period(options) == "TTM"
    assert default_latest_period_index(["2024", "2025"]) == 1
    assert default_latest_period(["2024", "2025"]) == "2025"
    assert default_latest_period([]) is None


def test_legacy_sort_implementation_is_completely_removed():
    root = Path(__file__).resolve().parent
    forbidden = (
        "Sort theo cột",
        "Thứ tự",
        "Giữ thứ tự gốc",
        "ORIGINAL_ORDER_LABEL",
        "ASC_LABEL",
        "DESC_LABEL",
        "interactive_sort_frame",
        "def sort_frame(",
    )
    for path in root.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token!r} remains in {path.name}"


def test_chapter1_and_shared_tables_use_native_renderers():
    root = Path(__file__).resolve().parent
    chapter1 = (root / "chapter1.py").read_text(encoding="utf-8")
    assert "render_static_table(" in chapter1
    assert "interactive_sort_frame" not in chapter1
