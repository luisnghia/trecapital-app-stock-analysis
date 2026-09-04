from __future__ import annotations

"""Unified-page support for Chapter 5 Phase 5B quantitative bridge."""

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter2_page_support import _active_paths, _path_signature
from modules.deep_company_analysis.chapter5 import load_record, render_chapter5, save_record
from modules.deep_company_analysis.chapter5_quant import build_chapter5_quant_context
from modules.deep_company_analysis.chapter5_evidence import (
    Chapter5EvidenceAgent,
    evidence_quality_summary,
    guardrails as phase5c_guardrails,
    merge_candidates_into_record,
    research_gaps,
)


def _safe_ticker(value: Any) -> str:
    try:
        return m1._safe_ticker(value)
    except Exception:
        return "".join(ch for ch in str(value or "").upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _heat_style(df: pd.DataFrame):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    styler = df.style
    if numeric_cols:
        def _heat(value):
            try:
                num = float(value)
            except Exception:
                return ""
            if num < 0:
                return "color:#B91C1C;font-weight:700;"
            if num > 0:
                return "color:#047857;"
            return ""
        styler = styler.map(_heat, subset=numeric_cols)
    return styler


@st.cache_data(ttl=120, show_spinner=False)
def _quant_cached(
    ticker: str,
    overview_path: str,
    year_path: str,
    quarter_path: str,
    overview_sig: tuple[int, int],
    year_sig: tuple[int, int],
    quarter_sig: tuple[int, int],
    source_label: str,
    adjustments_signature: tuple[tuple[str, str, str], ...],
):
    del overview_sig, year_sig, quarter_sig
    safe = _safe_ticker(ticker)
    company = m1._load_overview_cached(overview_path, safe)
    annual_raw = m1._load_timeseries_cached(year_path, safe, "Y", 11)
    quarterly = m1._load_timeseries_cached(quarter_path, safe, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    adjustments = [
        {"Adjustment": name, "Amount": amount, "Included?": included}
        for name, amount, included in adjustments_signature
    ]
    return build_chapter5_quant_context(
        safe,
        company_name,
        annual,
        source_label=source_label,
        adjustments=adjustments,
    )


def _adjustment_signature(record: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    rows = record.get("q26_roic_adjustments") if isinstance(record, dict) else []
    if not isinstance(rows, list):
        return tuple()
    out: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append((
            str(row.get("Adjustment") or ""),
            str(row.get("Amount") or ""),
            str(row.get("Included?") or ""),
        ))
    return tuple(out)


def load_chapter5_quant(ticker: str, record: dict[str, Any]):
    safe = _safe_ticker(ticker)
    paths, source_label = _active_paths(safe)
    if not paths:
        return None, f"{safe}: chưa có canonical statement cache trên máy."
    overview, year, quarter = paths
    try:
        ctx = _quant_cached(
            safe,
            str(overview), str(year), str(quarter),
            _path_signature(overview), _path_signature(year), _path_signature(quarter),
            source_label,
            _adjustment_signature(record),
        )
        return ctx or None, "" if ctx else f"{safe}: canonical bundle chưa có dữ liệu usable."
    except Exception as exc:
        return None, f"{safe}: không dựng được Chapter 5 quantitative context: {exc}"


def _refresh_target(ticker: str) -> tuple[bool, str]:
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
            _quant_cached.clear()
            return True, f"Đã cập nhật canonical data cho {safe}."
        return False, f"Chưa lấy được canonical data cho {safe}; app không dùng dữ liệu mã khác thay thế."
    except Exception as exc:
        return False, f"Cập nhật canonical data chưa thành công: {exc}"


def render_phase5b_quantitative_bridge(ticker: str) -> tuple[str, str]:
    safe = _safe_ticker(ticker) or "DGC"
    record = load_record(safe)
    ctx, error = load_chapter5_quant(safe, record)
    company_name = str((ctx or {}).get("company_name") or record.get("company_name") or "")

    with st.container(border=True):
        st.markdown("### 📐 Phase 5B — Quantitative Bridge từ Trecapital canonical data")
        st.caption(
            "Bridge này chỉ đưa dữ liệu định lượng vào Q22/Q25/Q26. Nó không tự chọn operating KPI trọng yếu, "
            "không chấm bảng cân đối mạnh/yếu, không tự gọi ROIC là chất lượng cao và không kết luận compounder."
        )
        c1, c2 = st.columns([3, 1])
        with c1:
            if ctx:
                prov = ctx.get("provenance", {})
                st.success(
                    f"{safe} — {company_name or 'Doanh nghiệp'} | kỳ {ctx.get('latest_period') or '—'} | "
                    f"{prov.get('source_label') or 'Trecapital'}"
                )
            else:
                st.warning(error)
        with c2:
            if st.button("🔄 Cập nhật data Chương 5", use_container_width=True, key=f"ch5b_refresh_{safe}"):
                with st.spinner(f"Đang cập nhật canonical data cho {safe}..."):
                    ok, note = _refresh_target(safe)
                (st.success if ok else st.warning)(note)
                if ok:
                    st.rerun()

        if not ctx:
            return safe, company_name

        with st.expander("Q22 — Financial / operating context 10 năm", expanded=True):
            q22 = ctx.get("q22_context")
            if isinstance(q22, pd.DataFrame) and not q22.empty:
                st.dataframe(_heat_style(q22), use_container_width=True, hide_index=True, height=min(420, 70 + 28 * len(q22)))
            else:
                st.caption("Chưa có lịch sử canonical đủ dùng.")
            st.warning(
                "Các dòng này là context định lượng, KHÔNG tự thay thế operating metrics đặc thù ngành. "
                "Analyst vẫn phải chọn KPI Q22 theo business model và kiểm tra định nghĩa có so sánh được hay không."
            )

        with st.expander("Q25 — Balance Sheet quantitative context", expanded=True):
            q25 = ctx.get("q25_context")
            if isinstance(q25, pd.DataFrame) and not q25.empty:
                st.dataframe(_heat_style(q25), use_container_width=True, hide_index=True, height=min(420, 70 + 28 * len(q25)))
                latest = q25.iloc[-1].to_dict()
                cols = st.columns(5)
                def _fmt(value, suffix=""):
                    try:
                        if value is None or pd.isna(value):
                            return "—"
                        return f"{float(value):,.1f}{suffix}"
                    except Exception:
                        return "—"
                cols[0].metric("Nợ vay ròng", _fmt(latest.get("Nợ vay ròng (tỷ)"), " tỷ"))
                cols[1].metric("Debt/EBITDA", _fmt(latest.get("Debt/EBITDA (x)"), "x"))
                cols[2].metric("EBIT/Interest", _fmt(latest.get("EBIT/Interest (x)"), "x"))
                cols[3].metric("CFO/Interest", _fmt(latest.get("CFO/Interest (x)"), "x"))
                cols[4].metric("Current Ratio", _fmt(latest.get("Current Ratio (x)"), "x"))
            else:
                st.caption("Canonical statements hiện chưa có đủ debt/liquidity fields để tính các ratio này.")
            st.caption(
                "Debt maturity, covenant, recourse và off-balance-sheet obligations vẫn phải lấy từ disclosure/analyst register. "
                "Không dùng một ngưỡng Debt/EBITDA máy móc để kết luận Strong/Weak Balance Sheet."
            )

        with st.expander("Q26 — Canonical ROIC + Shearn analytical variants", expanded=True):
            v = ctx.get("q26_variants")
            if isinstance(v, pd.DataFrame) and not v.empty:
                show = v.copy()
                for col in ("Value %", "Denominator (tỷ)"):
                    if col in show.columns:
                        show[col] = pd.to_numeric(show[col], errors="coerce")
                st.dataframe(_heat_style(show), use_container_width=True, hide_index=True, height=330)
            else:
                st.caption("Chưa có dữ liệu đủ để dựng ROIC views.")
            st.info(
                "Canonical ROIC là Single Source of Truth. Các dòng Shearn analytical chỉ là góc nhìn điều chỉnh. "
                "ROIC ex excess cash KHÔNG được tính nếu analyst chưa xác nhận lượng excess cash; off-BS adjusted cũng vậy."
            )

            diag = ctx.get("q26_distortions")
            if isinstance(diag, pd.DataFrame) and not diag.empty:
                st.markdown("**ROIC Distortion Diagnostics — review only**")
                st.dataframe(diag, use_container_width=True, hide_index=True)

            reinv = ctx.get("reinvestment_context")
            if isinstance(reinv, pd.DataFrame) and not reinv.empty:
                st.markdown("**Incremental-return / Reinvestment context — Trecapital extension**")
                st.dataframe(_heat_style(reinv), use_container_width=True, hide_index=True, height=min(300, 80 + 28 * len(reinv)))
                st.caption("Incremental ROIC có thể bị méo bởi chu kỳ/base effect. Không tự suy High ROIC + High reinvestment = compounder.")

        with st.expander("🔎 Data provenance & formula boundary", expanded=False):
            prov = ctx.get("provenance", {})
            st.write({
                "Ticker": safe,
                "Kỳ dữ liệu": ctx.get("latest_period"),
                "Source Module": prov.get("source_module"),
                "Data Origin": prov.get("data_origin"),
                "Source Label": prov.get("source_label"),
            })
            st.caption("Công thức chi tiết: docs/formulas/DEEP_COMPANY_ANALYSIS_CHAPTER5_FORMULAS.md")

    return safe, company_name



def render_phase5c_research_assistant(ticker: str, company_name: str = "") -> None:
    """Research evidence only; never mutates analyst conclusions automatically."""
    safe = _safe_ticker(ticker) or "DGC"
    session_key = f"ch5c_result_{safe}"
    gaps_key = f"ch5c_gaps_{safe}"
    note_key = f"ch5c_note_{safe}"
    audit_key = f"ch5c_audit_{safe}"

    with st.container(border=True):
        st.markdown("### 🔎 Phase 5C — Research Assistant Q21–Q26")
        st.caption(
            "Assistant tìm Candidate Evidence + Counter-Evidence và Research Gaps. "
            "Không tự sửa Q21–Q26, không tự chọn KPI critical, không chấm Frequency/Severity, "
            "không kết luận Strong/Weak Balance Sheet, High-quality ROIC hay Compounder."
        )
        st.info(
            "Ưu tiên: nguồn doanh nghiệp/IR & công bố chính thức → nguồn tài chính độc lập → nguồn bối cảnh. "
            "Search result/link điều hướng không được coi là bằng chứng."
        )

        c1, c2 = st.columns([2, 1])
        with c1:
            run = st.button(
                "🔎 Nghiên cứu tự động Q21–Q26",
                use_container_width=True,
                key=f"ch5c_run_{safe}",
                type="primary",
            )
        with c2:
            if st.button("🧹 Xóa kết quả tạm", use_container_width=True, key=f"ch5c_clear_{safe}"):
                for key in (session_key, gaps_key, note_key, audit_key):
                    st.session_state.pop(key, None)
                st.rerun()

        if run:
            record = load_record(safe, company_name)
            quant_ctx, _ = load_chapter5_quant(safe, record)
            raw_dir = Path(__file__).resolve().parents[2] / "data_cache" / "deep_company_analysis_evidence"
            with st.spinner(f"Đang nghiên cứu source-first cho {safe} — Q21 đến Q26..."):
                result = Chapter5EvidenceAgent(raw_dir).search(safe, company_name, max_results_per_query=4)
                gaps = research_gaps(result.candidates, quant_ctx)
            st.session_state[session_key] = result.candidates
            st.session_state[gaps_key] = gaps
            st.session_state[note_key] = result.note
            st.session_state[audit_key] = result.source_audit

        candidates = st.session_state.get(session_key)
        gaps = st.session_state.get(gaps_key, [])
        note = str(st.session_state.get(note_key, ""))
        if isinstance(candidates, pd.DataFrame):
            if note:
                st.success(note)
            summary = evidence_quality_summary(candidates)
            st.markdown("**Evidence Coverage — Research completeness, không phải investment-quality score**")
            st.dataframe(summary, use_container_width=True, hide_index=True, height=250)

            if not candidates.empty:
                display_cols = [
                    "Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness",
                    "Title", "URL", "Snippet", "Source Method",
                ]
                st.markdown("**Candidate Evidence / Counter-Evidence**")
                st.dataframe(
                    candidates[[c for c in display_cols if c in candidates.columns]],
                    use_container_width=True,
                    hide_index=True,
                    height=430,
                )
                st.caption(
                    "Direction chỉ là hướng candidate để chống confirmation bias; analyst phải mở nguồn gốc và xác minh. "
                    "Không có Candidate nào tự chuyển thành Verified."
                )
            else:
                st.warning("Chưa lấy được Candidate Evidence usable. App không bịa evidence để lấp chỗ trống.")

            if gaps:
                st.markdown("**Research Gaps được gợi ý**")
                st.dataframe(pd.DataFrame(gaps), use_container_width=True, hide_index=True, height=min(360, 80 + 45 * len(gaps)))

            if st.button(
                "➕ Lưu Candidate Evidence + Research Gaps vào Chương 5",
                use_container_width=True,
                key=f"ch5c_save_{safe}",
                disabled=candidates.empty and not gaps,
            ):
                current = load_record(safe, company_name)
                before_analyst = {
                    q: dict(current.get(q, {})) for q in ("q21", "q22", "q23", "q24", "q25", "q26")
                }
                merged = merge_candidates_into_record(current, candidates, gaps)
                # Hard runtime assertion: research refresh must not alter analyst judgement objects.
                after_analyst = {
                    q: dict(merged.get(q, {})) for q in ("q21", "q22", "q23", "q24", "q25", "q26")
                }
                if after_analyst != before_analyst:
                    raise RuntimeError("Phase 5C guardrail breach: analyst Q21–Q26 fields changed")
                save_record(merged, create_snapshot=False)
                st.success(
                    "Đã lưu dưới trạng thái Candidate — Analyst verify. Không tạo analyst snapshot mới và không thay kết luận Q21–Q26."
                )

            with st.expander("🛡️ Phase 5C guardrails & source audit", expanded=False):
                st.write(phase5c_guardrails())
                st.write(st.session_state.get(audit_key, {}))
                st.caption(
                    "Missing evidence = Research Gap, không phải Low Risk. Media attention không phải Severity. "
                    "Canonical financial data vẫn thuộc Trecapital Data Layer / Phase 5B."
                )
        else:
            st.caption("Bấm Nghiên cứu tự động để tạo evidence candidates. Không chạy ngầm và không tự thay analyst judgement.")

def render_chapter5_tab(default_ticker: str) -> None:
    safe, company_name = render_phase5b_quantitative_bridge(default_ticker)
    render_phase5c_research_assistant(safe, company_name)
    render_chapter5(default_ticker=safe, company_name=company_name)
