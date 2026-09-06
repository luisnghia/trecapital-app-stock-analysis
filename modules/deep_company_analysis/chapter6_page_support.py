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
        # _editor is commonly called from inside a question expander. Streamlit 1.40.x forbids
        # nested expanders, so the formatted preview uses a plain bordered container.
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
            table = ctx.get("q30_dol_history")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(430, 90 + 29 * len(table)))
            summary = ctx.get("q30_summary") or {}
            cols = st.columns(4)
            cols[0].metric("Valid DOL periods", int(summary.get("valid_observations") or 0))
            cols[1].metric("Median DOL", _metric_value(summary.get("median_dol"), "ratio"))
            cols[2].metric("Downside median", _metric_value(summary.get("downside_median_dol"), "ratio"))
            cols[3].metric("Upside median", _metric_value(summary.get("upside_median_dol"), "ratio"))
            st.caption(
                "DOL = %Δ EBIT / %Δ Revenue. Revenue gần như không đổi hoặc EBIT ≤ 0/sign shift được giữ trên bảng là Invalid, "
                "không bị ẩn và không tham gia median."
            )

        with st.expander("Q31 — Working Capital / CCC 5–10 năm", expanded=True):
            summary = ctx.get("q31_summary") or {}
            if not summary.get("applicable", True):
                st.warning(summary.get("status") or "N/A — not economically applicable")
                st.caption(summary.get("reason") or "")
            else:
                table = ctx.get("q31_working_capital")
                if isinstance(table, pd.DataFrame) and not table.empty:
                    render_static_table(table, height=min(460, 90 + 29 * len(table)))
                st.info(summary.get("cash_sign_convention") or "Cash impact = -ΔOWC.")
                st.caption(summary.get("reconciliation_note") or "")
            st.caption("Không tự kết luận CCC thấp hoặc negative working capital là tốt. Analyst phải xem business mechanism và tính bền vững.")

        with st.expander("Q32 — Capex intensity / D&A / FCF / PP&E age diagnostic", expanded=True):
            table = ctx.get("q32_capex_history")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(460, 90 + 29 * len(table)))
            summary = ctx.get("q32_summary") or {}
            cols = st.columns(3)
            cols[0].metric("Median Capex/Revenue", _metric_value(summary.get("median_capex_to_revenue_pct"), "percent"))
            cols[1].metric("Median Capex/D&A", _metric_value(summary.get("median_capex_to_da"), "ratio"))
            cols[2].metric("Sector relevance", str(summary.get("relevance") or "—"))
            st.warning(summary.get("maintenance_capex_guardrail") or "Maintenance capex remains analyst/source driven.")

        with st.expander("🔎 Phase 6B provenance & formula audit", expanded=False):
            table = ctx.get("provenance_table")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=360)
            st.write(ctx.get("provenance") or {})
            st.caption("Formula methodology: docs/formulas/DEEP_COMPANY_ANALYSIS_CHAPTER6_FORMULAS.md")

    return ctx


