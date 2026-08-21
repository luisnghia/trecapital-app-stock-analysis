from __future__ import annotations

"""Fast interactive shell for the Investment Checklist.

The expensive Trecapital data preparation lives in pages/05_Investment_Checklist.py. Streamlit
normally reruns that whole page for every selectbox change. This module keeps the complete Checklist
inside one fragment so Question/tool/section navigation reruns only the Checklist fragment. It also
collapses Q workspace reads to one SQL query and serves the static 59-question catalog from the
packaged CSV instead of PostgreSQL on every Question switch.
"""

from functools import lru_cache
import re
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from ..catalog.catalog import load_questions
from ..formula_assumptions import EVALUATION_RULES, FORMULA_ROWS, GLOSSARY, SOURCE_NOTES
from ..services.formulas import inventory_metrics
from ..services.integration_service import CATALOG_PATH
from . import page as _page
from . import portfolio_extensions as _pe
from .analytical_hub_v2 import render_analytical_hub_v2
from .present import ASSESSMENT_LABELS, STATUS_LABELS
from .watchlist_v2 import render_watchlist_v2


@lru_cache(maxsize=1)
def question_catalog_cached() -> tuple[dict[str, Any], ...]:
    """The catalog is immutable app code; do not round-trip to Supabase for every Question change."""
    return tuple(load_questions(CATALOG_PATH))


def metric_candidates_v3(df: pd.DataFrame, excluded: Iterable[str]) -> list[str]:
    """Allow analyst input for numeric columns even when the automatic source is entirely missing.

    Pandas assigns an all-None column dtype=object, which previously removed fields such as
    Provision/charge-off from the analyst editor. All-empty columns are therefore treated as eligible
    numeric inputs; explicit nonnumeric text columns remain excluded.
    """
    excluded = {str(x) for x in excluded}
    out: list[str] = []
    for col in df.columns:
        name = str(col)
        if name in excluded:
            continue
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            out.append(name)
            continue
        if series.isna().all():
            out.append(name)
            continue
        coerced = pd.to_numeric(series, errors="coerce")
        if coerced.notna().any() and coerced.notna().sum() == series.notna().sum():
            out.append(name)
    return out


# Existing editors resolve this global at runtime, so one safe patch fixes every Analytical table
# without duplicating the large rendering module.
_pe._metric_candidates = metric_candidates_v3


def render_fit_table(df: pd.DataFrame, *, css_class: str = "checklist-fit-table") -> None:
    """Render a real HTML table with wrapping. st.html avoids Markdown turning HTML into code text."""
    if df is None or df.empty:
        st.caption("Chưa có dữ liệu.")
        return
    cls = re.sub(r"[^A-Za-z0-9_-]", "-", str(css_class or "checklist-fit-table"))
    shown = df.copy().where(pd.notna(df), "—")
    table_html = shown.to_html(index=False, escape=True, border=0, classes=[cls])
    html = (
        f"<style>"
        f".wrap-{cls}{{width:100%;overflow-x:auto;margin:.35rem 0 1rem;}}"
        f"table.{cls}{{width:100%;table-layout:fixed;border-collapse:collapse;font-size:.84rem;line-height:1.35;}}"
        f"table.{cls} th{{background:#F6F2E8;color:#173F38;font-weight:800;padding:.55rem;border:1px solid #DDD4C2;"
        f"white-space:normal!important;word-break:normal;overflow-wrap:anywhere;vertical-align:top;}}"
        f"table.{cls} td{{padding:.52rem;border:1px solid #E5DED0;white-space:normal!important;word-break:normal;"
        f"overflow-wrap:anywhere;vertical-align:top;max-width:0;}}"
        f"table.{cls} tr:nth-child(even) td{{background:#FCFBF7;}}"
        f"</style><div class='wrap-{cls}'>{table_html}</div>"
    )
    # Streamlit 1.40 has st.html. It is deliberately preferred to Markdown because Markdown may
    # display an indented <table> literally as a code block, which was the production bug observed.
    if hasattr(st, "html"):
        st.html(html)
    else:  # defensive fallback for local environments older than Streamlit 1.33
        st.markdown(html, unsafe_allow_html=True)


