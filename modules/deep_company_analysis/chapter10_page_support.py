from __future__ import annotations

"""Streamlit analyst workspace for Chapter 10 Q53-Q57.

Research Assistant candidates are suggestions only. Promotion is explicit, and neither
promotion nor saving changes analyst conclusions automatically. V79 adds a neutral research
completion gate and analyst-owned growth synthesis/report section.
"""

import pandas as pd
import streamlit as st

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_completion as completion
import modules.deep_company_analysis.chapter10_research as research
from modules.deep_company_analysis.chapter10_store import load_record, save_record, promoted_candidate_ids
from modules.deep_company_analysis.table_format import render_static_table, sortable_data_editor


def _safe_ticker(value: str) -> str:
    return "".join(c for c in str(value).upper().strip() if c.isalnum() or c in {".", "-"})[:20]


def _candidate_session_key(ticker: str) -> str:
    return f"dca_ch10_candidates_{_safe_ticker(ticker)}"


def render_chapter10_tab(default_ticker: str = "") -> None:
    ticker = _safe_ticker(st.text_input("Mã cổ phiếu", value=default_ticker or "DGC", key="dca_ch10_ticker")) or "DGC"
    payload_key = f"dca_ch10_payload_{ticker}"
    if payload_key not in st.session_state:
        st.session_state[payload_key] = load_record(ticker)
    payload = ch10.normalize_payload(st.session_state[payload_key], ticker)

    st.subheader("Chương 10 — Evaluating Growth Opportunities")
    st.caption("Michael Shearn — The Investment Checklist — Q53–Q57, printed pages 281–303. AI/Data = Research Assistant; analyst owns conclusions.")
    st.info("Unknown-first. Research candidates do not become evidence until you explicitly promote them. No Growth Score, forecast, BUY/HOLD/SELL, MOS or Research Gate change is generated here.")

    for q in ch10.QUESTION_KEYS:
        with st.expander(f"{q} — {ch10.QUESTION_TITLES[q]}", expanded=(q == "Q53")):
            c1, c2 = st.columns(2)
            payload["question_status"][q] = c1.selectbox("Research status", ch10.QUESTION_STATUS_OPTIONS, index=ch10.QUESTION_STATUS_OPTIONS.index(payload["question_status"][q]), key=f"ch10_status_{ticker}_{q}")
            payload["confidence"][q] = c2.selectbox("Confidence", ch10.CONFIDENCE_OPTIONS, index=ch10.CONFIDENCE_OPTIONS.index(payload["confidence"][q]), key=f"ch10_conf_{ticker}_{q}")
            payload["analyst_assessment"][q] = st.text_area("Analyst assessment", value=str(payload["analyst_assessment"].get(q) or "Unknown"), key=f"ch10_assess_{ticker}_{q}")
            if q == "Q53":
                payload["growth_mode"] = st.selectbox("Growth mode — analyst owned", ch10.GROWTH_MODE_OPTIONS, index=ch10.GROWTH_MODE_OPTIONS.index(payload.get("growth_mode", "Unknown")), key=f"ch10_growth_mode_{ticker}")
            rows = []
            for item in ch10.EVIDENCE_DIMENSIONS[q]:
                dim_id = item["id"]
                rows.append({"Dimension ID": dim_id, "Dimension": item["label"], "Printed Pages": f"{item['pages'][0]}-{item['pages'][1]}", "Status": payload["dimension_status"].get(dim_id, "Unknown")})
            edited = sortable_data_editor(
                pd.DataFrame(rows), hide_index=True, use_container_width=True,
                disabled=["Dimension ID", "Dimension", "Printed Pages"],
                column_config={"Status": st.column_config.SelectboxColumn(options=list(ch10.DIMENSION_STATUS_OPTIONS))},
                key=f"ch10_dims_{ticker}_{q}",
            )
            for row in edited.to_dict("records"):
                payload["dimension_status"][str(row["Dimension ID"])] = str(row["Status"])

    st.markdown("### Research Assistant — candidate evidence")
    c1, c2 = st.columns(2)
    dim_ids = list(ch10.dimension_ids())
    dimension_id = c1.selectbox("Dimension", dim_ids, key=f"ch10_candidate_dim_{ticker}")
    direction = c2.selectbox("Direction", ch10.EVIDENCE_DIRECTION_OPTIONS, key=f"ch10_candidate_dir_{ticker}")
    title = st.text_input("Source title", key=f"ch10_candidate_title_{ticker}")
    url = st.text_input("Source URL / file", key=f"ch10_candidate_url_{ticker}")
    evidence_text = st.text_area("Evidence / reference", key=f"ch10_candidate_text_{ticker}")
    source_date = st.text_input("Source date / period", key=f"ch10_candidate_date_{ticker}")
    ck = _candidate_session_key(ticker)
    st.session_state.setdefault(ck, [])
    if st.button("➕ Add candidate for analyst review", key=f"ch10_add_candidate_{ticker}"):
        frame = research.build_candidates([{"dimension_id": dimension_id, "title": title, "url": url, "text": evidence_text, "source_date": source_date, "direction": direction}])
        st.session_state[ck].extend(frame.to_dict("records"))
        st.rerun()

    candidates = pd.DataFrame(st.session_state.get(ck, []), columns=research.CANDIDATE_COLUMNS)
    if not candidates.empty:
        promoted = promoted_candidate_ids(payload)
        candidates["Already Promoted"] = candidates["Candidate ID"].astype(str).isin(promoted)
        shown = sortable_data_editor(candidates, hide_index=True, use_container_width=True, disabled=[c for c in candidates.columns if c != "Select"], key=f"ch10_candidates_editor_{ticker}")
        selected = shown.loc[(shown["Select"] == True) & (~shown["Already Promoted"]), "Candidate ID"].astype(str).tolist()  # noqa: E712
        if st.button("✅ Promote selected evidence", disabled=not selected, key=f"ch10_promote_{ticker}"):
            payload = research.promote_selected_candidates(payload, candidates, selected)
            st.session_state[payload_key] = payload
            st.success(f"Promoted {len(selected)} candidate(s). Analyst conclusions remain unchanged.")
            st.rerun()
    else:
        st.caption("No candidate evidence yet. Add a source above; every candidate requires analyst review.")

    st.markdown("### Promoted evidence")
    evidence_df = pd.DataFrame(payload.get("evidence", []))
    if not evidence_df.empty:
        render_static_table(evidence_df, hide_index=True, use_container_width=True)
    gaps = research.research_gaps(candidates if not candidates.empty else None)
    st.markdown("### Open research gaps")
    render_static_table(gaps, hide_index=True, use_container_width=True)

    st.markdown("### Research Completion Gate")
    gate = completion.completion_gate(payload)
    c1, c2, c3 = st.columns(3)
    c1.metric("Questions research-ready", f"{sum(v['ready'] for v in gate['questions'].values())}/{gate['total_questions']}")
    c2.metric("Resolved dimensions", f"{gate['resolved_dimensions']}/{gate['total_dimensions']}")
    c3.metric("Chapter research-ready", "Yes" if gate["ready"] else "No")
    gate_rows = [{"Question": q, "Research Ready": v["ready"], "Status": v["research_status"], "Confidence": v["confidence"], "Open Dimensions": len(v["unresolved_dimensions"]), "Blockers": "; ".join(v["reasons"])} for q, v in gate["questions"].items()]
    render_static_table(pd.DataFrame(gate_rows), hide_index=True, use_container_width=True)
    st.caption("Completion means research completeness only; it is not a growth-quality score or investment recommendation.")

    st.markdown("### Analyst Growth Synthesis")
    synthesis = completion.normalize_synthesis(payload.get("growth_synthesis"))
    synthesis["status"] = st.selectbox("Synthesis status", completion.SYNTHESIS_STATUS_OPTIONS, index=completion.SYNTHESIS_STATUS_OPTIONS.index(synthesis["status"]), key=f"ch10_syn_status_{ticker}")
    synthesis["growth_route_takeaway"] = st.text_area("Growth route takeaway", synthesis["growth_route_takeaway"], key=f"ch10_syn_route_{ticker}")
    synthesis["profitability_takeaway"] = st.text_area("Profitability takeaway", synthesis["profitability_takeaway"], key=f"ch10_syn_profit_{ticker}")
    synthesis["runway_takeaway"] = st.text_area("Growth runway takeaway", synthesis["runway_takeaway"], key=f"ch10_syn_runway_{ticker}")
    synthesis["pace_and_funding_takeaway"] = st.text_area("Growth pace & funding takeaway", synthesis["pace_and_funding_takeaway"], key=f"ch10_syn_pace_{ticker}")
    synthesis["key_strengths"] = st.text_area("Key strengths", synthesis["key_strengths"], key=f"ch10_syn_strengths_{ticker}")
    synthesis["key_concerns"] = st.text_area("Key concerns", synthesis["key_concerns"], key=f"ch10_syn_concerns_{ticker}")
    synthesis["key_unknowns"] = st.text_area("Key unknowns", synthesis["key_unknowns"], key=f"ch10_syn_unknowns_{ticker}")
    synthesis["final_growth_synthesis"] = st.text_area("Final growth synthesis — analyst owned", synthesis["final_growth_synthesis"], key=f"ch10_syn_final_{ticker}")
    synthesis["analyst_note"] = st.text_area("Analyst note", synthesis["analyst_note"], key=f"ch10_syn_note_{ticker}")
    payload["growth_synthesis"] = completion.normalize_synthesis(synthesis)

    st.markdown("### Chapter 10 Report Preview")
    report = completion.report_section(payload)
    render_static_table(pd.DataFrame(report["questions"]), hide_index=True, use_container_width=True)
    st.caption(report["boundary_note"])

    st.session_state[payload_key] = payload
    if st.button("💾 Save Chapter 10 workspace", type="primary", use_container_width=True, key=f"ch10_save_{ticker}"):
        st.session_state[payload_key] = save_record(ticker, payload)
        st.success("Saved analyst-owned Chapter 10 workspace and synthesis. Canonical financial SSOT was not copied or mutated.")


__all__ = ["render_chapter10_tab"]
