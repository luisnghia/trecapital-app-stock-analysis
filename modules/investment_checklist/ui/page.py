from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

from ..contracts import HostContext, TrecapitalDataProvider, TrecapitalThemeAdapter
from ..repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from ..services.integration_service import ChecklistIntegrationService, build_repository
from .present import ASSESSMENT_LABELS, SCREENING_SYMBOL, STATUS_LABELS, THESIS_SYMBOL, fmt_pct, fmt_price, fmt_vnd_bn

FALLBACK_CSS = """
<style>
.checklist-module .locked{display:inline-block;padding:.2rem .55rem;border-radius:999px;background:#EEF2F6;color:#344054;font-size:.82rem}
.checklist-module .guide{padding:.75rem .9rem;border-left:4px solid #B68A3A;background:#FFFDF8;border-radius:6px;margin:.4rem 0 .8rem}
.checklist-module .principle{padding:.75rem .9rem;border:1px solid #D7CFBE;background:#F8F5ED;border-radius:8px;margin:.5rem 0}
.checklist-value-card{padding:.72rem .82rem;border:1px solid rgba(11,127,117,.18);border-radius:12px;background:#fff;min-height:82px;margin-bottom:.45rem}
.checklist-value-card .k{font-size:.78rem;color:#64748B;font-weight:750}.checklist-value-card .v{font-size:1.05rem;font-weight:900;margin-top:.2rem}.checklist-value-card .u{font-size:.72rem;color:#94A3B8}
</style>
"""
SECTIONS = ["🏠 Research Home", "📋 Table 1.1", "📊 Table 1.2", "🧠 Analyst Workspace Q01–Q59", "🕘 Snapshot & History"]


def _idx(options, value, default=0):
    try:
        return options.index(value)
    except ValueError:
        return default


def _map(rows, key):
    return {r[key]: r for r in rows}


def _float(v):
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _review_label(r):
    return f"{r['as_of_date']} | {r['review_type']} | {r['status']} | #{r['id']}"


def _heat(value):
    if not isinstance(value, (int, float)) or pd.isna(value) or value == 0:
        return ""
    alpha = 0.10 + 0.22 * min(abs(float(value)) / 100.0, 1.0)
    if value < 0:
        return f"color:#B91C1C;background-color:rgba(220,38,38,{alpha:.2f});font-weight:700"
    return f"color:#047857;background-color:rgba(16,185,129,{alpha:.2f});font-weight:700"


def _group_progress(repo, rid, qs):
    am = _map(repo.latest_assessments_for_review(rid), "question_id")
    rows = []
    for group in dict.fromkeys(q["group_name"] for q in qs):
        group_q = [q for q in qs if q["group_name"] == group]
        xs = [am.get(q["question_id"]) for q in group_q]
        na = sum(bool(x) and x["status"] == "na" for x in xs)
        ans = sum(bool(x) and x["status"] == "answered" for x in xs)
        gaps = sum(bool(x) and x["status"] == "research_gap" for x in xs)
        needs = sum(bool(x) and x["status"] == "needs_review" for x in xs)
        den = len(group_q) - na
        rows.append({"Nhóm": group, "Đã trả lời": ans, "N/A": na, "Research Gap": gaps, "Cần xem lại": needs, "Tổng áp dụng": den, "Hoàn thành": ans / den if den else 1.0})
    return pd.DataFrame(rows)


