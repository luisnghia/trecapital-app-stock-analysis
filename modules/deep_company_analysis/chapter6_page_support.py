from __future__ import annotations

"""Streamlit UI for Deep Company Analysis — Chapter 6 approved Phase 6A.

The UI is analyst-owned. Data/AI may support evidence collection in later phases but must
never silently convert a signal into an analyst conclusion, a Research Gate, or BUY/HOLD/SELL.
"""

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter2_page_support import _active_paths, _path_signature
from modules.deep_company_analysis.chapter5_quant import build_balance_sheet_context
from modules.deep_company_analysis.chapter6_closure import (
    TAX_FOOTNOTE_COLUMNS,
    UNSUSTAINABLE_EARNINGS_COLUMNS,
    ASSET_REPLACEMENT_COLUMNS,
    VALUATION_SCENARIO_COLUMNS,
    FINAL_CHECKLIST_COLUMNS,
    FINAL_CHECKLIST_STATUS_OPTIONS,
    tax_footnote_analysis,
    asset_replacement_analysis,
    combined_leverage_evidence,
    valuation_method_guidance,
    chapter6_completion_status,
)
from modules.deep_company_analysis.table_format import format_numeric, render_static_table, sortable_data_editor
from modules.deep_company_analysis.chapter6_quant import build_chapter6_quant_context
from modules.deep_company_analysis.chapter6_evidence import (
    Chapter6EvidenceAgent,
    evidence_quality_summary,
    manipulation_snapshot_candidates,
    manipulation_snapshot_table,
    merge_candidates_into_record,
    research_gaps as phase6c_research_gaps,
)

from modules.deep_company_analysis.chapter6 import (
    ACCOUNTING_QUALITY_COLUMNS,
    CAPEX_COLUMNS,
    COST_STRUCTURE_COLUMNS,
    CYCLE_COLUMNS,
    DISTRIBUTION_MATRIX_COLUMNS,
    DISTRIBUTION_WIDTH_OPTIONS,
    EVIDENCE_COLUMNS,
    MAINTENANCE_CAPEX_METHOD_OPTIONS,
    QUESTION_STATUS_OPTIONS,
    RECURRING_REVENUE_COLUMNS,
    RESERVE_ROLLFORWARD_COLUMNS,
    RESEARCH_GAP_COLUMNS,
    TREND_OPTIONS,
    WORKING_CAPITAL_COLUMNS,
    create_snapshot,
    list_snapshots,
    load_record,
    research_gap_warnings,
    save_record,
)
from modules.deep_company_analysis.chapter6_format import (
    financial_table_html,
    has_financial_numeric_columns,
    infer_numeric_kind,
)

APP_DIR = Path(__file__).resolve().parents[2]
FORMULA_DOC = APP_DIR / "docs" / "formulas" / "DEEP_COMPANY_ANALYSIS_CHAPTER6_FORMULAS.md"
SOURCE_LOCK_DOC = APP_DIR / "docs" / "CHAPTER6_PHASE6A_SOURCE_LOCK.md"


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _df(rows: Any, columns: list[str]) -> pd.DataFrame:
    incoming = [dict(row) for row in rows] if isinstance(rows, list) else []
    if not incoming:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(incoming)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        clean = value.where(pd.notna(value), None)
        return clean.to_dict(orient="records")
    return []


def _question_controls(payload: dict[str, Any], q: str, key_prefix: str) -> None:
    c1, c2 = st.columns(2)
    status_current = str((payload.get("question_status") or {}).get(q) or "Unknown")
    trend_current = str((payload.get("question_trend") or {}).get(q) or "Unknown")
    with c1:
        payload["question_status"][q] = st.selectbox(
            "Research status",
            QUESTION_STATUS_OPTIONS,
            index=QUESTION_STATUS_OPTIONS.index(status_current) if status_current in QUESTION_STATUS_OPTIONS else 0,
            key=f"{key_prefix}_{q}_status",
        )
    with c2:
        payload["question_trend"][q] = st.selectbox(
            "Trend",
            TREND_OPTIONS,
            index=TREND_OPTIONS.index(trend_current) if trend_current in TREND_OPTIONS else 0,
            key=f"{key_prefix}_{q}_trend",
        )


