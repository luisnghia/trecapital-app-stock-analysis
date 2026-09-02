from __future__ import annotations

from pathlib import Path


def patch_file(path: str, replacements: list[tuple[str, str]]) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    changed = False
    for old, new in replacements:
        if new in text:
            continue
        if old not in text:
            raise SystemExit(f"V5 patch anchor not found in {path}:\n{old[:400]}")
        text = text.replace(old, new, 1)
        changed = True
    if changed:
        target.write_text(text, encoding="utf-8")
        print(f"Patched {path} to Chapter 1 V5 monitoring")
    else:
        print(f"{path} already contains V5 monitoring")


patch_file(
    "modules/deep_company_analysis/trecapital_auto.py",
    [
        (
'''    return {
        "as_of": str(getattr(source, "as_of_date", "") or ""),
        "source_module": str(getattr(source, "source_module", "") or ""),
        "source_notes": list(getattr(source, "source_notes", ()) or ()),
        "valuation": valuation,
        "quality_suggestions": build_quantitative_suggestions(source, annual_df),
    }
''',
'''    roics = _recent_roic_values(annual_df, 5)
    monitoring_metrics = {
        "current_price": valuation.get("current_price"),
        "mos_pct": valuation.get("mos_pct"),
        "roic_pct": roics[0] if roics else None,
        "debt_ebitda": valuation.get("debt_ebitda"),
        "ebit_interest": valuation.get("ebit_interest"),
        "fcf_yield_pct": valuation.get("fcf_yield_pct"),
    }
    return {
        "as_of": str(getattr(source, "as_of_date", "") or ""),
        "source_module": str(getattr(source, "source_module", "") or ""),
        "source_notes": list(getattr(source, "source_notes", ()) or ()),
        "valuation": valuation,
        "quality_suggestions": build_quantitative_suggestions(source, annual_df),
        "monitoring_metrics": monitoring_metrics,
    }
''',
        )
    ],
)


patch_file(
    "modules/deep_company_analysis/chapter1.py",
    [
        (
'''import pandas as pd
import streamlit as st

APP_ROOT = Path(__file__).resolve().parents[2]
''',
'''import pandas as pd
import streamlit as st

from modules.deep_company_analysis.monitoring import evaluate_and_persist, render_monitoring_panel

APP_ROOT = Path(__file__).resolve().parents[2]
''',
        ),
        (
'''    st.warning("App có thể phát hiện trigger ở giai đoạn sau nhưng không được tự đổi Research Gate. Gate là quyết định của analyst.", icon="⚠️")

    if st.button("💾 Lưu đánh giá Chương 1", type="primary", use_container_width=True, key=f"dca_save_{ticker}"):
''',
'''    st.warning(
        "Monitoring Engine tự kiểm tra các trigger đã lưu khi dữ liệu Trecapital được cập nhật, nhưng không bao giờ tự đổi Research Gate. Gate vẫn là quyết định của analyst.",
        icon="⚠️",
    )

    evaluation_results: list[dict[str, Any]] = []
    if is_saved and auto_data and record.get("triggers"):
        try:
            evaluation_results = evaluate_and_persist(ticker, record, auto_data)
        except Exception as exc:
            st.caption(f"Monitoring Engine chưa đánh giá được trigger: {exc}")

    if st.button("💾 Lưu đánh giá Chương 1", type="primary", use_container_width=True, key=f"dca_save_{ticker}"):
''',
        ),
        (
'''    st.divider()
    _render_inventory()

    history = load_gate_history(ticker)
''',
'''    st.divider()
    _render_inventory()
    render_monitoring_panel(ticker, evaluation_results)

    history = load_gate_history(ticker)
''',
        ),
    ],
)


patch_file(
    "pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py",
    [
        (
'''from modules.deep_company_analysis.chapter1 import render_chapter1
from modules.deep_company_analysis.opportunity_signals import OpportunityEventEvidenceAgent, build_opportunity_signals
''',
'''from modules.deep_company_analysis.chapter1 import load_inventory, load_record, render_chapter1
from modules.deep_company_analysis.monitoring import evaluate_and_persist
from modules.deep_company_analysis.opportunity_signals import OpportunityEventEvidenceAgent, build_opportunity_signals
''',
        ),
        (
'''def _refresh_trecapital(ticker: str) -> bool:
''',
'''def _scan_review_queue_from_cache() -> tuple[int, int]:
    """Evaluate saved triggers for every inventory ticker that already has a local Trecapital bundle.

    This scan is deliberately cache-only: it does not fan out network calls across the watchlist.
    The normal per-ticker refresh remains the place where market/financial data is downloaded.
    """
    inventory = load_inventory()
    if inventory is None or inventory.empty or "Mã" not in inventory.columns:
        return 0, 0
    checked = 0
    skipped = 0
    for ticker_value in inventory["Mã"].astype(str).tolist():
        safe = _safe_ticker(ticker_value)
        if not safe:
            continue
        data, _, _ = _prepare_auto_data(safe)
        record = load_record(safe)
        if not data or not record.get("triggers"):
            skipped += 1
            continue
        try:
            evaluate_and_persist(safe, record, data)
            checked += 1
        except Exception:
            skipped += 1
    return checked, skipped


def _refresh_trecapital(ticker: str) -> bool:
''',
        ),
        (
'''render_chapter1(
    default_ticker=default_ticker,
''',
'''if st.button("🔎 Quét Review Queue từ dữ liệu cache", use_container_width=True, key="dca_scan_review_queue"):
    with st.spinner("Đang kiểm tra trigger của Opportunity Inventory bằng dữ liệu local đã có..."):
        checked, skipped = _scan_review_queue_from_cache()
    st.success(f"Đã kiểm tra {checked} mã; bỏ qua {skipped} mã chưa có cache hoặc chưa đặt trigger.")
    st.rerun()

render_chapter1(
    default_ticker=default_ticker,
''',
        ),
    ],
)
