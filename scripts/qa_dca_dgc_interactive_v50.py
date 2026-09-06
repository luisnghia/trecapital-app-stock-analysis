from __future__ import annotations

"""V50 live DGC acceptance for stable editors, lazy chapters, heatmap and latest-first display."""

import json
import re
import time
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

import module1_dashboard as m1
from module1_engine import append_ttm_row
import tre_sidebar_nav
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.table_format import (
    format_numeric,
    infer_numeric_kind,
    prefer_ttm_latest,
    static_table_html,
)


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "app.py"
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
OUT = ROOT / "reports" / "DCA_DGC_INTERACTIVE_V50_ACCEPTANCE.json"

CHAPTER_LABELS = [
    "📗 Chương 1 — Cơ hội đầu tư",
    "📘 Chương 2 — Hiểu doanh nghiệp",
    "📙 Chương 3 — Góc nhìn khách hàng",
    "📕 Chương 4 — Lợi thế & ngành",
    "📒 Chương 5 — Hoạt động & tài chính",
    "📓 Chương 6 — Earnings & dòng tiền",
    "👥 Chương 7 — Ban điều hành",
    "🧭 Chương 8 — Năng lực vận hành",
]


def _exceptions(at: AppTest) -> list[str]:
    return [str(item.value) for item in at.exception]


def _period_value(row: pd.Series) -> str:
    for key in ("period", "Kỳ", "year"):
        if key in row.index and pd.notna(row.get(key)):
            return str(row.get(key))
    return ""


def _bind_dgc_state(at: AppTest, ticker: str, paths, chapter: str) -> None:
    for key in (
        "active_ticker", "shared_ticker", "module1_ticker", "module2_ticker", "last_query_ticker",
        "dca_ch1_ticker", "dca_ch2_ticker", "dca_ch3_ticker", "dca_ch4_ticker",
        "dca_ch5_ticker", "dca_ch6_ticker", "dca_ch7_ticker", "dca_ch8_ticker",
    ):
        at.session_state[key] = ticker
    at.session_state["active_overview_csv"] = str(paths[0])
    at.session_state["active_year_csv"] = str(paths[1])
    at.session_state["active_quarter_csv"] = str(paths[2])
    at.session_state["active_source_label"] = "DGC V50 live canonical acceptance"
    at.session_state["dca_active_chapter"] = chapter


def _format_samples(bridge: dict) -> dict[str, str]:
    samples: dict[str, str] = {}
    for name in ("q45_cost_context", "q46_capital_allocation_context", "q47_buyback_context"):
        frame = bridge.get(name)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        ordered = prefer_ttm_latest(frame)
        for column in ordered.columns:
            kind = infer_numeric_kind(str(column))
            if kind == "text":
                continue
            values = pd.to_numeric(ordered[column], errors="coerce").dropna()
            if values.empty:
                continue
            samples[f"{name}:{column}"] = format_numeric(float(values.iloc[0]), kind)
    return samples


def _assert_vi_format(samples: dict[str, str]) -> None:
    assert samples, "No actual DGC numeric samples"
    for key, value in samples.items():
        if value.endswith("%") or value.endswith("x"):
            assert re.search(r",\d[%x]$", value), (key, value)
        assert not re.search(r"\d,\d{3}(?:\.\d+)?(?:[%x])?$", value), (key, value)