def _inventory_table(repo):
    rows = repo.latest_inventory_all()
    if not rows:
        st.info("Chưa có dữ liệu Table 1.2.")
        return
    out = []
    for x in rows:
        out.append({
            "Mã": x["ticker"], "Doanh nghiệp": x["company_name"], "As of": x["as_of_date"],
            "TEV/EBIT": x.get("tev_ebit"), "TEV/EBITDA": x.get("tev_ebitda"), "TEV/Norm.E": x.get("tev_normalized_earnings"),
            "Pre-tax yield": None if x.get("pretax_earnings_yield") is None else x["pretax_earnings_yield"] * 100,
            "Debt/EBITDA": x.get("debt_ebitda"), "EBIT/Interest": x.get("ebit_interest"),
            "FCF Yield EV": None if x.get("fcf_yield_ev") is None else x["fcf_yield_ev"] * 100,
            "FCF Yield Mkt": None if x.get("fcf_yield_market") is None else x["fcf_yield_market"] * 100,
            "Giá": x.get("market_price"), "Target": x.get("target_price"),
            "MOS": None if x.get("mos") is None else x["mos"] * 100, "Δ Thesis": THESIS_SYMBOL.get(x.get("thesis_direction"), "?")
        })
    df = pd.DataFrame(out)
    fm = {c: (lambda v: "—" if pd.isna(v) else f"{v:,.1f}x") for c in ["TEV/EBIT", "TEV/EBITDA", "TEV/Norm.E", "Debt/EBITDA", "EBIT/Interest"]}
    fm.update({c: (lambda v: "—" if pd.isna(v) else f"{v:,.1f}%") for c in ["Pre-tax yield", "FCF Yield EV", "FCF Yield Mkt", "MOS"]})
    fm.update({c: (lambda v: "—" if pd.isna(v) else f"{v:,.0f}") for c in ["Giá", "Target"]})
    nums = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    st.dataframe(df.style.format(fm, na_rep="—").map(_heat, subset=nums), use_container_width=True, hide_index=True)


def _source_cards(pre):
    items = [
        ("TEV", pre.tev, "tỷ đồng", fmt_vnd_bn), ("EBIT", pre.ebit, "tỷ đồng", fmt_vnd_bn), ("EBITDA", pre.ebitda, "tỷ đồng", fmt_vnd_bn),
        ("Normalized earnings", pre.normalized_earnings, "tỷ đồng", fmt_vnd_bn), ("Total debt", pre.total_debt, "tỷ đồng", fmt_vnd_bn),
        ("Interest expense", pre.interest_expense, "tỷ đồng", fmt_vnd_bn), ("Current FCF", pre.fcf_current, "tỷ đồng", fmt_vnd_bn),
        ("Market cap", pre.market_cap, "tỷ đồng", fmt_vnd_bn), ("Dividend/share", pre.dividend_per_share, "VND/cp", fmt_price),
        ("Market price", pre.market_price, "VND/cp", fmt_price), ("FCF Estimate", pre.fcf_estimate, "tỷ đồng", fmt_vnd_bn),
        ("Target price", pre.target_price, "VND/cp", fmt_price), ("MOS", pre.mos, "%", fmt_pct),
    ]
    for start in range(0, len(items), 4):
        cols = st.columns(4)
        for col, (name, val, unit, formatter) in zip(cols, items[start:start + 4]):
            color = "#B91C1C" if val is not None and val < 0 else ("#047857" if val is not None and val > 0 else "#475569")
            col.markdown(f"<div class='checklist-value-card'><div class='k'>{name}</div><div class='v' style='color:{color}'>{formatter(val)}</div><div class='u'>{unit}</div></div>", unsafe_allow_html=True)
    missing = [name for name, val, _, _ in items if val is None]
    if missing:
        st.caption("Chưa có dữ liệu nguồn cho: " + ", ".join(missing) + ". App không tự bịa số liệu.")


def _money_input(col, label, value, key):
    return col.number_input(label, value=_float(value), step=1.0, format="%.0f", key=key, placeholder="Chưa có dữ liệu")


def _company_cached(integration, host):
    c = host.company
    sig = (c.company_key, c.ticker, c.company_name, c.exchange, c.industry_name, c.company_type, c.currency, tuple(sorted((str(k), str(v)) for k, v in dict(c.metadata).items())))
    key = f"_checklist_company_context_{c.company_key}"
    cached = st.session_state.get(key)
    if cached and cached.get("sig") == sig:
        return cached["cid"], cached["company"]
    cid = integration.sync_company_context()
    company = integration.repo.get_company_ref(cid)
    st.session_state[key] = {"sig": sig, "cid": cid, "company": company}
    return cid, company


