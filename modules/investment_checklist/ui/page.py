from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

from ..contracts import HostContext, TrecapitalDataProvider, TrecapitalThemeAdapter
from ..repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from ..services.formulas import inventory_metrics
from ..services.integration_service import ChecklistIntegrationService, build_repository
from .present import ASSESSMENT_LABELS, SCREENING_SYMBOL, STATUS_LABELS, THESIS_SYMBOL, fmt_pct, fmt_price, fmt_vnd_bn

FALLBACK_CSS = """
<style>
.checklist-module .locked{display:inline-block;padding:.2rem .55rem;border-radius:999px;background:#EEF2F6;color:#344054;font-size:.82rem}
.checklist-module .guide{padding:.75rem .9rem;border-left:4px solid #B68A3A;background:#FFFDF8;border-radius:6px;margin:.4rem 0 .8rem}
.checklist-module .principle{padding:.75rem .9rem;border:1px solid #D7CFBE;background:#F8F5ED;border-radius:8px;margin:.5rem 0}
.checklist-value-card{padding:.72rem .82rem;border:1px solid rgba(11,127,117,.18);border-radius:12px;background:#fff;min-height:82px;margin-bottom:.45rem}
.checklist-value-card .k{font-size:.78rem;color:#64748B;font-weight:750}.checklist-value-card .v{font-size:1.05rem;font-weight:900;margin-top:.2rem}.checklist-value-card .u{font-size:.72rem;color:#94A3B8}
.checklist-auto-note{padding:.65rem .8rem;border-radius:10px;background:#F0FDF4;border:1px solid #BBF7D0;color:#166534;font-size:.84rem;margin:.35rem 0 .7rem}
</style>
"""
SECTIONS = ["🏠 Research Home", "📋 Table 1.1", "📊 Table 1.2", "🧠 Analyst Workspace Q01–Q59", "🕘 Snapshot & History"]


def _idx(options, value, default=0):
    try: return options.index(value)
    except ValueError: return default


def _map(rows, key): return {r[key]: r for r in rows}


def _float(v):
    try:
        if v is None or pd.isna(v): return None
        return float(v)
    except Exception: return None


def _review_label(r): return f"{r['as_of_date']} | {r['review_type']} | {r['status']} | #{r['id']}"


def _heat(value):
    if not isinstance(value, (int, float)) or pd.isna(value) or value == 0: return ""
    alpha = 0.10 + 0.22 * min(abs(float(value)) / 100.0, 1.0)
    if value < 0: return f"color:#B91C1C;background-color:rgba(220,38,38,{alpha:.2f});font-weight:700"
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


def _style_inventory(df: pd.DataFrame):
    if df.empty: return df.style
    ratio_cols = ["TEV/EBIT", "TEV/EBITDA", "TEV/Norm.E", "Debt/EBITDA", "EBIT/Interest"]
    pct_cols = ["Pre-tax yield", "FCF Yield EV", "FCF Yield Mkt", "MOS"]
    money_cols = ["TEV", "EBIT", "EBITDA", "Normalized earnings", "Total Debt", "FCF", "Market cap", "Giá", "Target", "FCF est./share"]
    fm = {c: (lambda v: "—" if pd.isna(v) else f"{v:,.1f}x") for c in ratio_cols if c in df}
    fm.update({c: (lambda v: "—" if pd.isna(v) else f"{v:,.1f}%") for c in pct_cols if c in df})
    fm.update({c: (lambda v: "—" if pd.isna(v) else f"{v:,.0f}") for c in money_cols if c in df})
    if "CCC" in df: fm["CCC"] = lambda v: "—" if pd.isna(v) else f"{v:,.0f} ngày"
    nums = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return df.style.format(fm, na_rep="—").map(_heat, subset=nums)