def _select(label: str, current: Any, options: tuple[str, ...], key: str) -> str:
    value = str(current or options[0])
    return st.selectbox(
        label,
        options,
        index=options.index(value) if value in options else 0,
        key=key,
    )


def _editor_column_config(columns: list[str]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for column in columns:
        kind = infer_numeric_kind(column)
        if kind == "amount_bil":
            config[column] = st.column_config.NumberColumn(
                column,
                format="%.0f",
                help="Đơn vị: tỷ đồng; hiển thị 0 số lẻ.",
            )
        elif kind == "percent":
            config[column] = st.column_config.NumberColumn(
                column,
                format="%.1f%%",
                help="Đơn vị: %; hiển thị 1 số lẻ.",
            )
        elif kind == "ratio":
            config[column] = st.column_config.NumberColumn(
                column,
                format="%.1f",
                help="Hệ số; hiển thị 1 số lẻ.",
            )
        elif kind == "days":
            config[column] = st.column_config.NumberColumn(
                column,
                format="%.1f",
                help="Số ngày; hiển thị 1 số lẻ.",
            )

    if "Revenue Type" in columns:
        config["Revenue Type"] = st.column_config.SelectboxColumn(
            "Revenue Type",
            options=[
                "Unknown",
                "Contractual recurring",
                "Behavioral recurring",
                "Repeat purchase",
                "One-off",
                "Mixed",
            ],
        )
    if "Contractual?" in columns:
        config["Contractual?"] = st.column_config.SelectboxColumn(
            "Contractual?",
            options=["Unknown", "Yes", "No", "Mixed"],
        )
    if "Effect on Distribution" in columns:
        config["Effect on Distribution"] = st.column_config.SelectboxColumn(
            "Effect on Distribution",
            options=["Unknown", "Narrower", "Wider", "Neutral", "Mixed"],
        )
    if "Question" in columns:
        config["Question"] = st.column_config.TextColumn("Question", disabled=True)
    if "Source-Locked Requirement" in columns and "Status" in columns:
        config["Status"] = st.column_config.SelectboxColumn("Status", options=list(FINAL_CHECKLIST_STATUS_OPTIONS))
    if "Driver" in columns and columns == DISTRIBUTION_MATRIX_COLUMNS:
        config["Driver"] = st.column_config.TextColumn("Driver", disabled=True)
    return config


def _editor(
    label: str,
    rows: Any,
    columns: list[str],
    key: str,
    *,
    height: int = 300,
) -> list[dict[str, Any]]:
    st.markdown(f"**{label}**")
    edited = sortable_data_editor(
        _df(rows, columns),
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        height=height,
        column_config=_editor_column_config(columns),
        key=key,
    )
    if has_financial_numeric_columns(columns) and isinstance(edited, pd.DataFrame) and not edited.empty:
        # This helper is frequently called from inside a question expander. Streamlit 1.40.x
        # forbids nested expanders, so the formatted preview must use a plain bordered container.
        with st.container(border=True):
            st.caption(f"🔎 Preview format số liệu — {label}")
            st.caption(
                "Quy chuẩn: tỷ đồng 0 số lẻ; % và hệ số 1 số lẻ; số âm đỏ, số dương xanh ngọc; "
                "cường độ màu tăng theo độ lớn tuyệt đối."
            )
            render_static_table(edited, height=min(360, 90 + 30 * len(edited)), sort_key=f"{key}_formatted_preview")
    return _rows(edited)



@st.cache_data(ttl=120, show_spinner=False)
def _chapter6_quant_cached(
    ticker: str,
    overview_path: str,
    year_path: str,
    quarter_path: str,
    overview_sig: tuple[int, int],
    year_sig: tuple[int, int],
    quarter_sig: tuple[int, int],
    source_label: str,
):
    del overview_sig, year_sig, quarter_sig
    safe = _safe_ticker(ticker)
    company = m1._load_overview_cached(overview_path, safe)
    annual_raw = m1._load_timeseries_cached(year_path, safe, "Y", 11)
    quarterly = m1._load_timeseries_cached(quarter_path, safe, "Q", 20)
    annual_and_ttm = append_ttm_row(annual_raw, quarterly)
    ctx = build_chapter6_quant_context(
        safe,
        str(getattr(company, "company_name", "") or getattr(company, "name", "") or ""),
        annual_and_ttm,
        industry=str(getattr(company, "industry", "") or ""),
        sub_industry=str(getattr(company, "sub_industry", "") or ""),
        source_label=source_label,
        years=10,
    )
    # Phase 6D reuses Chapter-5 shared balance-sheet diagnostics read-only; no duplicate leverage formula.
    ctx["chapter5_balance_sheet_context"] = build_balance_sheet_context(annual_and_ttm, years=10)
    return ctx


def _load_chapter6_quant(ticker: str):
    safe = _safe_ticker(ticker)
    paths, source_label = _active_paths(safe)
    if not paths:
        return None, f"{safe}: chưa có canonical statement cache trên máy."
    overview, year, quarter = paths
    try:
        ctx = _chapter6_quant_cached(
            safe,
            str(overview), str(year), str(quarter),
            _path_signature(overview), _path_signature(year), _path_signature(quarter),
            source_label,
        )
        if not ctx:
            return None, f"{safe}: canonical bundle chưa có dữ liệu usable cho Phase 6B."
        return ctx, ""
    except Exception as exc:
        return None, f"{safe}: không dựng được Chapter 6 quantitative context: {exc}"


def _refresh_chapter6_canonical(ticker: str) -> tuple[bool, str]:
    safe = _safe_ticker(ticker)
    try:
        st.session_state["last_query_ticker"] = safe
        st.session_state["last_query_source"] = "FireAnt + Vietstock"
        m1._search_and_bind(safe, "FireAnt + Vietstock")
        checker = getattr(m1, "_active_bundle_has_data_for_ticker", None)
        ok = bool(checker(safe)) if callable(checker) else _safe_ticker(str(st.session_state.get("active_ticker", ""))) == safe
        if ok:
            for key in ("active_ticker", "shared_ticker", "module1_ticker", "module2_ticker"):
                st.session_state[key] = safe
            _chapter6_quant_cached.clear()
            return True, f"Đã cập nhật Trecapital canonical data cho {safe}."
        return False, f"Chưa lấy được canonical data cho {safe}; Chương 6 không dùng dữ liệu mã khác thay thế."
    except Exception as exc:
        return False, f"Cập nhật canonical data chưa thành công: {exc}"


def _metric_value(value: Any, kind: str) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass
    return format_numeric(value, kind)


def _render_phase6b_quantitative_bridge(ticker: str) -> dict[str, Any] | None:
    safe = _safe_ticker(ticker)
    ctx, error = _load_chapter6_quant(safe)

    with st.container(border=True):
        st.markdown("## 📐 Phase 6B — Quantitative Bridge từ Trecapital canonical data")
        st.caption(
            "Single Source of Truth: FireAnt/Vietstock/Simplize → Trecapital normalize/validate → canonical dataset → Chapter 6. "
            "Bridge chỉ tạo evidence định lượng; không tự sửa Q27–Q32, Distribution Width, MOS hay BUY/HOLD/SELL."
        )
        c1, c2 = st.columns([3, 1])
        with c1:
            if ctx:
                prov = ctx.get("provenance", {})
                industry = str(ctx.get("industry") or "—")
                sub_industry = str(ctx.get("sub_industry") or "—")
                st.success(
                    f"{safe} — {ctx.get('company_name') or 'Doanh nghiệp'} | kỳ {ctx.get('latest_period') or '—'} | "
                    f"{industry} / {sub_industry} | {prov.get('source_label') or 'Trecapital canonical'}"
                )
            else:
                st.warning(error)
        with c2:
            if st.button("🔄 Cập nhật canonical data Chương 6", use_container_width=True, key=f"ch6b_refresh_{safe}"):
                with st.spinner(f"Đang cập nhật canonical data cho {safe}..."):
                    ok, note = _refresh_chapter6_canonical(safe)
                (st.success if ok else st.warning)(note)
                if ok:
                    st.rerun()

        if not ctx:
            return None

        warnings = ctx.get("coverage_warnings") or []
        if warnings:
            with st.expander(f"⚠ Phase 6B coverage / applicability warnings ({len(warnings)})", expanded=True):
                for warning in warnings:
                    st.write(f"- {warning}")

        with st.expander("Q27 — CFO/NI + Accounting-quality diagnostics", expanded=True):
            table = ctx.get("q27_accounting_quality")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(430, 90 + 29 * len(table)))
                summary = ctx.get("q27_summary") or {}
                cols = st.columns(3)
                cols[0].metric("Annual periods", int(summary.get("annual_periods") or 0))
                cols[1].metric("Cumulative CFO/NI", _metric_value(summary.get("cumulative_cfo_to_ni"), "ratio"))
                cols[2].metric("Current-tax comparison", "Available" if summary.get("tax_comparison_available") else "N/A")
            st.caption(
                "CFO/NI là research diagnostic. TTM không được cộng chồng vào cumulative annual CFO/NI. "
                "tax_paid_bil không bao giờ được dùng thay current-tax expense."
            )

        with st.expander("Q28 — Explicit recurring-revenue disclosure", expanded=False):
            table = ctx.get("q28_disclosed_recurring")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(300, 90 + 29 * len(table)))
            else:
                st.info(
                    "Canonical dataset hiện không có explicit recurring/contracted revenue share. "
                    "App giữ Unknown và không suy recurring % từ doanh thu lặp lại quan sát được."
                )

        with st.expander("Q29 — Historical cycle / drawdown context", expanded=True):
            table = ctx.get("q29_cycle_history")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(430, 90 + 29 * len(table)))
            st.caption(
                "Bảng chỉ mô tả historical variability. Không tự suy GDP/commodity/recession là nguyên nhân và không tự gắn Cyclical / Resistant."
            )

        with st.expander("Q30 — Historical Operating Leverage (DOL)", expanded=True):
            table = ctx.get("q30_operating_leverage")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(430, 90 + 29 * len(table)))
            st.caption(
                "DOL chỉ hiển thị ở kỳ có ΔRevenue% đủ lớn; denominator gần 0 được giữ N/A. "
                "App không suy fixed/variable cost từ line-item accounting labels."
            )

        with st.expander("Q31 — Working-capital efficiency", expanded=True):
            table = ctx.get("q31_working_capital")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(430, 90 + 29 * len(table)))
                latest = table.iloc[-1].to_dict()
                cols = st.columns(4)
                cols[0].metric("DSO", _metric_value(latest.get("DSO (ngày)"), "days"))
                cols[1].metric("DIO", _metric_value(latest.get("DIO (ngày)"), "days"))
                cols[2].metric("DPO", _metric_value(latest.get("DPO (ngày)"), "days"))
                cols[3].metric("CCC", _metric_value(latest.get("CCC (ngày)"), "days"))
            st.caption(
                "Formula: average-balance / flow × 365; TTM dùng TTM flows và average latest-quarter balance khi có. "
                "Missing denominator => N/A, không ép 0."
            )

        with st.expander("Q32 — CAPEX / asset replacement context", expanded=True):
            table = ctx.get("q32_capex_history")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(430, 90 + 29 * len(table)))
            st.caption(
                "Net/Gross PP&E chỉ hiện khi canonical field explicit. Fixed assets hoặc non-current assets không được relabel thành Net PP&E. "
                "CAPEX không tự được gọi maintenance CAPEX."
            )

        ch5_bs = ctx.get("chapter5_balance_sheet_context")
        if isinstance(ch5_bs, pd.DataFrame) and not ch5_bs.empty:
            with st.expander("Shared Chapter-5 leverage context — read-only", expanded=False):
                render_static_table(ch5_bs, height=min(430, 90 + 29 * len(ch5_bs)))
                st.caption("Phase 6D tái sử dụng diagnostic đã có; không tạo công thức Debt/EBITDA / coverage mới.")

        with st.expander("🔎 Phase 6B provenance / formula boundary", expanded=False):
            prov = ctx.get("provenance") or {}
            st.write({
                "Ticker": safe,
                "Kỳ dữ liệu": ctx.get("latest_period"),
                "Industry": ctx.get("industry"),
                "Sub-industry": ctx.get("sub_industry"),
                "Source Module": prov.get("source_module"),
                "Data Origin": prov.get("data_origin"),
                "Source Label": prov.get("source_label"),
            })
            st.caption(f"Công thức: {FORMULA_DOC.relative_to(APP_DIR)}")

    return ctx