def _render_phase6c_research_assistant(ticker: str, company_name: str) -> None:
    safe = _safe_ticker(ticker)
    external_key = f"ch6c_external_candidates_{safe}"
    note_key = f"ch6c_note_{safe}"
    snapshot = st.session_state.get("module2_manipulation_snapshot")
    if not isinstance(snapshot, dict) or _safe_ticker(str(snapshot.get("ticker") or "")) != safe:
        snapshot = None

    with st.container(border=True):
        st.markdown("## 🔎 Phase 6C — Evidence & Research Assistant")
        st.caption(
            "AI/Data chỉ tìm candidate evidence, counter-evidence và research gaps. Không tự đổi Conservative/Liberal, recurring quality, "
            "cycle classification, Distribution Width, MOS, Research Gate hay BUY/HOLD/SELL."
        )

        with st.expander("Q27 — Read-only Financial Manipulation evidence bridge", expanded=True):
            if snapshot:
                table = manipulation_snapshot_table(snapshot)
                if not table.empty:
                    render_static_table(table, height=min(340, 100 + 30 * len(table)), sort_key=f"ch6c_manip_{safe}")
                st.caption(
                    "Beneish / Sloan / Modified Jones / REM được tính và sở hữu bởi Module 2. Chương 6 chỉ đọc snapshot đã tính; "
                    "dòng TTM là applicability guardrail, không phải M-Score/Jones/REM TTM giả lập."
                )
            else:
                st.info("Chưa có snapshot Module 2 cho đúng ticker trong phiên này. Mở/cập nhật Định giá chuyên sâu để Module 2 publish diagnostics, rồi quay lại Chương 6.")
                try:
                    st.page_link("pages/02_Dinh_gia_Porter_Moat.py", label="Mở Module 2 — Định giá chuyên sâu", icon="🧠")
                except Exception:
                    pass

        if st.button("🌐 Cập nhật evidence Chương 6", use_container_width=True, key=f"ch6c_refresh_{safe}"):
            with st.spinner(f"Đang tìm evidence Q27–Q32 cho {safe}..."):
                try:
                    agent = Chapter6EvidenceAgent(APP_DIR / "data_cache" / "deep_company_analysis_evidence")
                    result = agent.search(safe, company_name, max_results_per_query=3)
                    st.session_state[external_key] = result.candidates
                    st.session_state[note_key] = result.note
                    st.success(f"Đã cập nhật candidate evidence cho {safe}. Analyst cần mở nguồn và xác minh trước khi dùng làm kết luận.")
                except Exception as exc:
                    st.warning(f"Evidence search chưa hoàn tất: {exc}")

        external = st.session_state.get(external_key, pd.DataFrame())
        if not isinstance(external, pd.DataFrame):
            external = pd.DataFrame()
        internal = manipulation_snapshot_candidates(snapshot)
        pieces = [x for x in (external, internal) if isinstance(x, pd.DataFrame) and not x.empty]
        combined = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
        if not combined.empty:
            combined = combined.drop_duplicates(subset=["Question", "Title", "URL", "Snippet"], keep="first").reset_index(drop=True)

        if not external.empty:
            st.markdown("### Evidence coverage — A/B/C")
            render_static_table(evidence_quality_summary(external), height=300, sort_key=f"ch6c_quality_{safe}")
        elif not combined.empty:
            st.caption("Hiện mới có internal Module-2 diagnostic; chưa có external A/B/C evidence run trong phiên này.")

        if not combined.empty:
            st.markdown("### Candidate Evidence / Counter-Evidence")
            render_static_table(combined, height=min(560, 120 + 30 * len(combined)), sort_key=f"ch6c_candidates_{safe}")
            st.warning("Candidate ≠ verified evidence. Direction chỉ là research cue để chống confirmation bias, không phải kết luận Q27–Q32.")
        else:
            st.info("Chưa có candidate evidence trong phiên này.")

        gaps = phase6c_research_gaps(external)
        st.markdown("### Research Gaps")
        if not gaps.empty:
            render_static_table(gaps, height=min(360, 110 + 30 * len(gaps)), sort_key=f"ch6c_gaps_{safe}")

        if st.session_state.get(note_key):
            with st.expander("Research log", expanded=False):
                st.caption(str(st.session_state[note_key]))

        if not combined.empty or not gaps.empty:
            if st.button("💾 Lưu candidates + research gaps vào Evidence Matrix", use_container_width=True, key=f"ch6c_merge_{safe}"):
                current = load_record(safe)
                merged = merge_candidates_into_record(current, combined, gaps)
                save_record(safe, merged, company_name or str(current.get("company_name") or ""))
                st.success("Đã lưu candidates/research gaps. Không có analyst conclusion nào bị thay đổi.")
                st.rerun()