def _inventory_display_row(x, *, period_key="as_of_date", source="Review"):
    return {
        "Kỳ": x.get(period_key), "Nguồn": source,
        "TEV": x.get("tev"), "EBIT": x.get("ebit"), "EBITDA": x.get("ebitda"), "Normalized earnings": x.get("normalized_earnings"),
        "TEV/EBIT": x.get("tev_ebit"), "TEV/EBITDA": x.get("tev_ebitda"), "TEV/Norm.E": x.get("tev_normalized_earnings"),
        "Pre-tax yield": None if x.get("pretax_earnings_yield") is None else x.get("pretax_earnings_yield") * 100,
        "Total Debt": x.get("total_debt"), "Debt/EBITDA": x.get("debt_ebitda"), "EBIT/Interest": x.get("ebit_interest"),
        "FCF": x.get("fcf_current"), "FCF Yield EV": None if x.get("fcf_yield_ev") is None else x.get("fcf_yield_ev") * 100,
        "FCF Yield Mkt": None if x.get("fcf_yield_market") is None else x.get("fcf_yield_market") * 100,
        "CCC": x.get("ccc_days"), "Market cap": x.get("market_cap"), "Giá": x.get("market_price"), "FCF est./share": x.get("fcf_estimate"),
        "Target": x.get("target_price"), "MOS": None if x.get("mos") is None else x.get("mos") * 100,
    }


def _saved_inventory_table(repo):
    rows = repo.latest_inventory_all()
    if not rows:
        st.info("Chưa có snapshot Table 1.2 đã lưu."); return
    out = []
    for x in rows:
        row = _inventory_display_row(x, source=f"{x.get('data_origin','snapshot')}")
        row = {"Mã": x["ticker"], "Doanh nghiệp": x["company_name"], **row, "Δ Thesis": THESIS_SYMBOL.get(x.get("thesis_direction"), "?")}
        out.append(row)
    st.dataframe(_style_inventory(pd.DataFrame(out)), use_container_width=True, hide_index=True)


def _current_auto_metrics(pre):
    if pre is None: return
    m = inventory_metrics(tev=pre.tev, ebit=pre.ebit, ebitda=pre.ebitda, normalized_earnings=pre.normalized_earnings,
        total_debt=pre.total_debt, interest_expense=pre.interest_expense, fcf_current=pre.fcf_current,
        market_cap=pre.market_cap, dividend_per_share=pre.dividend_per_share, market_price=pre.market_price, target_price=pre.target_price)
    x = {**pre.__dict__, **m}
    st.dataframe(_style_inventory(pd.DataFrame([_inventory_display_row(x, period_key="as_of_date", source="Trecapital TTM")])), use_container_width=True, hide_index=True)


def _source_cards(pre):
    items = [
        ("TEV", pre.tev, "tỷ đồng", fmt_vnd_bn), ("EBIT", pre.ebit, "tỷ đồng", fmt_vnd_bn), ("EBITDA", pre.ebitda, "tỷ đồng", fmt_vnd_bn),
        ("Normalized earnings", pre.normalized_earnings, "tỷ đồng", fmt_vnd_bn), ("Total debt", pre.total_debt, "tỷ đồng", fmt_vnd_bn),
        ("Interest expense", pre.interest_expense, "tỷ đồng", fmt_vnd_bn), ("Current FCF", pre.fcf_current, "tỷ đồng", fmt_vnd_bn),
        ("CCC", pre.ccc_days, "ngày", lambda v: "—" if v is None else f"{v:,.0f}"),
        ("Market cap", pre.market_cap, "tỷ đồng", fmt_vnd_bn), ("Shares outstanding", pre.shares_outstanding_mil, "triệu cp", fmt_vnd_bn),
        ("Dividend/share", pre.dividend_per_share, "VND/cp", fmt_price), ("Market price", pre.market_price, "VND/cp", fmt_price),
        ("FCF estimate/share", pre.fcf_estimate, "VND/cp", fmt_price), ("Target price", pre.target_price, "VND/cp", fmt_price), ("MOS", pre.mos, "%", fmt_pct),
    ]
    for start in range(0, len(items), 4):
        cols = st.columns(4)
        for col, (name, val, unit, formatter) in zip(cols, items[start:start + 4]):
            color = "#B91C1C" if val is not None and val < 0 else ("#047857" if val is not None and val > 0 else "#475569")
            col.markdown(f"<div class='checklist-value-card'><div class='k'>{name}</div><div class='v' style='color:{color}'>{formatter(val)}</div><div class='u'>{unit}</div></div>", unsafe_allow_html=True)
    missing = [name for name, val, _, _ in items if val is None]
    if missing: st.caption("Chưa có dữ liệu nguồn cho: " + ", ".join(missing) + ". App không tự bịa số liệu.")
    for note in getattr(pre, "source_notes", ()) or ():
        st.warning(note) if str(note).startswith("CẢNH BÁO") else st.caption("• " + str(note))