def _render_home(repo, review):
    if not review:
        st.info("Tạo review để bắt đầu nghiên cứu.")
        return
    m = repo.review_metrics(review["id"])
    cols = st.columns(6)
    vals = [("Table 1.1", f"{repo.quality_tally(review['id'])}/10"), ("Checklist answered", f"{m['answered']}/59"), ("Research completion", f"{m['research_completion'] * 100:.1f}%"), ("Research gaps", m["research_gaps"]), ("Critical unknowns", m["critical_unknowns"]), ("Red flags (-2)", m["red_flags"])]
    for c, (k, v) in zip(cols, vals):
        c.metric(k, v)
    st.caption("Research Completion = Answered / (59 − N/A). Research Gap không được tính là Answered và không bị quy đổi thành Assessment 0.")
    qs = repo.list_questions()
    g = _group_progress(repo, review["id"], qs)
    g["Hoàn thành"] = g["Hoàn thành"].map(lambda x: f"{x * 100:.1f}%")
    st.dataframe(g, use_container_width=True, hide_index=True)


def _render_table11(repo, review, actor):
    st.markdown("#### Table 1.1 — Quality Criteria Matrix")
    st.caption("✓ = Có · X = Không có · — = Chưa biết · N/A = Không áp dụng. Total chỉ đếm ✓, không tạo BUY/SELL.")
    matrix = repo.screening_matrix_latest()
    if matrix:
        df = pd.DataFrame(matrix)
        for col in df.columns:
            if col not in {"Ticker", "Company", "As of", "Total ✓"}:
                df[col] = df[col].map(SCREENING_SYMBOL)
        st.dataframe(df, use_container_width=True, hide_index=True)
    if not review:
        return
    if review["status"] == "completed":
        st.info("Review đã khóa. Tạo review mới để cập nhật Table 1.1.")
        return
    criteria = repo.list_screening_criteria()
    cur = _map(repo.latest_screening_for_review(review["id"]), "criterion_code")
    prior_rows = repo.latest_screening_for_review(review["prior_review_id"]) if review.get("prior_review_id") else []
    priors = _map(prior_rows, "criterion_code")
    if priors and st.button("↪ Confirm toàn bộ Table 1.1 unchanged từ review trước", key=f"carry_sc_{review['id']}"):
        for c in criteria:
            if priors.get(c["criterion_code"]):
                repo.confirm_screening_unchanged(review["id"], c["criterion_code"], actor=actor)
        st.rerun()
    with st.form(f"screen_form_{review['id']}"):
        values = []
        options = ["yes", "no", "unknown", "na"]
        for c in criteria:
            old = cur.get(c["criterion_code"])
            prior = priors.get(c["criterion_code"])
            st.markdown(f"**{c['display_order']}. {c['criterion_name_vi']}** · `{c['criterion_name_en']}`")
            a, b, d = st.columns([1.4, 1.2, 4])
            val = a.selectbox("Kết luận", options, index=_idx(options, old["analyst_value"] if old else "unknown", 2), format_func=lambda x: {"yes": "✓ Có", "no": "X Không", "unknown": "— Chưa biết", "na": "N/A"}[x], key=f"sc_v_{review['id']}_{c['criterion_code']}")
            conf = b.selectbox("Confidence", [1, 2, 3, 4, 5], index=_idx([1, 2, 3, 4, 5], old["confidence"] if old and old["confidence"] else 3, 2), key=f"sc_c_{review['id']}_{c['criterion_code']}")
            note = d.text_input("Ghi chú / bằng chứng analyst", value=old["note"] if old else "", key=f"sc_n_{review['id']}_{c['criterion_code']}")
            if prior:
                d.caption(f"Prior: {SCREENING_SYMBOL.get(prior['analyst_value'], '—')} · conf {prior['confidence'] or '—'}")
            values.append((c["criterion_code"], val, conf, note))
        if st.form_submit_button("Lưu Table 1.1 — tạo version mới", type="primary", use_container_width=True):
            for code, val, conf, note in values:
                repo.save_screening(review_id=review["id"], criterion_code=code, analyst_value=val, confidence=conf, note=note, actor=actor)
            st.rerun()


