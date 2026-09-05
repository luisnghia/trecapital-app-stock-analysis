from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from modules.deep_company_analysis.table_format import format_numeric, infer_numeric_kind, sort_frame, static_table_html

MOD = ROOT / "modules" / "deep_company_analysis"


def production_files() -> list[Path]:
    return [p for p in sorted(MOD.glob("*.py")) if not p.name.startswith("test_")]


def pass1_format() -> None:
    assert infer_numeric_kind("CFO (tỷ)") == "amount_bil"
    assert infer_numeric_kind("EBIT Margin (%)") == "percent"
    assert infer_numeric_kind("CFO/NI (x)") == "ratio"
    assert infer_numeric_kind("CCC ngày") == "days"
    assert format_numeric(1234.56, "amount_bil") == "1,235"
    assert format_numeric(-1234.56, "amount_bil") == "-1,235"
    assert format_numeric(12.345, "percent") == "12.3%"
    assert format_numeric(2.345, "ratio") == "2.3x"
    assert format_numeric(45.67, "days") == "45.7"
    html = static_table_html(pd.DataFrame([
        {"CFO (tỷ)": -123.6, "EBIT Margin (%)": 10.25},
        {"CFO (tỷ)": 250.4, "EBIT Margin (%)": -5.44},
    ]))
    for token in ("table-layout:fixed", "white-space:normal", "overflow-wrap:anywhere", "rgba(185,28,28", "rgba(4,120,87"):
        assert token in html, token
    print("PASS 1/3: numeric display contract + wrap + heat OK")


def pass2_ttm() -> None:
    loaders = [
        "chapter2_page_support.py",
        "chapter4_page_support.py",
        "chapter5_page_support.py",
        "chapter6_page_support.py",
    ]
    for name in loaders:
        text = (MOD / name).read_text(encoding="utf-8")
        assert "append_ttm_row" in text, f"{name}: canonical loader missing append_ttm_row"

    ch4 = (MOD / "chapter4_quant.py").read_text(encoding="utf-8")
    assert "display_rows = annual_rows[-10:]" in ch4
    assert "display_rows = display_rows + [current]" in ch4

    ch5 = (MOD / "chapter5_quant.py").read_text(encoding="utf-8")
    assert "def _history_rows" in ch5
    assert "include_ttm=True" in ch5
    assert "TTM displayed; incremental ROIC requires a comparable prior TTM" in ch5

    ch6 = (MOD / "chapter6_quant.py").read_text(encoding="utf-8")
    assert "TTM displayed; comparable prior TTM is required for DOL" in ch6

    evidence = (MOD / "chapter6_evidence.py").read_text(encoding="utf-8")
    assert "TTM applicability" in evidence
    assert "does not fabricate a TTM model value" in evidence
    print("PASS 2/3: canonical time-series reach valid TTM; annual-only/incomparable methods explicitly N/A")


def pass3_sort_and_boundary() -> None:
    direct_editor: list[str] = []
    direct_dataframe: list[str] = []
    direct_table: list[str] = []
    for path in production_files():
        if path.name == "table_format.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "st.data_editor(" in text:
            direct_editor.append(path.name)
        if "st.dataframe(" in text:
            direct_dataframe.append(path.name)
        if "st.table(" in text:
            direct_table.append(path.name)
    assert not direct_editor, f"Direct st.data_editor remains: {direct_editor}"
    assert not direct_dataframe, f"Direct st.dataframe remains: {direct_dataframe}"
    assert not direct_table, f"Direct st.table remains: {direct_table}"

    tf = (MOD / "table_format.py").read_text(encoding="utf-8")
    for token in ("def interactive_sort_frame", "def sortable_data_editor", "Sort theo cột", "Tăng dần", "Giảm dần"):
        assert token in tf, token

    ch1 = (MOD / "chapter1.py").read_text(encoding="utf-8")
    assert 'interactive_sort_frame(subset, key=f"ch1_inventory_{gate_key}")' in ch1
    assert 'interactive_sort_frame(history, key=f"ch1_gate_history_{ticker}")' in ch1

    monitoring = (MOD / "monitoring.py").read_text(encoding="utf-8")
    assert 'interactive_sort_frame(display, key=f"dca_review_queue_table_{current_ticker}")' in monitoring

    ch5 = (MOD / "chapter5_page_support.py").read_text(encoding="utf-8")
    assert "st.html(_wrapped_html_table(lock_table" not in ch5
    assert "st.html(_wrapped_html_table(report.research_readiness" not in ch5
    assert "render_static_table(lock_table, height=420)" in ch5
    assert "render_static_table(report.research_readiness, height=360)" in ch5

    ch6 = (MOD / "chapter6_page_support.py").read_text(encoding="utf-8")
    assert "rows_html" not in ch6
    assert 'sort_key=f"ch6_snapshots_{ticker}"' in ch6
    assert 'sort_key=f"{key}_formatted_preview"' in ch6

    evidence = (MOD / "chapter6_evidence.py").read_text(encoding="utf-8")
    for forbidden in ("module2_engine", "build_beneish", "build_modified_jones", "build_real_earnings"):
        assert forbidden not in evidence, f"Phase6C must not recompute Module2: {forbidden}"
    for boundary in ("q27", "q29", "earnings_distribution_width"):
        assert re.search(rf'out\[\s*["\']{re.escape(boundary)}["\']\s*\]\s*=', evidence) is None, boundary

    sample = pd.DataFrame({"Kỳ": ["2025", "2024", "TTM"], "CFO (tỷ)": [100.4, -20.2, 250.6]})
    sorted_sample = sort_frame(sample, "CFO (tỷ)", ascending=True)
    assert sorted_sample["CFO (tỷ)"].tolist() == [-20.2, 100.4, 250.6]
    assert sample["CFO (tỷ)"].tolist() == [100.4, -20.2, 250.6]
    print("PASS 3/3: all production table paths sortable + Phase6C analyst boundary OK")


def main() -> None:
    pass1_format()
    pass2_ttm()
    pass3_sort_and_boundary()


if __name__ == "__main__":
    main()