def _auto_text(value, formatter=fmt_vnd_bn): return "—" if value is None else formatter(value)


def _override_input(col, label, auto_value, key, *, formatter=fmt_vnd_bn):
    return col.number_input(label, value=None, step=1.0, format="%.0f", key=key,
        placeholder=f"Tự động: {_auto_text(auto_value, formatter)}",
        help=f"Để trống = dùng số tự động của Trecapital ({_auto_text(auto_value, formatter)}). Chỉ nhập khi analyst muốn điều chỉnh.")


def _effective(auto_value, manual_value): return manual_value if manual_value is not None else auto_value


def _company_cached(integration, host):
    c = host.company
    sig = (c.company_key, c.ticker, c.company_name, c.exchange, c.industry_name, c.company_type, c.currency, tuple(sorted((str(k), str(v)) for k, v in dict(c.metadata).items())))
    key = f"_checklist_company_context_{c.company_key}"; cached = st.session_state.get(key)
    if cached and cached.get("sig") == sig: return cached["cid"], cached["company"]
    cid = integration.sync_company_context(); company = integration.repo.get_company_ref(cid)
    st.session_state[key] = {"sig": sig, "cid": cid, "company": company}; return cid, company


def _render_home(repo, cid, review):
    if not review: st.info("Tạo review để bắt đầu nghiên cứu."); return
    m = repo.review_metrics(review["id"]); cols = st.columns(6)
    vals = [("Table 1.1", f"{repo.quality_tally(review['id'])}/10"), ("Checklist answered", f"{m['answered']}/59"), ("Research completion", f"{m['research_completion'] * 100:.1f}%"), ("Research gaps", m["research_gaps"]), ("Critical unknowns", m["critical_unknowns"]), ("Red flags (-2)", m["red_flags"])]
    for c, (k, v) in zip(cols, vals): c.metric(k, v)
    st.caption("Research Completion = Answered / (59 − N/A). Research Gap không được tính là Answered và không bị quy đổi thành Assessment 0.")
    qs = repo.list_questions(); g = _group_progress(repo, review["id"], qs); g["Hoàn thành"] = g["Hoàn thành"].map(lambda x: f"{x * 100:.1f}%")
    st.dataframe(g, use_container_width=True, hide_index=True)
    with st.expander("Lịch sử review — theo dõi thay đổi doanh nghiệp", expanded=False):
        reviews = repo.list_reviews(cid)
        st.dataframe(pd.DataFrame(reviews), use_container_width=True, hide_index=True) if reviews else st.caption("Chưa có lịch sử review.")