def _render_table12(repo, integration, cid, review, actor):
    st.markdown("#### Table 1.2 — Opportunity Inventory")
    st.caption("Quy chuẩn hiển thị: tỷ đồng 0 số thập phân; % và hệ số 1 số thập phân; số âm đỏ, số dương xanh ngọc lục bảo.")
    _inventory_table(repo)
    pre = integration.get_inventory_prefill()
    if pre:
        with st.expander("🔗 Dữ liệu hiện có từ Trecapital Data Layer", expanded=True):
            _source_cards(pre)
            st.caption(f"Nguồn bridge: {pre.source_module} · kỳ dữ liệu: {pre.as_of_date}")
            if st.button("Lưu snapshot từ Data Layer", key=f"host_inv_{cid}"):
                integration.save_host_inventory_snapshot(company_ref_id=cid, review_id=review["id"] if review else None, data=pre)
                st.rerun()
    inv = repo.inventory_history(cid)
    latest = inv[0] if inv else {}
    p = pre.__dict__ if pre else {}
    def base(k):
        return latest.get(k) if latest.get(k) is not None else p.get(k)
    with st.expander("✏️ Manual override / Lưu Inventory Snapshot", expanded=False):
        with st.form(f"inv_form_{cid}"):
            default_date = date.fromisoformat(pre.as_of_date[:10]) if pre and len(pre.as_of_date) >= 10 and pre.as_of_date[:10].count("-") == 2 else (date.fromisoformat(review["as_of_date"]) if review else date.today())
            asof = st.date_input("As-of date", value=default_date)
            c = st.columns(4)
            tev = _money_input(c[0], "TEV (tỷ)", base("tev"), f"inv_tev_{cid}")
            ebit = _money_input(c[1], "EBIT (tỷ)", base("ebit"), f"inv_ebit_{cid}")
            ebitda = _money_input(c[2], "EBITDA (tỷ)", base("ebitda"), f"inv_ebitda_{cid}")
            norm = _money_input(c[3], "Normalized earnings (tỷ)", base("normalized_earnings"), f"inv_norm_{cid}")
            c = st.columns(4)
            debt = _money_input(c[0], "Total debt (tỷ)", base("total_debt"), f"inv_debt_{cid}")
            interest = _money_input(c[1], "Interest expense (tỷ)", base("interest_expense"), f"inv_interest_{cid}")
            fcf = _money_input(c[2], "Current FCF (tỷ)", base("fcf_current"), f"inv_fcf_{cid}")
            mcap = _money_input(c[3], "Market cap (tỷ)", base("market_cap"), f"inv_mcap_{cid}")
            c = st.columns(4)
            dps = _money_input(c[0], "Dividend/share (VND)", base("dividend_per_share"), f"inv_dps_{cid}")
            price = _money_input(c[1], "Market price (VND)", base("market_price"), f"inv_price_{cid}")
            fcf_est = _money_input(c[2], "FCF Estimate (tỷ)", base("fcf_estimate"), f"inv_fcf_est_{cid}")
            target = _money_input(c[3], "Target price (VND)", base("target_price"), f"inv_target_{cid}")
            c = st.columns([1, 1, 3])
            md = latest.get("mos") if latest.get("mos") is not None else p.get("mos")
            mos = c[0].number_input("MOS (%)", value=None if md is None else float(md) * 100, step=.1, format="%.1f", key=f"inv_mos_{cid}", placeholder="Chưa có dữ liệu")
            thesis = c[1].selectbox("Δ Thesis", ["unknown", "up", "flat", "down"], index=_idx(["unknown", "up", "flat", "down"], latest.get("thesis_direction") or "unknown"), format_func=lambda x: {"unknown": "?", "up": "↑ Cải thiện", "flat": "→ Không đổi", "down": "↓ Suy giảm"}[x])
            note = c[2].text_input("Ghi chú", value=latest.get("note") or "")
            if st.form_submit_button("Lưu Inventory Snapshot", type="primary", use_container_width=True):
                repo.save_inventory_snapshot(company_ref_id=cid, as_of_date=asof, review_id=review["id"] if review else None, tev=tev, ebit=ebit, ebitda=ebitda, normalized_earnings=norm, total_debt=debt, interest_expense=interest, fcf_current=fcf, market_cap=mcap, dividend_per_share=dps, market_price=price, fcf_estimate=fcf_est, target_price=target, mos=mos / 100 if mos is not None else None, thesis_direction=thesis, note=note, actor=actor, data_origin="mixed" if pre else "manual", source_as_of_date=pre.as_of_date if pre else None)
                st.rerun()
    if inv:
        with st.expander("Lịch sử Table 1.2"):
            h = pd.DataFrame(inv)
            money = [c for c in ["tev", "ebit", "ebitda", "normalized_earnings", "total_debt", "interest_expense", "fcf_current", "market_cap", "dividend_per_share", "market_price", "fcf_estimate", "target_price"] if c in h]
            ratio = [c for c in ["tev_ebit", "tev_ebitda", "tev_normalized_earnings", "debt_ebitda", "ebit_interest"] if c in h]
            pct = [c for c in ["pretax_earnings_yield", "fcf_yield_ev", "fcf_yield_market", "dividend_yield", "price_vs_target", "research_completion", "mos"] if c in h]
            fm = {c: (lambda v: "—" if pd.isna(v) else f"{v:,.0f}") for c in money}
            fm.update({c: (lambda v: "—" if pd.isna(v) else f"{v:,.1f}x") for c in ratio})
            fm.update({c: (lambda v: "—" if pd.isna(v) else f"{v * 100:,.1f}%") for c in pct})
            nums = [c for c in h.columns if pd.api.types.is_numeric_dtype(h[c])]
            st.dataframe(h.style.format(fm, na_rep="—").map(_heat, subset=nums), use_container_width=True, hide_index=True)