def _fmt_current(value, kind: str = "money") -> str:
    if value is None or pd.isna(value):
        return "—"
    value = float(value)
    if kind == "pct":
        return f"{value * 100:,.1f}%"
    if kind == "ratio":
        return f"{value:,.1f}x"
    if kind == "price":
        return f"{value:,.0f} đ/cp"
    if kind == "days":
        return f"{value:,.0f} ngày"
    return f"{value:,.0f} tỷ"


def render_formula_assumptions_v3(integration, host) -> None:
    st.markdown("#### Công thức & giả định")
    st.markdown(
        "<div class='principle'><b>Nguyên tắc Trecapital:</b> công thức phải bám tài liệu nguồn; "
        "giả định nào bộ nguồn không khóa cứng phải được ghi rõ; dữ liệu thiếu không được tự điền 0; "
        "công thức và Data Layer phải đồng bộ giữa các module.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("##### Tóm tắt công thức đang dùng")
    render_fit_table(pd.DataFrame(FORMULA_ROWS), css_class="core-formula-v3")

    pre = integration.get_inventory_prefill()
    st.markdown("##### Audit số liệu hiệu lực hiện tại")
    if pre is None:
        st.info("Chưa có dữ liệu hiệu lực để thay số vào công thức. App không tự bịa số liệu.")
    else:
        metrics = inventory_metrics(
            tev=pre.tev,
            ebit=pre.ebit,
            ebitda=pre.ebitda,
            normalized_earnings=pre.normalized_earnings,
            total_debt=pre.total_debt,
            interest_expense=pre.interest_expense,
            fcf_current=pre.fcf_current,
            market_cap=pre.market_cap,
            dividend_per_share=pre.dividend_per_share,
            market_price=pre.market_price,
            target_price=pre.target_price,
        )
        audit_rows = [
            {"Chỉ tiêu": "TEV", "Số liệu": _fmt_current(pre.tev), "Công thức / cách đọc": "Market Cap + Interest-bearing Debt − Cash − Short-term Investments. Thiếu Debt ⇒ Unknown, không tự thay bằng 0."},
            {"Chỉ tiêu": "TEV/EBIT", "Số liệu": _fmt_current(metrics.get("tev_ebit"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.tev)} ÷ {_fmt_current(pre.ebit)}"},
            {"Chỉ tiêu": "TEV/EBITDA", "Số liệu": _fmt_current(metrics.get("tev_ebitda"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.tev)} ÷ {_fmt_current(pre.ebitda)}"},
            {"Chỉ tiêu": "TEV/Normalized Earnings", "Số liệu": _fmt_current(metrics.get("tev_normalized_earnings"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.tev)} ÷ {_fmt_current(pre.normalized_earnings)}"},
            {"Chỉ tiêu": "Pre-tax Earnings Yield", "Số liệu": _fmt_current(metrics.get("pretax_earnings_yield"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.ebit)} ÷ {_fmt_current(pre.tev)} — nghịch đảo TEV/EBIT theo Table 1.2."},
            {"Chỉ tiêu": "Debt/EBITDA", "Số liệu": _fmt_current(metrics.get("debt_ebitda"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.total_debt)} ÷ {_fmt_current(pre.ebitda)}"},
            {"Chỉ tiêu": "EBIT/Interest", "Số liệu": _fmt_current(metrics.get("ebit_interest"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.ebit)} ÷ {_fmt_current(pre.interest_expense)}"},
            {"Chỉ tiêu": "FCF Yield EV", "Số liệu": _fmt_current(metrics.get("fcf_yield_ev"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.fcf_current)} ÷ {_fmt_current(pre.tev)}"},
            {"Chỉ tiêu": "FCF Yield Market", "Số liệu": _fmt_current(metrics.get("fcf_yield_market"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.fcf_current)} ÷ {_fmt_current(pre.market_cap)}"},
            {"Chỉ tiêu": "Dividend Yield", "Số liệu": _fmt_current(metrics.get("dividend_yield"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.dividend_per_share, 'price')} ÷ {_fmt_current(pre.market_price, 'price')}"},
            {"Chỉ tiêu": "Stock Price vs Target", "Số liệu": _fmt_current(metrics.get("price_vs_target"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.market_price, 'price')} ÷ {_fmt_current(pre.target_price, 'price')}"},
            {"Chỉ tiêu": "MOS", "Số liệu": _fmt_current(pre.mos, "pct"), "Công thức / cách đọc": "(Target − Market Price) ÷ Target; nhận đồng bộ từ Module 2."},
            {"Chỉ tiêu": "CCC", "Số liệu": _fmt_current(pre.ccc_days, "days"), "Công thức / cách đọc": "DIO + DSO − DPO; proxy dùng số dư bình quân khi đủ dữ liệu."},
        ]
        render_fit_table(pd.DataFrame(audit_rows), css_class="formula-audit-v3")
        for note in getattr(pre, "source_notes", ()) or ():
            st.warning(note) if str(note).startswith("CẢNH BÁO") else st.caption("• " + str(note))

    st.markdown("##### Giả định/nguyên tắc đánh giá")
    for rule in EVALUATION_RULES:
        st.markdown(f"- {rule}")

    st.markdown("##### Thuật ngữ & từ viết tắt")
    render_fit_table(pd.DataFrame(GLOSSARY), css_class="formula-glossary-v3")

    st.markdown("##### Nguồn và phạm vi")
    for note in SOURCE_NOTES:
        st.caption("• " + note)
    st.caption(
        f"Overlay ngành hiệu lực: {host.company.company_type}. Công thức là tài liệu vận hành của Checklist; "
        "thay đổi công thức phải đi cùng regression test và audit trail."
    )


def _assessment_bundle(repo, company_ref_id: int, review: dict[str, Any], qid: str):
    """One SQL round-trip returns history; current/prior are derived from that same result."""
    sql = """SELECT a.*,r.as_of_date,r.review_type,r.status review_status
    FROM analyst_assessments a JOIN research_reviews r ON r.id=a.review_id
    WHERE a.company_ref_id=? AND a.question_id=?
    ORDER BY r.as_of_date DESC,a.review_id DESC,a.version_no DESC,a.id DESC"""
    with repo._conn() as c:
        history = [dict(r) for r in c.execute(sql, (company_ref_id, qid))]
    rid = int(review["id"])
    prior_id = review.get("prior_review_id")
    current = next((x for x in history if int(x.get("review_id") or 0) == rid), None)
    prior = next((x for x in history if prior_id and int(x.get("review_id") or 0) == int(prior_id)), None)
    return current, prior, history


def _fragment_rerun() -> None:
    try:
        st.rerun(scope="fragment")
    except (TypeError, ValueError):
        st.rerun()


def render_workspace_fast(repo, company_ref_id: int, review: dict[str, Any] | None, actor: str) -> None:
    st.markdown("#### Analyst Workspace — Q01–Q59")
    if not review:
        st.info("Tạo review để làm checklist.")
        return

    qs = list(question_catalog_cached())
    groups = list(dict.fromkeys(q["group_name"] for q in qs))
    c1, c2 = st.columns([1.2, 2.8])
    group = c1.selectbox("Nhóm", groups, key=f"q_group_fast_{review['id']}")
    qg = [q for q in qs if q["group_name"] == group]
    qids = [q["question_id"] for q in qg]
    q_by_id = {q["question_id"]: q for q in qg}
    qid = c2.selectbox(
        "Câu hỏi",
        qids,
        format_func=lambda x: f"{x} — {q_by_id[x]['question_vi']}",
        key=f"q_sel_fast_{review['id']}_{group}",
    )
    q = q_by_id[qid]
    current, prior, history = _assessment_bundle(repo, company_ref_id, review, qid)

    st.markdown(f"### {qid}. {q['question_vi']}")
    st.markdown(f"<div class='guide'><b>Hướng dẫn tự phân tích:</b> {q['guidance']}</div>", unsafe_allow_html=True)
    st.caption(f"Supporting tool: {q['supporting_tool'] or 'Không có'}")

    a, b = st.columns(2)
    a.markdown("**Current review**")
    a.write(current or "Chưa có version")
    b.markdown("**Prior completed review**")
    b.write(prior or "Không có prior assessment")

    if review["status"] != "completed":
        if prior and st.button("↪ Confirm unchanged từ review trước", key=f"carry_fast_{review['id']}_{qid}"):
            repo.confirm_unchanged(review["id"], qid, actor=actor)
            _fragment_rerun()

        statuses = ["not_reviewed", "answered", "research_gap", "needs_review", "na"]
        seed_status = current["status"] if current else (prior["status"] if prior else "not_reviewed")
        status = st.selectbox(
            "Status",
            statuses,
            index=_page._idx(statuses, seed_status),
            format_func=lambda x: STATUS_LABELS[x],
            key=f"status_fast_{review['id']}_{qid}",
        )
        with st.form(f"assess_fast_{review['id']}_{qid}"):
            answer = st.text_area(
                "Câu trả lời của analyst",
                value=(current["analyst_answer"] if current else (prior["analyst_answer"] if prior else "")) or "",
                height=180,
            )
            if status in {"answered", "needs_review"}:
                opts = [-2, -1, 0, 1, 2]
                base = current["assessment"] if current and current["assessment"] is not None else (
                    prior["assessment"] if prior and prior["assessment"] is not None else 0
                )
                assessment = st.radio(
                    "Assessment", opts, index=_page._idx(opts, base, 2), horizontal=True,
                    format_func=lambda x: ASSESSMENT_LABELS[x],
                )
            else:
                assessment = None
                st.caption("Status này không được quy đổi thành điểm Assessment.")

            if status in {"answered", "needs_review", "research_gap"}:
                cc = st.columns(2)
                conf = current["confidence"] if current and current["confidence"] else (
                    prior["confidence"] if prior and prior["confidence"] else 3
                )
                mat = current["materiality"] if current and current["materiality"] else (
                    prior["materiality"] if prior and prior["materiality"] else 3
                )
                confidence = cc[0].slider("Confidence", 1, 5, int(conf))
                materiality = cc[1].slider("Materiality", 1, 5, int(mat))
            else:
                confidence = materiality = None

            reason = st.text_input("Reason for Change *", help="Bắt buộc cho mọi phiên bản được lưu, kể cả khi kết luận không đổi.")
            if st.form_submit_button("Lưu phiên bản mới", type="primary", use_container_width=True):
                if not reason.strip():
                    st.error("Bắt buộc nhập Reason for Change trước khi lưu phiên bản review.")
                else:
                    try:
                        repo.save_assessment(
                            review_id=review["id"], question_id=qid, analyst_answer=answer, status=status,
                            assessment=assessment, confidence=confidence, materiality=materiality,
                            change_reason=reason, actor=actor,
                        )
                        _fragment_rerun()
                    except _page.ValidationError as exc:
                        st.error(str(exc))
    else:
        st.info("Review đã completed. Hãy tạo review mới để cập nhật.")

    if history:
        st.dataframe(pd.DataFrame(history[:80]), use_container_width=True, hide_index=True)


def render_analytical_fast(repo, integration, company_ref_id: int, review, actor: str, data_provider, company_type: str) -> None:
    """Patch formula table renderer while retaining the tested lazy 11-tool analytical hub."""
    original = _pe.render_wrapped_table
    _pe.render_wrapped_table = render_fit_table
    try:
        render_analytical_hub_v2(repo, integration, company_ref_id, review, actor, data_provider, company_type)
    finally:
        _pe.render_wrapped_table = original


def render_watchlist_fast(repo, company_ref_id: int, ticker: str, *, actor: str, data_provider) -> None:
    render_watchlist_v2(repo, company_ref_id, ticker, actor=actor, data_provider=data_provider)