def _render_table11(repo, cid, review, actor):
    st.markdown("#### Table 1.1 — Quality Criteria Matrix")
    st.caption("✓ = Có · X = Không có · — = Chưa biết · N/A = Không áp dụng. Total chỉ đếm ✓, không tạo BUY/SELL.")
    matrix = repo.screening_matrix_latest()
    if matrix:
        df = pd.DataFrame(matrix)
        for col in df.columns:
            if col not in {"Ticker", "Company", "As of", "Total ✓"}: df[col] = df[col].map(SCREENING_SYMBOL)
        st.dataframe(df, use_container_width=True, hide_index=True)
    history = repo.screening_history_matrix(cid)
    if history:
        with st.expander("Lịch sử Table 1.1 theo từng review", expanded=False):
            h = pd.DataFrame(history)
            for col in h.columns:
                if col not in {"Review #", "As of", "Type", "Status", "Total ✓"}: h[col] = h[col].map(SCREENING_SYMBOL)
            st.dataframe(h, use_container_width=True, hide_index=True)
    if not review: return
    if review["status"] == "completed": st.info("Review đã khóa. Tạo review mới để cập nhật Table 1.1."); return
    criteria = repo.list_screening_criteria(); cur = _map(repo.latest_screening_for_review(review["id"]), "criterion_code")
    prior_rows = repo.latest_screening_for_review(review["prior_review_id"]) if review.get("prior_review_id") else []; priors = _map(prior_rows, "criterion_code")
    if priors and st.button("↪ Confirm toàn bộ Table 1.1 unchanged từ review trước", key=f"carry_sc_{review['id']}"):
        for c in criteria:
            if priors.get(c["criterion_code"]): repo.confirm_screening_unchanged(review["id"], c["criterion_code"], actor=actor)
        st.rerun()
    with st.form(f"screen_form_{review['id']}"):
        values=[]; options=["yes","no","unknown","na"]
        for c in criteria:
            old=cur.get(c["criterion_code"]); prior=priors.get(c["criterion_code"])
            st.markdown(f"**{c['display_order']}. {c['criterion_name_vi']}** · `{c['criterion_name_en']}`")
            a,b,d=st.columns([1.4,1.2,4])
            val=a.selectbox("Kết luận", options, index=_idx(options, old["analyst_value"] if old else "unknown",2), format_func=lambda x:{"yes":"✓ Có","no":"X Không","unknown":"— Chưa biết","na":"N/A"}[x], key=f"sc_v_{review['id']}_{c['criterion_code']}")
            conf=b.selectbox("Confidence", [1,2,3,4,5], index=_idx([1,2,3,4,5], old["confidence"] if old and old["confidence"] else 3,2), key=f"sc_c_{review['id']}_{c['criterion_code']}")
            note=d.text_input("Ghi chú / bằng chứng analyst", value=old["note"] if old else "", key=f"sc_n_{review['id']}_{c['criterion_code']}")
            if prior: d.caption(f"Prior: {SCREENING_SYMBOL.get(prior['analyst_value'],'—')} · conf {prior['confidence'] or '—'}")
            values.append((c["criterion_code"],val,conf,note))
        if st.form_submit_button("Lưu Table 1.1 — tạo version mới", type="primary", use_container_width=True):
            for code,val,conf,note in values: repo.save_screening(review_id=review["id"],criterion_code=code,analyst_value=val,confidence=conf,note=note,actor=actor)
            st.rerun()


def _render_table12_trend(repo, integration, cid):
    provider = integration.data_provider
    proxy = []
    getter = getattr(provider, "get_inventory_proxy_history", None)
    if callable(getter):
        try: proxy = getter(10) or []
        except Exception as exc: st.caption(f"Chưa dựng được proxy lịch sử 10 năm: {exc}")
    rows=[]
    for x in reversed(proxy): rows.append(_inventory_display_row(x, period_key="period", source=x.get("source_type","10Y proxy")))
    for x in repo.inventory_history(cid): rows.append(_inventory_display_row(x, source=f"Review/snapshot #{x.get('last_review_id') or '—'} · {x.get('data_origin','snapshot')}"))
    if rows:
        st.markdown("##### Proxy 10 năm gần nhất + TTM + lịch sử review")
        st.caption("Proxy lịch sử chỉ dùng dữ liệu Trecapital của đúng kỳ. Target/MOS lịch sử không được hồi tố; chỉ xuất hiện khi có snapshot/review thực tế. CCC dùng công thức Shearn DIO + DSO − DPO với số dư bình quân khi nguồn chưa có CCC trực tiếp.")
        st.dataframe(_style_inventory(pd.DataFrame(rows)), use_container_width=True, hide_index=True, height=min(560, 38 * len(rows) + 75))
    else: st.info("Chưa có đủ chuỗi 10 năm/review để dựng lịch sử Table 1.2.")