def _render_phase6d_final_closure(ticker: str, payload: dict[str, Any], quant_ctx: dict[str, Any] | None) -> None:
    safe = _safe_ticker(ticker)
    ctx = quant_ctx if isinstance(quant_ctx, dict) else {}
    with st.container(border=True):
        st.markdown("## 🔒 Phase 6D — Chapter 6 Final Source Closure")
        st.caption(
            "Source closure theo Shearn: tax footnote, unsustainable earnings, operating leverage × debt, asset replacement, "
            "Distribution→Valuation bridge và Final Source Checklist. Analyst vẫn sở hữu toàn bộ kết luận/assumptions."
        )

        with st.expander("Q27 — Income-tax Footnote Analyzer + Unsustainable Earnings", expanded=True):
            st.caption(
                "Current Tax phải đến từ disclosure thuế hiện hành; tax paid không được dùng thay thế. Annual-only disclosure không được chế tạo TTM."
            )
            payload["q27_tax_footnote"] = _editor(
                "Current Tax vs Income-Tax Provision — 5–10Y disclosure register",
                payload.get("q27_tax_footnote"),
                TAX_FOOTNOTE_COLUMNS,
                f"dca6d_{safe}_tax",
                height=330,
            )
            tax_view = tax_footnote_analysis(payload.get("q27_tax_footnote"))
            if not tax_view.empty:
                render_static_table(tax_view, height=min(430, 90 + 29 * len(tax_view)), sort_key=f"dca6d_{safe}_tax_analysis")
            else:
                st.info("Chưa có Current Tax + Tax Provision disclosure đủ dùng; giữ N/A thay vì proxy.")

            payload["q27_unsustainable_earnings"] = _editor(
                "Unsustainable Earnings / One-off Register",
                payload.get("q27_unsustainable_earnings"),
                UNSUSTAINABLE_EARNINGS_COLUMNS,
                f"dca6d_{safe}_oneoffs",
                height=310,
            )
            st.caption(
                "Bao gồm debt-retirement gains/losses, restructuring/write-offs và temporary cuts to advertising/R&D/maintenance khi có bằng chứng."
            )

        with st.expander("Q30 — Operating Leverage × Balance-Sheet Debt", expanded=True):
            leverage = combined_leverage_evidence(
                ctx.get("q30_summary") if ctx else {},
                ctx.get("chapter5_balance_sheet_context") if ctx else None,
            )
            if not leverage.empty:
                render_static_table(leverage, height=210, sort_key=f"dca6d_{safe}_leverage")
            else:
                st.info("Chưa đủ DOL và/hoặc Chapter-5 balance-sheet context để hiển thị combined leverage evidence.")
            st.caption(
                "Không tạo distress score. Bảng chỉ đặt DOL cạnh Net Debt, Debt/EBITDA và interest coverage để analyst đánh giá rủi ro kết hợp."
            )

        with st.expander("Q32 — Asset Replacement / PP&E Age Register", expanded=True):
            payload["q32_asset_replacement"] = _editor(
                "Asset Replacement Register",
                payload.get("q32_asset_replacement"),
                ASSET_REPLACEMENT_COLUMNS,
                f"dca6d_{safe}_asset_replacement",
                height=350,
            )
            asset_view = asset_replacement_analysis(payload.get("q32_asset_replacement"))
            if not asset_view.empty:
                render_static_table(asset_view, height=min(440, 90 + 29 * len(asset_view)), sort_key=f"dca6d_{safe}_asset_analysis")
            st.caption(
                "Net/Gross PP&E chỉ là diagnostic. Phải xem asset class, land/non-depreciable assets, remaining life, replacement timing "
                "và accelerated-depreciation comparability trước khi suy replacement burden."
            )

        with st.expander("Distribution Width → Valuation Method Bridge", expanded=True):
            guidance = valuation_method_guidance(str(payload.get("earnings_distribution_width") or "Unknown"))
            st.info(f"{guidance['guidance']} | {guidance['boundary']}")
            payload["valuation_method_selected"] = _select(
                "Analyst valuation-method selection",
                payload.get("valuation_method_selected"),
                (
                    "Unknown",
                    "Point estimate / normalized earnings or FCF",
                    "Hybrid point estimate + scenarios",
                    "Bear / Base / Bull scenario analysis",
                    "Analyst custom",
                ),
                f"dca6d_{safe}_valuation_method",
            )
            payload["valuation_bridge_note"] = st.text_area(
                "Valuation-method rationale / limitation",
                value=str(payload.get("valuation_bridge_note") or ""),
                key=f"dca6d_{safe}_valuation_note",
            )
            payload["valuation_scenarios"] = _editor(
                "Bear / Base / Bull — analyst-owned scenario workspace",
                payload.get("valuation_scenarios"),
                VALUATION_SCENARIO_COLUMNS,
                f"dca6d_{safe}_scenarios",
                height=300,
            )
            st.caption("App không tự đặt probability, revenue, margin, normalized earnings/FCF, fair value hoặc MOS.")

        with st.expander("Chapter 6 Final Source Checklist & Completion Gate", expanded=True):
            payload["chapter6_final_checklist"] = _editor(
                "Source-Locked Final Checklist",
                payload.get("chapter6_final_checklist"),
                FINAL_CHECKLIST_COLUMNS,
                f"dca6d_{safe}_final_checklist",
                height=390,
            )
            status = chapter6_completion_status(payload)
            if status["blockers"]:
                st.warning("Chapter 6 chưa thể khóa Final:\n\n- " + "\n- ".join(status["blockers"]))
            else:
                st.success("Không còn blocker theo Completion Gate. Analyst có thể xác nhận Chapter 6 Complete.")
            for warning in status["warnings"]:
                st.info(warning)

            if status["ready"]:
                payload["chapter6_complete_confirmed"] = st.checkbox(
                    "✅ Analyst xác nhận Chapter 6 Complete / Source-Closed",
                    value=bool(payload.get("chapter6_complete_confirmed")),
                    key=f"dca6d_{safe}_complete",
                )
            else:
                payload["chapter6_complete_confirmed"] = False
                st.checkbox(
                    "✅ Analyst xác nhận Chapter 6 Complete / Source-Closed",
                    value=False,
                    disabled=True,
                    key=f"dca6d_{safe}_complete_disabled",
                )
            payload["chapter6_completion_note"] = st.text_area(
                "Completion note / residual uncertainty accepted by analyst",
                value=str(payload.get("chapter6_completion_note") or ""),
                key=f"dca6d_{safe}_completion_note",
            )
            final_status = chapter6_completion_status(payload)
            st.caption(f"Completion status: {final_status['status']}. Đây là research/source-completion gate, không phải Research Gate đầu tư.")