def _render_workspace(repo, cid, review, actor):
    st.markdown("#### Analyst Workspace — Q01–Q59")
    if not review:
        st.info("Tạo review để làm checklist.")
        return
    qs = repo.list_questions()
    groups = list(dict.fromkeys(q["group_name"] for q in qs))
    c1, c2 = st.columns([1.2, 2.8])
    group = c1.selectbox("Nhóm", groups, key=f"q_group_{review['id']}")
    qg = [q for q in qs if q["group_name"] == group]
    qids = [q["question_id"] for q in qg]
    qid = c2.selectbox("Câu hỏi", qids, format_func=lambda x: f"{x} — {next(q for q in qg if q['question_id'] == x)['question_vi']}", key=f"q_sel_{review['id']}_{group}")
    q = next(q for q in qs if q["question_id"] == qid)
    current = repo.latest_assessment(review["id"], qid)
    prior = repo.latest_assessment(review["prior_review_id"], qid) if review.get("prior_review_id") else None
    st.markdown(f"### {qid}. {q['question_vi']}")
    st.markdown(f"<div class='guide'><b>Hướng dẫn tự phân tích:</b> {q['guidance']}</div>", unsafe_allow_html=True)
    st.caption(f"Supporting tool (Phase sau): {q['supporting_tool'] or 'Không có'}")
    a, b = st.columns(2)
    a.markdown("**Current review**")
    a.write(current or "Chưa có version")
    b.markdown("**Prior completed review**")
    b.write(prior or "Không có prior assessment")
    if review["status"] != "completed":
        if prior and st.button("↪ Confirm unchanged từ review trước", key=f"carry_{review['id']}_{qid}"):
            repo.confirm_unchanged(review["id"], qid, actor=actor)
            st.rerun()
        statuses = ["not_reviewed", "answered", "research_gap", "needs_review", "na"]
        status = st.selectbox("Status", statuses, index=_idx(statuses, current["status"] if current else (prior["status"] if prior else "not_reviewed")), format_func=lambda x: STATUS_LABELS[x], key=f"status_{review['id']}_{qid}")
        with st.form(f"assess_{review['id']}_{qid}"):
            answer = st.text_area("Câu trả lời của analyst", value=(current["analyst_answer"] if current else (prior["analyst_answer"] if prior else "")) or "", height=180)
            if status in {"answered", "needs_review"}:
                opts = [-2, -1, 0, 1, 2]
                base = current["assessment"] if current and current["assessment"] is not None else (prior["assessment"] if prior and prior["assessment"] is not None else 0)
                assessment = st.radio("Assessment", opts, index=_idx(opts, base, 2), horizontal=True, format_func=lambda x: ASSESSMENT_LABELS[x])
            else:
                assessment = None
                st.caption("Status này không được quy đổi thành điểm Assessment.")
            if status in {"answered", "needs_review", "research_gap"}:
                cc = st.columns(2)
                conf = current["confidence"] if current and current["confidence"] else (prior["confidence"] if prior and prior["confidence"] else 3)
                mat = current["materiality"] if current and current["materiality"] else (prior["materiality"] if prior and prior["materiality"] else 3)
                confidence = cc[0].slider("Confidence", 1, 5, int(conf))
                materiality = cc[1].slider("Materiality", 1, 5, int(mat))
            else:
                confidence = materiality = None
            reason = st.text_input("Reason for Change", help="Bắt buộc nếu Assessment thay đổi so với version hiện tại.")
            if st.form_submit_button("Lưu phiên bản mới", type="primary", use_container_width=True):
                try:
                    repo.save_assessment(review_id=review["id"], question_id=qid, analyst_answer=answer, status=status, assessment=assessment, confidence=confidence, materiality=materiality, change_reason=reason, actor=actor)
                    st.rerun()
                except ValidationError as exc:
                    st.error(str(exc))
    else:
        st.info("Review đã completed. Hãy tạo review mới để cập nhật.")
    hist = repo.assessment_history(cid, qid)
    if hist:
        st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)