def _render_table12(repo, integration, cid, review, actor):
    st.markdown("#### Table 1.2 — Opportunity Inventory")
    st.caption("Quy chuẩn: tỷ đồng 0 số thập phân; % và hệ số 1 số thập phân; CCC theo ngày; số âm đỏ, số dương xanh ngọc lục bảo. FCF estimate theo VND/cp.")
    pre = integration.get_inventory_prefill()
    if pre:
        st.markdown("##### Chỉ tiêu hiệu lực hiện tại — tự động từ Trecapital"); _current_auto_metrics(pre)
        with st.expander("🔗 Dữ liệu gốc đã chuẩn hóa từ Trecapital Data Layer", expanded=True):
            _source_cards(pre); st.caption(f"Nguồn bridge: {pre.source_module} · kỳ dữ liệu: {pre.as_of_date}")
            debt_note = st.session_state.get("checklist_debt_source_note")
            if debt_note: st.caption("• " + str(debt_note))
            if st.button("Lưu snapshot tự động hiện tại", key=f"host_inv_{cid}"):
                integration.save_host_inventory_snapshot(company_ref_id=cid, review_id=review["id"] if review else None, data=pre); st.rerun()
    else: st.warning("Checklist chưa nhận được dữ liệu tự động từ Trecapital Data Layer cho mã hiện tại.")

    _render_table12_trend(repo, integration, cid)
    auto = pre.__dict__ if pre else {}
    with st.expander("✏️ Điều chỉnh của nhà phân tích — để trống = dùng số tự động", expanded=False):
        st.markdown("<div class='checklist-auto-note'><b>Nguyên tắc override:</b> mọi ô mặc định để trống. Analyst chỉ nhập chỉ tiêu cần điều chỉnh; ô không nhập tự động dùng Trecapital. Snapshot lưu cả bộ giá trị hiệu lực để audit/history.</div>", unsafe_allow_html=True)
        with st.form(f"inv_form_{cid}"):
            default_date=date.fromisoformat(pre.as_of_date[:10]) if pre and len(pre.as_of_date)>=10 and pre.as_of_date[:10].count("-")==2 else (date.fromisoformat(review["as_of_date"]) if review else date.today())
            asof=st.date_input("As-of date",value=default_date)
            c=st.columns(4); tev_o=_override_input(c[0],"Điều chỉnh TEV (tỷ)",auto.get("tev"),f"ov_tev_{cid}"); ebit_o=_override_input(c[1],"Điều chỉnh EBIT (tỷ)",auto.get("ebit"),f"ov_ebit_{cid}"); ebitda_o=_override_input(c[2],"Điều chỉnh EBITDA (tỷ)",auto.get("ebitda"),f"ov_ebitda_{cid}"); norm_o=_override_input(c[3],"Điều chỉnh Normalized earnings (tỷ)",auto.get("normalized_earnings"),f"ov_norm_{cid}")
            c=st.columns(4); debt_o=_override_input(c[0],"Điều chỉnh Total debt (tỷ)",auto.get("total_debt"),f"ov_debt_{cid}"); interest_o=_override_input(c[1],"Điều chỉnh Interest expense (tỷ)",auto.get("interest_expense"),f"ov_interest_{cid}"); fcf_o=_override_input(c[2],"Điều chỉnh Current FCF (tỷ)",auto.get("fcf_current"),f"ov_fcf_{cid}"); mcap_o=_override_input(c[3],"Điều chỉnh Market cap (tỷ)",auto.get("market_cap"),f"ov_mcap_{cid}")
            c=st.columns(4); dps_o=_override_input(c[0],"Điều chỉnh Dividend/share (VND)",auto.get("dividend_per_share"),f"ov_dps_{cid}",formatter=fmt_price); price_o=_override_input(c[1],"Điều chỉnh Market price (VND)",auto.get("market_price"),f"ov_price_{cid}",formatter=fmt_price); fcf_est_o=_override_input(c[2],"Điều chỉnh FCF estimate/share (VND)",auto.get("fcf_estimate"),f"ov_fcf_est_{cid}",formatter=fmt_price); target_o=_override_input(c[3],"Điều chỉnh Target price (VND)",auto.get("target_price"),f"ov_target_{cid}",formatter=fmt_price)
            c=st.columns([1,1,1,3]); ccc_o=_override_input(c[0],"Điều chỉnh CCC (ngày)",auto.get("ccc_days"),f"ov_ccc_{cid}",formatter=lambda v:"—" if v is None else f"{v:,.0f}")
            mos_auto_pct=None if auto.get("mos") is None else float(auto["mos"])*100
            mos_o=c[1].number_input("Điều chỉnh MOS (%)",value=None,step=.1,format="%.1f",key=f"ov_mos_{cid}",placeholder=f"Tự động: {'—' if mos_auto_pct is None else f'{mos_auto_pct:.1f}%'}",help="Để trống = dùng MOS tự động từ Module 2.")
            thesis=c[2].selectbox("Δ Thesis",["unknown","up","flat","down"],format_func=lambda x:{"unknown":"?","up":"↑ Cải thiện","flat":"→ Không đổi","down":"↓ Suy giảm"}[x]); analyst_note=c[3].text_input("Ghi chú analyst",value="")
            overrides={"tev":tev_o,"ebit":ebit_o,"ebitda":ebitda_o,"normalized_earnings":norm_o,"total_debt":debt_o,"interest_expense":interest_o,"fcf_current":fcf_o,"market_cap":mcap_o,"dividend_per_share":dps_o,"market_price":price_o,"fcf_estimate":fcf_est_o,"target_price":target_o,"ccc_days":ccc_o}
            if st.form_submit_button("Lưu Inventory Snapshot hiệu lực",type="primary",use_container_width=True):
                effective={k:_effective(auto.get(k),v) for k,v in overrides.items()}; effective_mos=_effective(auto.get("mos"),None if mos_o is None else mos_o/100.0); changed=[k for k,v in overrides.items() if v is not None]
                if mos_o is not None: changed.append("mos")
                origin="mixed" if pre and changed else ("host_data_layer" if pre else "manual"); audit_note=analyst_note.strip()
                if changed: audit_note=f"{audit_note} | Manual overrides: {', '.join(changed)}".strip(" |")
                repo.save_inventory_snapshot(company_ref_id=cid,as_of_date=asof,review_id=review["id"] if review else None,mos=effective_mos,thesis_direction=thesis,note=audit_note,actor=actor,data_origin=origin,source_as_of_date=pre.as_of_date if pre else None,**effective); st.rerun()

    st.markdown("##### Snapshot gần nhất đã lưu — history/audit"); st.caption("Snapshot cũ không ghi đè dữ liệu tự động hiện tại; mọi điều chỉnh phải được analyst nhập rõ và tạo version/snapshot mới."); _saved_inventory_table(repo)
    inv=repo.inventory_history(cid)
    if inv:
        with st.expander("Lịch sử chi tiết Table 1.2"):
            h=pd.DataFrame(inv); money=[c for c in ["tev","ebit","ebitda","normalized_earnings","total_debt","interest_expense","fcf_current","market_cap","dividend_per_share","market_price","fcf_estimate","target_price"] if c in h]; ratio=[c for c in ["tev_ebit","tev_ebitda","tev_normalized_earnings","debt_ebitda","ebit_interest"] if c in h]; pct=[c for c in ["pretax_earnings_yield","fcf_yield_ev","fcf_yield_market","dividend_yield","price_vs_target","research_completion","mos"] if c in h]
            fm={c:(lambda v:"—" if pd.isna(v) else f"{v:,.0f}") for c in money}; fm.update({c:(lambda v:"—" if pd.isna(v) else f"{v:,.1f}x") for c in ratio}); fm.update({c:(lambda v:"—" if pd.isna(v) else f"{v*100:,.1f}%") for c in pct});
            if "ccc_days" in h: fm["ccc_days"]=lambda v:"—" if pd.isna(v) else f"{v:,.0f} ngày"
            nums=[c for c in h.columns if pd.api.types.is_numeric_dtype(h[c])]; st.dataframe(h.style.format(fm,na_rep="—").map(_heat,subset=nums),use_container_width=True,hide_index=True)