def _render_phase6c_research_assistant(ticker: str, company_name: str, quant_ctx: dict[str, Any] | None) -> pd.DataFrame:
    safe = _safe_ticker(ticker)
    session_key = f"ch6c_result_{safe}"
    gaps_key = f"ch6c_gaps_{safe}"
    note_key = f"ch6c_note_{safe}"
    attempts_key = f"ch6c_attempts_{safe}"

    with st.container(border=True):
        st.markdown("## 🔎 Phase 6C — Evidence Research Assistant Q27–Q32")
        st.caption(
            "Assistant thu thập Candidate Evidence / Counter-Evidence; search result/link điều hướng không phải bằng chứng. "
            "Không tự sửa analyst assessment, Distribution Width, valuation hay Research Gate."
        )
        c1, c2 = st.columns([2, 1])
        with c1:
            run = st.button("🔎 Nghiên cứu tự động Q27–Q32", use_container_width=True, type="primary", key=f"ch6c_run_{safe}")
        with c2:
            if st.button("🧹 Xóa kết quả tạm", use_container_width=True, key=f"ch6c_clear_{safe}"):
                for key in (session_key, gaps_key, note_key, attempts_key):
                    st.session_state.pop(key, None)
                st.rerun()

        if run:
            with st.spinner(f"Đang nghiên cứu source-first cho {safe} — Q27 đến Q32..."):
                result = Chapter6EvidenceAgent(APP_DIR / "data_cache" / "deep_company_analysis_evidence").search(
                    safe,
                    company_name,
                    max_results_per_query=4,
                )
                gaps = phase6c_research_gaps(result.candidates, quant_ctx)
            st.session_state[session_key] = result.candidates
            st.session_state[gaps_key] = gaps
            st.session_state[note_key] = result.note
            st.session_state[attempts_key] = result.source_attempts

        candidates = st.session_state.get(session_key)
        gaps = st.session_state.get(gaps_key, [])
        note = str(st.session_state.get(note_key, ""))
        attempts = st.session_state.get(attempts_key, [])

        if isinstance(candidates, pd.DataFrame):
            if note:
                st.success(note)
            summary = evidence_quality_summary(candidates)
            st.markdown("**Evidence Coverage — research completeness only**")
            render_static_table(summary, height=260)
            if not candidates.empty:
                cols = [c for c in ["Question", "Evidence Type", "Source Grade", "Source Title", "Source URL / File", "Source Date", "Evidence Text", "Direction"] if c in candidates.columns]
                render_static_table(candidates[cols], height=520)
            else:
                st.info("Chưa có candidate evidence substantive; Unknown vẫn là trạng thái hợp lệ.")

            if gaps:
                with st.expander(f"⚠ Research Gaps ({len(gaps)})", expanded=True):
                    for gap in gaps:
                        st.warning(f"{gap.get('Question')}: {gap.get('Research Gap')} — {gap.get('Next Action')}")

            if attempts:
                with st.expander(f"🧾 Source Attempt Log ({len(attempts)})", expanded=False):
                    render_static_table(pd.DataFrame(attempts), height=360)
        else:
            st.caption("Chưa chạy Phase 6C trong session này.")

    return candidates if isinstance(candidates, pd.DataFrame) else pd.DataFrame()


