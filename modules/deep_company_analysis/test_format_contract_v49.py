from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter6_format as ch6fmt
import modules.deep_company_analysis.table_format as fmt


def test_v49_vietnamese_display_contract():
    assert fmt.format_numeric(1234.56, "amount_bil") == "1.235"
    assert fmt.format_numeric(-1234.56, "amount_bil") == "-1.235"
    assert fmt.format_numeric(12.345, "percent") == "12,3%"
    assert fmt.format_numeric(-5.44, "percent") == "-5,4%"
    assert fmt.format_numeric(2.345, "ratio") == "2,3x"
    assert fmt.format_numeric(45.67, "days") == "45,7"
    assert fmt.format_numeric(379.812, "shares") == "379,8"


def test_v49_chapter6_uses_same_display_contract():
    assert ch6fmt.format_numeric(1234.56, "amount_bil") == fmt.format_numeric(1234.56, "amount_bil")
    assert ch6fmt.format_numeric(12.345, "percent") == fmt.format_numeric(12.345, "percent")
    assert ch6fmt.format_numeric(2.345, "ratio") == fmt.format_numeric(2.345, "ratio")


def test_v49_static_table_format_and_heat_contract():
    frame = pd.DataFrame([
        {"Kỳ": "2025", "Doanh thu (tỷ)": 12345.6, "FCF (tỷ)": -123.6, "ROIC canonical %": 20.25, "Debt/EBITDA (x)": 1.26},
        {"Kỳ": "TTM", "Doanh thu (tỷ)": 15001.2, "FCF (tỷ)": 250.4, "ROIC canonical %": 25.04, "Debt/EBITDA (x)": 0.84},
    ])
    html = fmt.static_table_html(frame)
    assert "12.346" in html and "15.001" in html
    assert "-124" in html and "250" in html
    assert "20,2%" in html and "25,0%" in html
    assert "1,3x" in html and "0,8x" in html
    assert "#991B1B" in html and "#047857" in html
    assert "white-space:normal" in html and "overflow-wrap:anywhere" in html


def test_v49_all_chapter_production_tables_use_shared_wrappers():
    root = Path(__file__).resolve().parent
    production = []
    for path in root.glob("chapter*.py"):
        if path.name.startswith("test_") or path.name in {"chapter6_format.py"}:
            continue
        production.append(path)
    assert production
    offenders = []
    for path in production:
        text = path.read_text(encoding="utf-8")
        if "st.dataframe(" in text or "st.table(" in text or "st.data_editor(" in text:
            offenders.append(path.name)
    assert offenders == [], f"Chapter files bypass shared table formatting: {offenders}"


def test_v49_static_native_grid_does_not_override_localized_styler_with_printf():
    source = Path(fmt.__file__).read_text(encoding="utf-8")
    render_body = source.split("def render_static_table", 1)[1]
    assert "_native_table_styler(frame)" in render_body
    assert "column_config = provided if isinstance(provided, dict) else None" in render_body
    assert "_default_editor_column_config(frame)" not in render_body.split("__all__", 1)[0]