def _render_workspace(repo,cid,review,actor):
    st.markdown("#### Analyst Workspace — Q01–Q59")
    if not review: st.info("Tạo review để làm checklist."); return
    qs=repo.list_questions(); groups=list(dict.fromkeys(q["group_name"] for q in qs)); c1,c2=st.columns([1.2,2.8]); group=c1.selectbox("Nhóm",groups,key=f"q_group_{review['id']}"); qg=[q for q in qs if q["group_name"]==group]; qids=[q["question_id"] for q in qg]
    qid=c2.selectbox("Câu hỏi",qids,format_func=lambda x:f"{x} — {next(q for q in qg if q['question_id']==x)['question_vi']}",key=f"q_sel_{review['id']}_{group}"); q=next(q for q in qs if q["question_id"]==qid); current=repo.latest_assessment(review["id"],qid); prior=repo.latest_assessment(review["prior_review_id"],qid) if review.get("prior_review_id") else None
    st.markdown(f"### {qid}. {q['question_vi']}"); st.markdown(f"<div class='guide'><b>Hướng dẫn tự phân tích:</b> {q['guidance']}</div>",unsafe_allow_html=True); st.caption(f"Supporting tool (Phase sau): {q['supporting_tool'] or 'Không có'}")
    a,b=st.columns(2); a.markdown("**Current review**"); a.write(current or "Chưa có version"); b.markdown("**Prior completed review**"); b.write(prior or "Không có prior assessment")
    if review["status"]!="completed":
        if prior and st.button("↪ Confirm unchanged từ review trước",key=f"carry_{review['id']}_{qid}"): repo.confirm_unchanged(review["id"],qid,actor=actor); st.rerun()
        statuses=["not_reviewed","answered","research_gap","needs_review","na"]; status=st.selectbox("Status",statuses,index=_idx(statuses,current["status"] if current else (prior["status"] if prior else "not_reviewed")),format_func=lambda x:STATUS_LABELS[x],key=f"status_{review['id']}_{qid}")
        with st.form(f"assess_{review['id']}_{qid}"):
            answer=st.text_area("Câu trả lời của analyst",value=(current["analyst_answer"] if current else (prior["analyst_answer"] if prior else "")) or "",height=180)
            if status in {"answered","needs_review"}:
                opts=[-2,-1,0,1,2]; base=current["assessment"] if current and current["assessment"] is not None else (prior["assessment"] if prior and prior["assessment"] is not None else 0); assessment=st.radio("Assessment",opts,index=_idx(opts,base,2),horizontal=True,format_func=lambda x:ASSESSMENT_LABELS[x])
            else: assessment=None; st.caption("Status này không được quy đổi thành điểm Assessment.")
            if status in {"answered","needs_review","research_gap"}:
                cc=st.columns(2); conf=current["confidence"] if current and current["confidence"] else (prior["confidence"] if prior and prior["confidence"] else 3); mat=current["materiality"] if current and current["materiality"] else (prior["materiality"] if prior and prior["materiality"] else 3); confidence=cc[0].slider("Confidence",1,5,int(conf)); materiality=cc[1].slider("Materiality",1,5,int(mat))
            else: confidence=materiality=None
            reason=st.text_input("Reason for Change",help="Bắt buộc nếu Assessment thay đổi so với version hiện tại.")
            if st.form_submit_button("Lưu phiên bản mới",type="primary",use_container_width=True):
                try: repo.save_assessment(review_id=review["id"],question_id=qid,analyst_answer=answer,status=status,assessment=assessment,confidence=confidence,materiality=materiality,change_reason=reason,actor=actor); st.rerun()
                except ValidationError as exc: st.error(str(exc))
    else: st.info("Review đã completed. Hãy tạo review mới để cập nhật.")
    hist=repo.assessment_history(cid,qid)
    if hist: st.dataframe(pd.DataFrame(hist),use_container_width=True,hide_index=True)