def _render_history(repo, cid, review, actor):
    st.markdown("#### Snapshot & History")
    if not review:
        st.info("Chưa có review.")
        return
    m = repo.review_metrics(review["id"])
    c = st.columns(3)
    c[0].metric("Answered", m["answered"])
    c[1].metric("Research gaps", m["research_gaps"])
    c[2].metric("Completion", f"{m['research_completion'] * 100:.1f}%")
    if review["status"] != "completed":
        ok = st.checkbox("Tôi hiểu review sẽ bị khóa sau khi finalize.", key=f"fin_{review['id']}")
        if st.button("🔒 Finalize & Create Immutable Snapshot", type="primary", disabled=not ok, key=f"final_{review['id']}"):
            repo.finalize_review(review["id"], actor=actor)
            st.rerun()
    snaps = repo.list_snapshots(cid)
    if snaps:
        st.dataframe(pd.DataFrame(snaps), use_container_width=True, hide_index=True)
        sid = st.selectbox("View as-of snapshot", [s["id"] for s in snaps], format_func=lambda x: f"Snapshot #{x} — {next(s for s in snaps if s['id'] == x)['as_of_date']}")
        with st.expander("Raw immutable payload (audit)"):
            st.json(repo.get_snapshot(sid)["payload"])
    else:
        st.info("Chưa có snapshot.")
    with st.expander("Audit log"):
        logs = repo.list_audit_logs(cid, 200)
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True) if logs else st.caption("Chưa có log.")
    with st.expander("Integration sync log"):
        logs = repo.list_sync_logs(cid, 100)
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True) if logs else st.caption("Chưa có sync log.")