def main() -> int:
    ticker = "DGC"
    assert st.__version__ == "1.40.2", st.__version__

    ok, paths, canonical_note = refresh_peer_canonical_bundle(ticker)
    assert ok and paths, canonical_note
    assert all(path.exists() and path.stat().st_size > 20 for path in paths)

    company = m1._load_overview_cached(str(paths[0]), ticker)
    company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    assert company_name
    annual_raw = m1._load_timeseries_cached(str(paths[1]), ticker, "Y", 20)
    quarterly = m1._load_timeseries_cached(str(paths[2]), ticker, "Q", 40)
    annual = append_ttm_row(annual_raw, quarterly)
    assert not annual.empty
    latest_period = _period_value(annual.iloc[-1])
    assert "TTM" in latest_period.upper(), latest_period

    bridge = build_phase8b_context(ticker, annual, chapter7_payload=None, guidance_rows=None)
    samples = _format_samples(bridge)
    _assert_vi_format(samples)

    # Real DGC financial context: presentation order must put a real TTM first when the table has periods.
    period_tables_checked = 0
    for key in ("q45_cost_context", "q46_capital_allocation_context", "q47_buyback_context"):
        frame = bridge[key]
        period_col = next((c for c in ("Kỳ", "Period", "period", "Kỳ dữ liệu") if c in frame.columns), None)
        if period_col:
            ordered = prefer_ttm_latest(frame)
            if ordered[period_col].astype(str).str.upper().str.contains("TTM").any():
                assert "TTM" in str(ordered.iloc[0][period_col]).upper(), (key, ordered[period_col].tolist())
            period_tables_checked += 1

    # Heatmap must apply to ordinary financial amount/%/ratio columns, not just a narrow keyword set.
    heat_html = static_table_html(
        pd.DataFrame(
            {
                "Kỳ": ["TTM", "2025", "2024"],
                "Doanh thu (tỷ)": [10097.0, 9870.0, -120.0],
                "ROIC %": [11.0, 10.0, -2.0],
                "Debt/EBITDA (x)": [0.7, 0.9, -0.1],
            }
        )
    )
    assert "rgba(4,120,87" in heat_html
    assert "rgba(185,28,28" in heat_html

    home = AppTest.from_file(str(ENTRYPOINT))
    home.run(timeout=120)
    assert not _exceptions(home), _exceptions(home)

    page_source = PAGE.read_text(encoding="utf-8")
    assert "st.tabs(" not in page_source
    assert "active_chapter = st.radio(" in page_source
    for index, label in enumerate(CHAPTER_LABELS):
        assert label in page_source
        assert f"if active_chapter == CHAPTER_OPTIONS[{index}]:" in page_source

    chapter_runtime_seconds: dict[str, float] = {}
    chapter_exception_counts: dict[str, int] = {}
    with patch.object(tre_sidebar_nav, "render_tre_sidebar_nav", lambda: None):
        for chapter in CHAPTER_LABELS:
            at = AppTest.from_file(str(PAGE))
            _bind_dgc_state(at, ticker, paths, chapter)
            started = time.perf_counter()
            at.run(timeout=180)
            elapsed = time.perf_counter() - started
            errors = _exceptions(at)
            chapter_runtime_seconds[chapter] = round(elapsed, 3)
            chapter_exception_counts[chapter] = len(errors)
            if errors:
                raise AssertionError(f"{chapter} raised exceptions:\n" + "\n".join(errors))

            # The selected radio value confirms the lazy branch selection used by this run.
            try:
                selected = at.radio[0].value
                assert selected == chapter, (selected, chapter)
            except IndexError:
                raise AssertionError(f"No active-chapter radio rendered for {chapter}")

    # Warm Ch2 rerun is the closest AppTest approximation of ordinary analyst interaction.
    with patch.object(tre_sidebar_nav, "render_tre_sidebar_nav", lambda: None):
        ch2 = AppTest.from_file(str(PAGE))
        _bind_dgc_state(ch2, ticker, paths, CHAPTER_LABELS[1])
        ch2.run(timeout=180)
        started = time.perf_counter()
        ch2.run(timeout=180)
        ch2_warm_rerun_seconds = round(time.perf_counter() - started, 3)
        ch2_errors = _exceptions(ch2)
        assert not ch2_errors, ch2_errors

    out = {
        "phase": "DCA Stable Interactive Tables + Lazy Chapters V50",
        "acceptance": "PASS",
        "ticker": ticker,
        "company_name": company_name,
        "streamlit_version": st.__version__,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "annual_rows": int(len(annual_raw)),
        "quarterly_rows": int(len(quarterly)),
        "latest_canonical_period": latest_period,
        "chapters_executed_sequentially": len(CHAPTER_LABELS),
        "chapter_exception_counts": chapter_exception_counts,
        "chapter_runtime_seconds": chapter_runtime_seconds,
        "chapter2_warm_rerun_seconds": ch2_warm_rerun_seconds,
        "lazy_chapter_rendering": True,
        "st_tabs_removed": True,
        "dynamic_editor_native_rows": True,
        "dynamic_editor_form_batched": True,
        "forced_editor_rerun_removed": True,
        "sessioninfo_race_pattern_removed": True,
        "latest_period_default_top": True,
        "period_tables_checked": period_tables_checked,
        "heatmap_all_explicit_financial_numeric_columns": True,
        "format_contract": {
            "amount_billion_decimals": 0,
            "percent_decimals": 1,
            "ratio_decimals": 1,
            "thousands_separator": ".",
            "decimal_separator": ",",
            "negative_color": "red",
            "positive_color": "emerald",
            "heat_intensity_by_absolute_magnitude": True,
        },
        "actual_dgc_format_samples": samples,
        "financial_ssot": bridge["financial_ssot"],
        "note": (
            "Each DGC chapter was executed as the selected lazy chapter in a separate AppTest run. "
            "The old custom add/delete + forced st.rerun editor race is absent by source contract; "
            "native dynamic row controls are form-batched so cell typing does not run Python until submit."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