def _render_history(repo,cid,review,actor):
    st.markdown("#### Snapshot & History")
    reviews=repo.list_reviews(cid)
    if reviews:
        st.markdown("##### Lịch sử toàn bộ review"); st.dataframe(pd.DataFrame(reviews),use_container_width=True,hide_index=True)
    if not review: st.info("Chưa có review."); return
    m=repo.review_metrics(review["id"]); c=st.columns(3); c[0].metric("Answered",m["answered"]); c[1].metric("Research gaps",m["research_gaps"]); c[2].metric("Completion",f"{m['research_completion']*100:.1f}%")
    if review["status"]!="completed":
        ok=st.checkbox("Tôi hiểu review sẽ bị khóa sau khi finalize.",key=f"fin_{review['id']}")
        if st.button("🔒 Finalize & Create Immutable Snapshot",type="primary",disabled=not ok,key=f"final_{review['id']}"): repo.finalize_review(review["id"],actor=actor); st.rerun()
    snaps=repo.list_snapshots(cid)
    if snaps:
        st.dataframe(pd.DataFrame(snaps),use_container_width=True,hide_index=True); sid=st.selectbox("View as-of snapshot",[s["id"] for s in snaps],format_func=lambda x:f"Snapshot #{x} — {next(s for s in snaps if s['id']==x)['as_of_date']}")
        with st.expander("Raw immutable payload (audit)"): st.json(repo.get_snapshot(sid)["payload"])
    else: st.info("Chưa có snapshot.")
    with st.expander("Audit log"):
        logs=repo.list_audit_logs(cid,200); st.dataframe(pd.DataFrame(logs),use_container_width=True,hide_index=True) if logs else st.caption("Chưa có log.")
    with st.expander("Integration sync log"):
        logs=repo.list_sync_logs(cid,100); st.dataframe(pd.DataFrame(logs),use_container_width=True,hide_index=True) if logs else st.caption("Chưa có sync log.")