def render_investment_checklist(host: HostContext, *, repo: Optional[SQLiteChecklistRepository] = None, data_provider: Optional[TrecapitalDataProvider] = None, theme: Optional[TrecapitalThemeAdapter] = None) -> None:
    if theme:
        theme.inject_module_css()
    else:
        st.markdown(FALLBACK_CSS, unsafe_allow_html=True)
    repo = repo or build_repository(host)
    integration = ChecklistIntegrationService(repo, host, data_provider)
    cid, company = _company_cached(integration, host)
    actor = host.analyst.user_id
    st.markdown('<div class="checklist-module">', unsafe_allow_html=True)
    st.subheader("Investment Research & Checklist System")
    st.caption("Phase 1C — Table 1.1 + Table 1.2 + Q01–Q59 + versioning + immutable snapshots. Không AI.")
    st.markdown(f"**{company['ticker']} — {company['company_name']}** · {company['industry_name'] or 'Chưa gán ngành'}")
    st.markdown('<div class="principle"><b>Nguyên tắc:</b> Analyst tự trả lời, tự đánh giá; Unknown khác Neutral; mọi thay đổi được lưu version; review đã finalize là read-only.</div>', unsafe_allow_html=True)
    reviews = repo.list_reviews(cid)
    review = None
    left, right = st.columns([2.4, 1])
    if reviews:
        ids = [r["id"] for r in reviews]
        state = f"checklist_review_{company['host_company_key']}"
        desired = st.session_state.get(state)
        index = ids.index(desired) if desired in ids else 0
        rid = left.selectbox("Review", ids, index=index, format_func=lambda x: _review_label(next(r for r in reviews if r["id"] == x)), key=f"review_select_{cid}")
        st.session_state[state] = rid
        review = next(r for r in reviews if r["id"] == rid)
    else:
        left.info("Chưa có review cho mã này.")
    with right.popover("➕ Tạo review mới", use_container_width=True):
        asof = st.date_input("As-of date", value=date.today(), key=f"new_review_date_{cid}")
        rtype = st.selectbox("Loại review", ["full", "screening", "delta"], key=f"new_review_type_{cid}")
        if st.button("Tạo review", use_container_width=True, key=f"create_review_{cid}"):
            rid = repo.create_review(cid, asof, rtype, actor)
            st.session_state[f"checklist_review_{company['host_company_key']}"] = rid
            st.rerun()
    if review:
        st.caption(f"Review #{review['id']} · {review['as_of_date']} · {review['review_type']} · {review['status']}")
        if review["status"] == "completed":
            st.markdown('<span class="locked">🔒 Completed — read only</span>', unsafe_allow_html=True)
    # st.tabs executes every tab body on every Streamlit rerun. Rendering only the selected
    # section keeps Q01-Q59 navigation fast and prevents unrelated history/Table 1.2 queries.
    section = st.radio("Khu vực checklist", SECTIONS, horizontal=True, label_visibility="collapsed", key=f"checklist_section_{cid}")
    if section == SECTIONS[0]:
        _render_home(repo, review)
    elif section == SECTIONS[1]:
        _render_table11(repo, review, actor)
    elif section == SECTIONS[2]:
        _render_table12(repo, integration, cid, review, actor)
    elif section == SECTIONS[3]:
        _render_workspace(repo, cid, review, actor)
    else:
        _render_history(repo, cid, review, actor)
    st.markdown("</div>", unsafe_allow_html=True)