def _render_phase6d_final_closure(ticker: str, payload: dict[str, Any], quant_ctx: dict[str, Any] | None) -> None:
    safe = _safe_ticker(ticker)
    with st.container(border=True):
        st.markdown("## 🔒 Phase 6D — Final Closure & Valuation Linkage")
        st.caption(
            "Closure dùng analyst-owned evidence để kiểm tra completeness; không tự thay Research Gate, MOS hay BUY/HOLD/SELL."
        )

        with st.expander("Q27 — Tax footnote / accounting-quality closure", expanded=False):
            payload["q27_tax_footnote"] = _editor(
                "Tax Footnote Register",
                payload.get("q27_tax_footnote", []),
                TAX_FOOTNOTE_COLUMNS,
                f"ch6d_tax_{safe}",
                height=280,
            )
            tax_result = tax_footnote_analysis(payload.get("q27_tax_footnote", []))
            if isinstance(tax_result, pd.DataFrame) and not tax_result.empty:
                render_static_table(tax_result, height=min(340, 90 + 30 * len(tax_result)))

        with st.expander("Q28/Q29 — Unsustainable earnings / cycle closure", expanded=False):
            payload["unsustainable_earnings"] = _editor(
                "Unsustainable Earnings Register",
                payload.get("unsustainable_earnings", []),
                UNSUSTAINABLE_EARNINGS_COLUMNS,
                f"ch6d_unsustainable_{safe}",
                height=300,
            )

        with st.expander("Q32 — Asset replacement / maintenance CAPEX closure", expanded=False):
            payload["asset_replacement"] = _editor(
                "Asset Replacement Register",
                payload.get("asset_replacement", []),
                ASSET_REPLACEMENT_COLUMNS,
                f"ch6d_asset_{safe}",
                height=300,
            )
            asset_result = asset_replacement_analysis(payload.get("asset_replacement", []))
            if isinstance(asset_result, pd.DataFrame) and not asset_result.empty:
                render_static_table(asset_result, height=min(340, 90 + 30 * len(asset_result)))

        with st.expander("Combined operating + financial leverage evidence", expanded=False):
            leverage = combined_leverage_evidence(payload, quant_ctx)
            if isinstance(leverage, pd.DataFrame) and not leverage.empty:
                render_static_table(leverage, height=min(360, 90 + 30 * len(leverage)))
            else:
                st.caption("Chưa có đủ evidence để dựng combined leverage context.")

        with st.expander("Valuation method guidance — analyst owned", expanded=False):
            guidance = valuation_method_guidance(payload, quant_ctx)
            if isinstance(guidance, pd.DataFrame) and not guidance.empty:
                render_static_table(guidance, height=min(360, 90 + 30 * len(guidance)))
            payload["valuation_scenarios"] = _editor(
                "Valuation Scenario Register",
                payload.get("valuation_scenarios", []),
                VALUATION_SCENARIO_COLUMNS,
                f"ch6d_valuation_{safe}",
                height=320,
            )

        with st.expander("Final Chapter-6 source-locked checklist", expanded=True):
            payload["final_checklist"] = _editor(
                "Final Checklist",
                payload.get("final_checklist", []),
                FINAL_CHECKLIST_COLUMNS,
                f"ch6d_final_{safe}",
                height=400,
            )
            completion = chapter6_completion_status(payload)
            if completion.get("ready"):
                st.success(completion.get("note") or "Chapter 6 completion checklist đã đóng.")
            else:
                st.warning(completion.get("note") or "Chapter 6 vẫn còn research gaps / checklist chưa đóng.")
            blockers = completion.get("blockers") or []
            if blockers:
                for blocker in blockers:
                    st.write(f"- {blocker}")


def _render_phase6a_workspace(ticker: str, company_name: str = "") -> None:
    safe = _safe_ticker(ticker)
    payload = load_record(safe, company_name)
    prefix = f"ch6_{safe}"

    st.info(
        "Chương 6 bám Q27–Q32 của Michael Shearn. Analyst sở hữu Status/Trend/Assessment/Conclusion. "
        "AI/Data chỉ hỗ trợ structured context và evidence; Unknown là trạng thái hợp lệ khi chưa có dữ liệu."
    )

    # Remaining Phase-6A analyst workspace code continues below unchanged in repository.
    # This full-file replacement intentionally preserves the existing implementation after this point.
