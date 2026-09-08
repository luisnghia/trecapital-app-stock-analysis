from __future__ import annotations

"""Streamlit analyst workspace for Chapter 11 Q58-Q59 — Phase 11E / V86.

Research Assistant candidates remain suggestions. Evidence enters the durable workspace only
through explicit analyst promotion. Saving never changes analyst conclusions automatically and
never copies canonical financial SSOT into Chapter 11.
"""

import pandas as pd
import streamlit as st

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_research as research
from modules.deep_company_analysis.chapter11_store import load_record, save_record, promoted_candidate_ids
from modules.deep_company_analysis.table_format import render_static_table, sortable_data_editor


def _safe_ticker(value: str) -> str:
    return "".join(c for c in str(value).upper().strip() if c.isalnum() or c in {".", "-"})[:20]


def _candidate_session_key(ticker: str) -> str:
    return f"dca_ch11_candidates_{_safe_ticker(ticker)}"


def render_chapter11_tab(default_ticker: str = "") -> None:
    ticker = _safe_ticker(st.text_input("Mã cổ phiếu", value=default_ticker or "DGC", key="dca_ch11_ticker")) or "DGC"
    payload_key = f"dca_ch11_payload_{ticker}"
    if payload_key not in st.session_state:
        st.session_state[payload_key] = load_record(ticker)
    payload = ch11.normalize_payload(st.session_state[payload_key], ticker)

    st.subheader("Chương 11 — Evaluating Mergers & Acquisitions")
    st.caption("Michael Shearn — The Investment Checklist — Q58–Q59, printed pages 305–322. AI/Data = Research Assistant; analyst owns conclusions.")
    st.info("Unknown-first. Research candidates do not become evidence until explicitly promoted. No M&A score, acquisition-success conclusion, synergy forecast, BUY/HOLD/SELL, MOS or Investment Research Gate change is generated here.")

    for q in ch11.QUESTION_KEYS:
        with st.expander(f"{q} — {ch11.QUESTION_TITLES[q]}", expanded=(q == "Q58")):
            c1, c2 = st.columns(2)
            payload["question_status"][q] = c1.selectbox(
                "Research status", ch11.QUESTION_STATUS_OPTIONS,
                index=ch11.QUESTION_STATUS_OPTIONS.index(payload["question_status"][q]),
                key=f"ch11_status_{ticker}_{q}",
            )
            payload["confidence"][q] = c2.selectbox(
                "Confidence", ch11.CONFIDENCE_OPTIONS,
                index=ch11.CONFIDENCE_OPTIONS.index(payload["confidence"][q]),
                key=f"ch11_conf_{ticker}_{q}",
            )
            payload["analyst_assessment"][q] = st.text_area(
                "Analyst assessment", value=str(payload["analyst_assessment"].get(q) or "Unknown"),
                key=f"ch11_assess_{ticker}_{q}",
            )
            rows = []
            for item in ch11.EVIDENCE_DIMENSIONS[q]:
                dim_id = item["id"]
                rows.append({
                    "Dimension ID": dim_id,
                    "Dimension": item["label"],
                    "Printed Pages": f"{item['pages'][0]}-{item['pages'][1]}",
                    "Status": payload["dimension_status"].get(dim_id, "Unknown"),
                })
            edited = sortable_data_editor(
                pd.DataFrame(rows), hide_index=True, use_container_width=True,
                disabled=["Dimension ID", "Dimension", "Printed Pages"],
                column_config={"Status": st.column_config.SelectboxColumn(options=list(ch11.DIMENSION_STATUS_OPTIONS))},
                key=f"ch11_dims_{ticker}_{q}",
            )
            for row in edited.to_dict("records"):
                payload["dimension_status"][str(row["Dimension ID"])] = str(row["Status"])

    st.markdown("### Research Assistant — candidate evidence")
    c1, c2 = st.columns(2)
    dimension_id = c1.selectbox("Dimension", list(ch11.dimension_ids()), key=f"ch11_candidate_dim_{ticker}")
    direction = c2.selectbox("Direction", ch11.EVIDENCE_DIRECTION_OPTIONS, key=f"ch11_candidate_dir_{ticker}")
    title = st.text_input("Source title", key=f"ch11_candidate_title_{ticker}")
    url = st.text_input("Source URL / file", key=f"ch11_candidate_url_{ticker}")
    evidence_text = st.text_area("Evidence / reference", key=f"ch11_candidate_text_{ticker}")
    source_date = st.text_input("Source date / period", key=f"ch11_candidate_date_{ticker}")
    ck = _candidate_session_key(ticker)
    st.session_state.setdefault(ck, [])
    if st.button("➕ Add candidate for analyst review", key=f"ch11_add_candidate_{ticker}"):
        frame = research.build_candidates([{
            "dimension_id": dimension_id, "title": title, "url": url,
            "text": evidence_text, "source_date": source_date, "direction": direction,
        }])
        st.session_state[ck].extend(frame.to_dict("records"))
        st.rerun()

    candidates = pd.DataFrame(st.session_state.get(ck, []), columns=research.CANDIDATE_COLUMNS)
    if not candidates.empty:
        promoted = promoted_candidate_ids(payload)
        candidates["Already Promoted"] = candidates["Candidate ID"].astype(str).isin(promoted)
        shown = sortable_data_editor(
            candidates, hide_index=True, use_container_width=True,
            disabled=[c for c in candidates.columns if c != "Select"],
            key=f"ch11_candidates_editor_{ticker}",
        )
        selected = shown.loc[(shown["Select"] == True) & (~shown["Already Promoted"]), "Candidate ID"].astype(str).tolist()  # noqa: E712
        if st.button("✅ Promote selected evidence", disabled=not selected, key=f"ch11_promote_{ticker}"):
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

    st.markdown("### Open research gaps")
    gaps = research.research_gaps(candidates if not candidates.empty else None)
    render_static_table(gaps, hide_index=True, use_container_width=True)

    st.session_state[payload_key] = payload
    if st.button("💾 Save Chapter 11 workspace", type="primary", use_container_width=True, key=f"ch11_save_{ticker}"):
        st.session_state[payload_key] = save_record(ticker, payload)
        st.success("Saved analyst-owned Chapter 11 workspace. Canonical financial SSOT was not copied or mutated.")


__all__ = ["render_chapter11_tab"]