def render_investment_checklist(host:HostContext,*,repo:Optional[SQLiteChecklistRepository]=None,data_provider:Optional[TrecapitalDataProvider]=None,theme:Optional[TrecapitalThemeAdapter]=None)->None:
    if theme: theme.inject_module_css()
    else: st.markdown(FALLBACK_CSS,unsafe_allow_html=True)
    repo=repo or build_repository(host); integration=ChecklistIntegrationService(repo,host,data_provider); cid,company=_company_cached(integration,host); actor=host.analyst.user_id
    st.markdown('<div class="checklist-module">',unsafe_allow_html=True); st.subheader("Investment Research & Checklist System"); st.caption("Phase 1C — Table 1.1 + Table 1.2 + Q01–Q59 + versioning + immutable snapshots. Không AI."); st.markdown(f"**{company['ticker']} — {company['company_name']}** · {company['industry_name'] or 'Chưa gán ngành'}"); st.markdown('<div class="principle"><b>Nguyên tắc:</b> Analyst tự trả lời, tự đánh giá; Unknown khác Neutral; mọi thay đổi được lưu version; review đã finalize là read-only.</div>',unsafe_allow_html=True)
    reviews=repo.list_reviews(cid); review=None; left,right=st.columns([2.4,1])
    if reviews:
        ids=[r["id"] for r in reviews]; state=f"checklist_review_{company['host_company_key']}"; desired=st.session_state.get(state); index=ids.index(desired) if desired in ids else 0; rid=left.selectbox("Review",ids,index=index,format_func=lambda x:_review_label(next(r for r in reviews if r["id"]==x)),key=f"review_select_{cid}"); st.session_state[state]=rid; review=next(r for r in reviews if r["id"]==rid)
    else: left.info("Chưa có review cho mã này.")
    with right.popover("➕ Tạo review mới",use_container_width=True):
        asof=st.date_input("As-of date",value=date.today(),key=f"new_review_date_{cid}"); rtype=st.selectbox("Loại review",["full","screening","delta"],key=f"new_review_type_{cid}")
        if st.button("Tạo review",use_container_width=True,key=f"create_review_{cid}"): rid=repo.create_review(cid,asof,rtype,actor); st.session_state[f"checklist_review_{company['host_company_key']}"]=rid; st.rerun()
    if review:
        st.caption(f"Review #{review['id']} · {review['as_of_date']} · {review['review_type']} · {review['status']}")
        if review["status"]=="completed": st.markdown('<span class="locked">🔒 Completed — read only</span>',unsafe_allow_html=True)
    # st.tabs executes every tab body on every Streamlit rerun. Rendering only the selected section keeps Q01-Q59 fast.
    section = st.radio("Khu vực checklist", SECTIONS, horizontal=True, label_visibility="collapsed", key=f"checklist_section_{cid}")
    if section==SECTIONS[0]: _render_home(repo,cid,review)
    elif section==SECTIONS[1]: _render_table11(repo,cid,review,actor)
    elif section==SECTIONS[2]: _render_table12(repo,integration,cid,review,actor)
    elif section==SECTIONS[3]: _render_workspace(repo,cid,review,actor)
    else: _render_history(repo,cid,review,actor)
    st.markdown("</div>",unsafe_allow_html=True)