def render_chapter6_tab(default_ticker: str = "") -> None:
    st.subheader("Chương 6 — Đánh giá phân phối lợi nhuận & dòng tiền")
    st.caption(
        "Michael Shearn Q27–Q32 | Phase 6A + 6B canonical bridge + 6C Evidence Assistant + 6D Final Source Closure. "
        "Mục tiêu là hiểu độ rộng/predictability của earnings & cash-flow distribution."
    )

    with st.expander("📘 Source lock, ranh giới phân tích & format", expanded=True):
        st.markdown(
            """
**Mục tiêu:** không cố dự báo một con số lợi nhuận tương lai duy nhất. Chương 6 đánh giá **độ rộng của phân phối earnings/cash flow** và những yếu tố có thể khiến kết quả thực tế lệch khỏi kỳ vọng.

- **Q27:** tìm true operating earnings; kiểm tra tax/book, CFO/NI, revenue recognition, capitalization, discretionary costs, depreciation/estimate changes, restructuring và reserves.
- **Q28:** phân biệt **Contractual recurring / Behavioral recurring / Repeat purchase / One-off**; không tự suy ra recurring share nếu thiếu disclosure/evidence.
- **Q29:** cyclical / countercyclical / recession-resistant phải dựa trên company economics, customer cycle, supply/demand và downturn evidence.
- **Q30:** Phase 6A phân rã fixed / variable / semi-variable; Phase 6B hiển thị historical DOL có invalid-row guardrails.
- **Q31:** không dùng quy tắc máy móc `CCC thấp = tốt` hay `negative WC = tốt`.
- **Q32:** maintenance capex theo thứ tự **company disclosure → analyst estimate có evidence → depreciation rough proxy gắn nhãn rõ → Unknown**. Total capex không được mặc định là maintenance capex.

**Không weighted score 0–100. Không tự đổi MOS. Không BUY/HOLD/SELL.**
            """
        )
        st.success(
            "Format lock: tỷ đồng = 0 số lẻ; % = 1 số lẻ; hệ số = 1 số lẻ; "
            "bảng số read-only dùng st.html(), fixed layout + wrap; âm đỏ, dương xanh ngọc theo heat intensity."
        )
        st.caption(
            f"Approved source lock: `{SOURCE_LOCK_DOC.relative_to(APP_DIR)}` | "
            f"Formula boundary: `{FORMULA_DOC.relative_to(APP_DIR)}`"
        )

    safe_default = _safe_ticker(default_ticker) or "DGC"
    ticker = _safe_ticker(
        st.text_input("Mã cổ phiếu", value=safe_default, key="dca_ch6_ticker_input")
    ) or safe_default
    st.session_state["dca_ch6_ticker"] = ticker

    payload = load_record(ticker)
    payload["ticker"] = ticker
    payload["company_name"] = st.text_input(
        "Tên doanh nghiệp (analyst, optional)",
        value=str(payload.get("company_name") or ""),
        key=f"dca_ch6_company_{ticker}",
    )

    quant_ctx = _render_phase6b_quantitative_bridge(ticker)
    _render_phase6c_research_assistant(ticker, str(payload.get("company_name") or ""))

    with st.expander("Q27 — Accounting standards: Conservative hay Liberal?", expanded=True):
        st.caption(
            "Mục tiêu theo Shearn là tiến gần true operating earnings, không phải gắn nhãn gian lận từ một ratio riêng lẻ."
        )
        _question_controls(payload, "Q27", f"dca6_{ticker}")
        q = payload["q27"]
        q["tax_book_difference"] = _select(
            "27A — Tax vs Book Earnings",
            q.get("tax_book_difference"),
            ("Unknown", "Small / conservative", "Material", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_tax",
        )
        q["cfo_vs_net_income"] = _select(
            "27B — CFO vs Net Income",
            q.get("cfo_vs_net_income"),
            ("Unknown", "Closely approximates", "Persistent gap", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_cfo",
        )
        q["revenue_recognition"] = _select(
            "27C — Revenue recognition",
            q.get("revenue_recognition"),
            ("Unknown", "When earned", "Potentially front-loaded", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_rev",
        )
        q["expense_vs_capitalize"] = _select(
            "27D — Expense vs capitalize",
            q.get("expense_vs_capitalize"),
            ("Unknown", "Expenses quickly", "Potential capitalization concern", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_cap",
        )
        q["discretionary_costs"] = _select(
            "27E — Discretionary costs",
            q.get("discretionary_costs"),
            ("Unknown", "No smoothing evidence", "Potential smoothing", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_disc",
        )
        q["depreciation_assumptions"] = _select(
            "27F — Depreciation / estimate assumptions",
            q.get("depreciation_assumptions"),
            ("Unknown", "Conservative / stable", "Potentially liberal", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_dep",
        )
        q["restructuring_charges"] = _select(
            "27G — Restructuring / one-offs",
            q.get("restructuring_charges"),
            ("Unknown", "No concern found", "Potential concern", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_restruct",
        )
        q["reserve_quality"] = _select(
            "Reserve quality",
            q.get("reserve_quality"),
            ("Unknown", "Well matched to outcomes", "Over/under-reserving concern", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_reserve",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Conservative", "Balanced", "Liberal", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_overall",
        )
        q["true_operating_earnings_note"] = st.text_area(
            "True operating earnings / adjustments cần xem xét",
            value=str(q.get("true_operating_earnings_note") or ""),
            key=f"dca6_{ticker}_q27_true",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q27",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q27_conclusion",
        )
        payload["q27_accounting_quality"] = _editor(
            "Accounting Quality Investigation Register",
            payload.get("q27_accounting_quality"),
            ACCOUNTING_QUALITY_COLUMNS,
            f"dca6_{ticker}_q27_table",
            height=340,
        )
        payload["q27_reserve_rollforward"] = _editor(
            "Reserve / Provision Roll-forward — Tables 6.1–6.2",
            payload.get("q27_reserve_rollforward"),
            RESERVE_ROLLFORWARD_COLUMNS,
            f"dca6_{ticker}_q27_reserve_rollforward",
            height=320,
        )
        st.info(
            "Không tính Beneish lần thứ hai tại đây. Phase 6C chỉ nhận read-only evidence/cảnh báo "
            "từ Module Manipulation; analyst vẫn quyết định Conservative / Mixed / Liberal."
        )

    with st.expander("Q28 — Revenue Durability: recurring hay one-off?", expanded=False):
        st.caption(
            "Contractual recurring khác Behavioral recurring; Repeat purchase cũng không được relabel thành contracted revenue."
        )
        _question_controls(payload, "Q28", f"dca6_{ticker}")
        q = payload["q28"]
        q["recurring_revenue_share"] = st.text_input(
            "Recurring revenue share (chỉ nhập khi có nguồn hoặc analyst estimate rõ)",
            value=str(q.get("recurring_revenue_share") or ""),
            key=f"dca6_{ticker}_q28_share",
        )
        q["recurring_revenue_share_source"] = _select(
            "Nguồn recurring revenue share",
            q.get("recurring_revenue_share_source"),
            ("Unknown", "Company disclosed", "Analyst estimate with evidence", "N/A"),
            f"dca6_{ticker}_q28_share_source",
        )
        q["starting_revenue_base"] = _select(
            "Starting revenue base",
            q.get("starting_revenue_base"),
            ("Unknown", "High recurring base", "Mixed", "Mostly resets", "N/A"),
            f"dca6_{ticker}_q28_base",
        )
        q["dependence_on_new_sales"] = _select(
            "Dependence on new sales/products",
            q.get("dependence_on_new_sales"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q28_new",
        )
        q["expense_budget_visibility"] = _select(
            "Expense budget visibility",
            q.get("expense_budget_visibility"),
            ("Unknown", "High", "Medium", "Low", "N/A"),
            f"dca6_{ticker}_q28_budget",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Predominantly recurring", "Mixed", "Predominantly one-off", "N/A"),
            f"dca6_{ticker}_q28_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q28",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q28_conclusion",
        )
        payload["q28_revenue_streams"] = _editor(
            "Revenue Durability Map",
            payload.get("q28_revenue_streams"),
            RECURRING_REVENUE_COLUMNS,
            f"dca6_{ticker}_q28_table",
            height=330,
        )

    with st.expander("Q29 — Cycle Exposure Map", expanded=False):
        st.caption(
            "Không gắn nhãn recession-resistant chỉ vì một downturn trước đó tốt; phải kiểm tra company economics và supply/demand context."
        )
        _question_controls(payload, "Q29", f"dca6_{ticker}")
        q = payload["q29"]
        q["cycle_classification"] = _select(
            "Analyst cycle classification",
            q.get("cycle_classification"),
            ("Unknown", "Cyclical", "Countercyclical", "Recession-resistant", "Mixed", "N/A"),
            f"dca6_{ticker}_q29_class",
        )
        q["purchase_deferrability"] = _select(
            "Customer purchase deferrability",
            q.get("purchase_deferrability"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q29_defer",
        )
        q["recurring_revenue_protection"] = _select(
            "Recurring-revenue protection",
            q.get("recurring_revenue_protection"),
            ("Unknown", "Strong", "Moderate", "Weak", "N/A"),
            f"dca6_{ticker}_q29_rec",
        )
        q["customer_budget_importance"] = _select(
            "Share of customer budget / necessity",
            q.get("customer_budget_importance"),
            ("Unknown", "Low / easy to keep", "Moderate", "High / cuttable", "Mixed", "N/A"),
            f"dca6_{ticker}_q29_budget",
        )
        q["customer_cycle_exposure"] = _select(
            "Customer exposure to economic cycle",
            q.get("customer_cycle_exposure"),
            ("Unknown", "Low", "Medium", "High", "Mixed", "N/A"),
            f"dca6_{ticker}_q29_customer",
        )
        q["supply_demand_distortion"] = _select(
            "Past supply/demand distortion?",
            q.get("supply_demand_distortion"),
            ("Unknown", "No evidence", "Possible", "Material", "N/A"),
            f"dca6_{ticker}_q29_supply",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Narrow earnings distribution", "Moderate", "Wide earnings distribution", "Mixed", "N/A"),
            f"dca6_{ticker}_q29_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q29",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q29_conclusion",
        )
        payload["q29_cycle_drivers"] = _editor(
            "Cycle Driver / Downturn Evidence Map",
            payload.get("q29_cycle_drivers"),
            CYCLE_COLUMNS,
            f"dca6_{ticker}_q29_table",
            height=330,
        )

    with st.expander("Q30 — Operating leverage tác động earnings thế nào?", expanded=False):
        st.caption(
            "Phase 6A phân rã cost structure. DOL lịch sử, downside/upside sensitivity và stress test thuộc Phase 6B."
        )
        _question_controls(payload, "Q30", f"dca6_{ticker}")
        q = payload["q30"]
        q["operating_leverage"] = _select(
            "Operating leverage",
            q.get("operating_leverage"),
            ("Unknown", "Low", "Medium", "High", "Mixed", "N/A"),
            f"dca6_{ticker}_q30_dol",
        )
        q["fixed_cost_intensity"] = _select(
            "Fixed-cost intensity",
            q.get("fixed_cost_intensity"),
            ("Unknown", "Low", "Medium", "High", "Mixed", "N/A"),
            f"dca6_{ticker}_q30_fixed",
        )
        q["cost_flexibility"] = _select(
            "Cost flexibility",
            q.get("cost_flexibility"),
            ("Unknown", "High", "Medium", "Low", "Mixed", "N/A"),
            f"dca6_{ticker}_q30_flex",
        )
        q["forecast_difficulty"] = _select(
            "Earnings forecast difficulty",
            q.get("forecast_difficulty"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q30_forecast",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Favorable / low amplification", "Neutral", "Risky / high amplification", "Mixed", "N/A"),
            f"dca6_{ticker}_q30_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q30",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q30_conclusion",
        )
        payload["q30_cost_structure"] = _editor(
            "Cost Structure Matrix — Tables 6.3–6.5 logic",
            payload.get("q30_cost_structure"),
            COST_STRUCTURE_COLUMNS,
            f"dca6_{ticker}_q30_table",
            height=320,
        )

    with st.expander("Q31 — Working capital tác động cash flow thế nào?", expanded=False):
        st.caption(
            "Theo Shearn cần xem nhiều năm DSO/DIO/DPO/CCC và giải thích nguyên nhân. Phase 6A lưu cơ chế; Phase 6B mới tính canonical history."
        )
        _question_controls(payload, "Q31", f"dca6_{ticker}")
        q = payload["q31"]
        q["working_capital_model"] = st.text_area(
            "Working-capital mechanism của doanh nghiệp",
            value=str(q.get("working_capital_model") or ""),
            key=f"dca6_{ticker}_q31_model",
        )
        q["ccc_direction"] = _select(
            "CCC direction",
            q.get("ccc_direction"),
            ("Unknown", "Improving", "Stable", "Deteriorating", "Volatile", "N/A"),
            f"dca6_{ticker}_q31_ccc",
        )
        q["ccc_change_quality"] = _select(
            "Quality of CCC change",
            q.get("ccc_change_quality"),
            ("Unknown", "Sustainable", "Partly sustainable", "Temporary", "Adverse", "N/A"),
            f"dca6_{ticker}_q31_quality",
        )
        q["negative_working_capital"] = _select(
            "Negative working capital model",
            q.get("negative_working_capital"),
            ("Unknown", "No", "Yes — structurally favorable", "Yes — liquidity-sensitive", "Mixed", "N/A"),
            f"dca6_{ticker}_q31_negative",
        )
        q["liquidity_dependency"] = _select(
            "Liquidity dependency",
            q.get("liquidity_dependency"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q31_liq",
        )
        q["normalization_needed"] = _select(
            "Normalize temporary WC benefit?",
            q.get("normalization_needed"),
            ("Unknown", "No", "Possibly", "Yes", "N/A"),
            f"dca6_{ticker}_q31_norm",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Cash-generative", "Neutral", "Cash-absorbing", "Mixed", "N/A"),
            f"dca6_{ticker}_q31_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q31",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q31_conclusion",
        )
        payload["q31_working_capital"] = _editor(
            "Working Capital Mechanism Register — Table 6.6 logic",
            payload.get("q31_working_capital"),
            WORKING_CAPITAL_COLUMNS,
            f"dca6_{ticker}_q31_table",
            height=310,
        )

    with st.expander("Q32 — Capital-expenditure requirements cao hay thấp?", expanded=False):
        st.caption(
            "Maintenance capex hierarchy: disclosure → analyst estimate có evidence → depreciation rough proxy gắn nhãn rõ → Unknown."
        )
        _question_controls(payload, "Q32", f"dca6_{ticker}")
        q = payload["q32"]
        q["capital_intensity"] = _select(
            "Capital intensity",
            q.get("capital_intensity"),
            ("Unknown", "Low", "Medium", "High", "Mixed", "N/A"),
            f"dca6_{ticker}_q32_intensity",
        )
        q["maintenance_capex_visibility"] = _select(
            "Maintenance capex visibility",
            q.get("maintenance_capex_visibility"),
            ("Unknown", "Disclosed / supportable", "Partial", "Not separately disclosed", "N/A"),
            f"dca6_{ticker}_q32_maintvis",
        )
        q["maintenance_vs_growth_split"] = _select(
            "Maintenance vs growth split",
            q.get("maintenance_vs_growth_split"),
            ("Unknown", "Supportable", "Partly supportable", "Not supportable", "N/A"),
            f"dca6_{ticker}_q32_split",
        )
        q["maintenance_capex_method"] = _select(
            "Maintenance capex method",
            q.get("maintenance_capex_method"),
            MAINTENANCE_CAPEX_METHOD_OPTIONS,
            f"dca6_{ticker}_q32_method",
        )
        if q["maintenance_capex_method"] == "Depreciation rough proxy — clearly labelled":
            st.warning(
                "Depreciation chỉ là rough proxy theo Shearn trong trường hợp phù hợp. Ghi rõ vì sao hợp lý, "
                "asset age/growth context và giới hạn; không relabel thành company-disclosed maintenance capex."
            )
            q["depreciation_proxy_note"] = st.text_area(
                "Lý do / giới hạn khi dùng depreciation proxy",
                value=str(q.get("depreciation_proxy_note") or ""),
                key=f"dca6_{ticker}_q32_dep_proxy_note",
            )
        q["regulatory_capex_burden"] = _select(
            "Regulatory / mandatory capex burden",
            q.get("regulatory_capex_burden"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q32_reg",
        )
        q["deferred_maintenance_risk"] = _select(
            "Deferred maintenance risk",
            q.get("deferred_maintenance_risk"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q32_defer",
        )
        q["asset_age_replacement_risk"] = _select(
            "Asset-age / replacement risk",
            q.get("asset_age_replacement_risk"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q32_age",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Low capex burden", "Moderate", "High capex burden", "Mixed", "N/A"),
            f"dca6_{ticker}_q32_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q32",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q32_conclusion",
        )
        payload["q32_capex_register"] = _editor(
            "Capex Register",
            payload.get("q32_capex_register"),
            CAPEX_COLUMNS,
            f"dca6_{ticker}_q32_table",
            height=320,
        )

    with st.expander("Evidence, Counter-evidence & Research Gaps", expanded=False):
        payload["evidence_matrix"] = _editor(
            "Evidence Matrix",
            payload.get("evidence_matrix"),
            EVIDENCE_COLUMNS,
            f"dca6_{ticker}_evidence",
            height=320,
        )
        payload["research_gaps_table"] = _editor(
            "Research Gaps",
            payload.get("research_gaps_table"),
            RESEARCH_GAP_COLUMNS,
            f"dca6_{ticker}_gaps",
            height=260,
        )

    st.markdown("### Chapter 6 — Earnings & Cash-flow Predictability Matrix")
    payload["earnings_distribution_width"] = _select(
        "Earnings/Cash-flow Distribution",
        payload.get("earnings_distribution_width"),
        DISTRIBUTION_WIDTH_OPTIONS,
        f"dca6_{ticker}_distribution_width",
    )
    payload["earnings_distribution_matrix"] = _editor(
        "Predictability Matrix — không weighted score",
        payload.get("earnings_distribution_matrix"),
        DISTRIBUTION_MATRIX_COLUMNS,
        f"dca6_{ticker}_distribution_matrix",
        height=285,
    )
    st.caption(
        "Không tính điểm 0–100 và không tự điều chỉnh MOS. Distribution là kết luận của analyst từ Q27–Q32."
    )
    if payload["earnings_distribution_width"] in {"Moderately Wide", "Wide"}:
        st.info(
            "Distribution rộng: ở phase định giá sau này app có thể gợi ý Bear/Base/Bull, normalized earnings/FCF và wider MOS review, "
            "nhưng không tự thay assumptions."
        )
    elif payload["earnings_distribution_width"] in {"Narrow", "Moderately Narrow"}:
        st.info(
            "Distribution hẹp: single-point valuation có thể hữu ích hơn, nhưng đây vẫn không phải Buy Signal."
        )

    payload["earnings_distribution_summary"] = st.text_area(
        "Phân phối earnings/cash flow: hẹp hay rộng, vì sao?",
        value=str(payload.get("earnings_distribution_summary") or ""),
        key=f"dca6_{ticker}_dist",
    )
    payload["narrowing_factors"] = st.text_area(
        "Các yếu tố làm hẹp distribution",
        value=str(payload.get("narrowing_factors") or ""),
        key=f"dca6_{ticker}_narrow",
    )
    payload["widening_factors"] = st.text_area(
        "Các yếu tố làm rộng distribution",
        value=str(payload.get("widening_factors") or ""),
        key=f"dca6_{ticker}_wide",
    )
    payload["critical_unknowns"] = st.text_area(
        "Critical unknowns",
        value=str(payload.get("critical_unknowns") or ""),
        key=f"dca6_{ticker}_unknowns",
    )
    payload["analyst_summary"] = st.text_area(
        "Kết luận Chapter 6 của analyst",
        value=str(payload.get("analyst_summary") or ""),
        key=f"dca6_{ticker}_summary",
    )

    _render_phase6d_final_closure(ticker, payload, quant_ctx)

    warnings = research_gap_warnings(payload)
    if warnings:
        st.warning("Consistency / Research Gap:\n\n- " + "\n- ".join(warnings))

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Lưu Chapter 6", use_container_width=True, key=f"dca6_{ticker}_save"):
            save_record(ticker, payload, str(payload.get("company_name") or ""))
            st.success("Đã lưu Chapter 6. Không có analyst conclusion nào bị AI/Data ghi đè.")
    with c2:
        if st.button("📸 Lưu snapshot Chapter 6", use_container_width=True, key=f"dca6_{ticker}_snapshot"):
            snapshot_id = create_snapshot(ticker, payload)
            st.success(f"Đã lưu snapshot #{snapshot_id}.")

    snapshots = list_snapshots(ticker, limit=8)
    if snapshots:
        with st.expander("🕘 Snapshot gần nhất", expanded=False):
            snapshot_table = pd.DataFrame([
                {
                    "Snapshot": int(item["id"]),
                    "Created": str(item["created_at"]),
                    "Research completion": str(item["understanding_status"]),
                }
                for item in snapshots
            ])
            render_static_table(snapshot_table, height=min(330, 90 + 30 * len(snapshot_table)), sort_key=f"ch6_snapshots_{ticker}")


__all__ = ["render_chapter6_tab"]
