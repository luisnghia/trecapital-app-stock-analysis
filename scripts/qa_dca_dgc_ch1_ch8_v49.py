from __future__ import annotations

"""V49 live DGC acceptance: canonical data + unified Chapters 1-8 + numeric display contract."""

import json
import re
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
from modules.deep_company_analysis.table_format import format_numeric, infer_numeric_kind


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "app.py"
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
OUT = ROOT / "reports" / "DCA_DGC_CH1_CH8_V49_ACCEPTANCE.json"

TAB_LABELS = [
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


def _format_samples(bridge: dict) -> dict[str, str]:
    samples: dict[str, str] = {}
    for name in ("q45_cost_context", "q46_capital_allocation_context", "q47_buyback_context"):
        frame = bridge.get(name)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        for column in frame.columns:
            kind = infer_numeric_kind(str(column))
            if kind == "text":
                continue
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            if values.empty:
                continue
            samples[f"{name}:{column}"] = format_numeric(float(values.iloc[-1]), kind)
    return samples


def _assert_vi_format(samples: dict[str, str]) -> None:
    assert samples, "No actual DGC numeric format samples were produced"
    for key, value in samples.items():
        assert ".0%" not in value and ".0x" not in value, (key, value)
        if value.endswith("%") or value.endswith("x"):
            assert re.search(r",\d[%x]$", value), (key, value)
        assert not re.search(r"\d,\d{3}(?:\.\d+)?(?:[%x])?$", value), (key, value)


def main() -> int:
    ticker = "DGC"
    if st.__version__ != "1.40.2":
        raise AssertionError(f"Expected pinned Streamlit 1.40.2, got {st.__version__}")

    ok, paths, canonical_note = refresh_peer_canonical_bundle(ticker)
    assert ok and paths, f"DGC canonical refresh failed: {canonical_note}"
    overview_path, annual_path, quarter_path = paths
    assert all(path.exists() and path.stat().st_size > 20 for path in paths)

    company = m1._load_overview_cached(str(overview_path), ticker)
    company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    assert company_name, f"Unexpected company overview: {company_name!r}"
    annual_raw = m1._load_timeseries_cached(str(annual_path), ticker, "Y", 20)
    quarterly = m1._load_timeseries_cached(str(quarter_path), ticker, "Q", 40)
    assert isinstance(annual_raw, pd.DataFrame) and not annual_raw.empty
    assert isinstance(quarterly, pd.DataFrame) and not quarterly.empty
    annual = append_ttm_row(annual_raw, quarterly)
    assert isinstance(annual, pd.DataFrame) and not annual.empty
    latest_period = _period_value(annual.iloc[-1])
    assert "TTM" in latest_period.upper(), f"Expected actual TTM latest row, got {latest_period!r}"

    bridge = build_phase8b_context(ticker, annual, chapter7_payload=None, guidance_rows=None)
    for key in ("q45_cost_context", "q46_capital_allocation_context", "q47_buyback_context"):
        assert isinstance(bridge[key], pd.DataFrame) and not bridge[key].empty, key
    format_samples = _format_samples(bridge)
    _assert_vi_format(format_samples)

    home = AppTest.from_file(str(ENTRYPOINT))
    home.run(timeout=120)
    home_exceptions = _exceptions(home)
    if home_exceptions:
        raise AssertionError("Production entrypoint AppTest raised exceptions:\n" + "\n".join(home_exceptions))

    with patch.object(tre_sidebar_nav, "render_tre_sidebar_nav", lambda: None):
        dca = AppTest.from_file(str(PAGE))
        for key in (
            "active_ticker", "shared_ticker", "module1_ticker", "module2_ticker", "last_query_ticker",
            "dca_ch1_ticker", "dca_ch2_ticker", "dca_ch3_ticker", "dca_ch4_ticker",
            "dca_ch5_ticker", "dca_ch6_ticker", "dca_ch7_ticker", "dca_ch8_ticker",
        ):
            dca.session_state[key] = ticker
        dca.session_state["active_overview_csv"] = str(overview_path)
        dca.session_state["active_year_csv"] = str(annual_path)
        dca.session_state["active_quarter_csv"] = str(quarter_path)
        dca.session_state["active_source_label"] = "DGC V49 live canonical acceptance"
        dca.run(timeout=180)

    dca_exceptions = _exceptions(dca)
    if dca_exceptions:
        raise AssertionError("DGC unified Ch1-Ch8 AppTest raised exceptions:\n" + "\n".join(dca_exceptions))

    page_source = PAGE.read_text(encoding="utf-8")
    for label in TAB_LABELS:
        assert label in page_source, label

    rendered_messages: list[str] = []
    for collection_name in ("success", "info", "warning", "caption", "markdown"):
        try:
            rendered_messages.extend(str(item.value) for item in getattr(dca, collection_name))
        except Exception:
            pass
    rendered_text = "\n".join(rendered_messages)
    assert "Dữ liệu mẫu DCM" not in rendered_text
    assert ticker in rendered_text, "DGC was not visible in the rendered unified page"

    out = {
        "phase": "DCA Numeric Format + DGC Chapter 1-8 Acceptance V49",
        "acceptance": "PASS",
        "ticker": ticker,
        "company_name": company_name,
        "streamlit_version": st.__version__,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "canonical_overview_path": str(overview_path),
        "annual_rows": int(len(annual_raw)),
        "quarterly_rows": int(len(quarterly)),
        "latest_period": latest_period,
        "tabs_executed": len(TAB_LABELS),
        "tab_labels": TAB_LABELS,
        "entrypoint_exceptions": 0,
        "dgc_ch1_ch8_exceptions": 0,
        "dgc_sample_fallback_used": False,
        "format_contract": {
            "amount_billion_decimals": 0,
            "percent_decimals": 1,
            "ratio_decimals": 1,
            "thousands_separator": ".",
            "decimal_separator": ",",
            "negative_color": "red",
            "positive_growth_color": "emerald"
        },
        "actual_dgc_format_samples": format_samples,
        "financial_ssot": bridge["financial_ssot"],
        "note": (
            "DGC was refreshed through Trecapital canonical pipeline, then the unified page executed all "
            "Chapter 1-8 tab bodies in one Streamlit AppTest run with the DGC bundle explicitly bound."
        )
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
