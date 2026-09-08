from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from modules.deep_company_analysis.appendix_b import (
    APPENDIX_TITLE,
    CONTEXTUAL_CHECKS,
    FACE_TO_FACE_CAVEATS,
    INTERVIEW_PROTOCOL,
    MANAGEMENT_INTERVIEW_TOPICS,
    SOURCE_LOCK,
)
from modules.deep_company_analysis.appendix_b_store import (
    list_research_gaps,
    list_sessions,
    save_research_gap,
    save_session,
)
from modules.deep_company_analysis.appendix_b_workspace import (
    CAVEAT_OPTIONS,
    DCA_QUESTION_IDS,
    SESSION_STATUS_OPTIONS,
    new_research_gap,
    new_session,
    normalize_session,
)

st.set_page_config(page_title="Appendix B — Management Interview", layout="wide")
st.title(f"Appendix B — {APPENDIX_TITLE}")
st.caption(f"Source lock: {SOURCE_LOCK}. Research Assistant organizes evidence; analyst owns interpretation and conclusions.")

with st.expander("Source-locked interview protocol", expanded=False):
    for item in INTERVIEW_PROTOCOL:
        st.write(f"• {item}")
    st.warning("Face-to-face access can increase confidence without increasing accuracy. Meeting impressions are caveats, never management-quality signals.")

DB_PATH = Path("data_cache") / "deep_company_analysis_appendix_b.sqlite"
col1, col2 = st.columns([1, 2])
with col1:
    ticker = st.text_input("Ticker / Company key", key="appb_ticker").strip().upper()
with col2:
    company_name = st.text_input("Company name", key="appb_company_name").strip()

if not ticker:
    st.info("Enter a ticker/company key to open the management-interview workspace.")
    st.stop()

st.subheader("Create interview session")
c1, c2, c3 = st.columns(3)
with c1:
    participant = st.text_input("Management participant / role")
with c2:
    interview_date = st.date_input("Interview date").isoformat()
with c3:
    if st.button("Create / open session", use_container_width=True, disabled=not participant.strip()):
        session = new_session(ticker, participant, interview_date, company_name)
        save_session(DB_PATH, session)
        st.session_state["appb_selected_session"] = session["session_id"]
        st.rerun()

sessions = list_sessions(DB_PATH, ticker)
if sessions:
    labels = {s["session_id"]: f"{s['interview_date']} — {s['management_participant_role']} — {s['status']}" for s in sessions}
    selected_id = st.selectbox(
        "Interview sessions",
        options=list(labels),
        format_func=lambda value: labels[value],
        index=max(0, list(labels).index(st.session_state.get("appb_selected_session"))) if st.session_state.get("appb_selected_session") in labels else 0,
    )
    current = normalize_session(next(s for s in sessions if s["session_id"] == selected_id))
    current["status"] = st.selectbox("Session status", SESSION_STATUS_OPTIONS, index=SESSION_STATUS_OPTIONS.index(current["status"]))

    st.markdown("### Interview notes by source-locked topic")
    for idx, topic in enumerate(MANAGEMENT_INTERVIEW_TOPICS):
        entry = current["topic_entries"][idx]
        with st.expander(topic, expanded=False):
            entry["open_ended_question"] = st.text_area("Open-Ended Question", value=entry["open_ended_question"], key=f"q_{selected_id}_{idx}")
            entry["management_response_observation"] = st.text_area("Management Response / Observation", value=entry["management_response_observation"], key=f"r_{selected_id}_{idx}")
            entry["clarification_follow_up"] = st.text_area("Clarification / Follow-up", value=entry["clarification_follow_up"], key=f"f_{selected_id}_{idx}")
            entry["past_behavior_evidence"] = st.text_area("Past-Behavior Evidence", value=entry["past_behavior_evidence"], key=f"p_{selected_id}_{idx}")
            entry["hypothetical_flag"] = st.checkbox("Hypothetical answer — do not treat as evidence of future behavior", value=entry["hypothetical_flag"], key=f"h_{selected_id}_{idx}")
            entry["face_to_face_caveat"] = st.selectbox("Face-to-Face Caveat", CAVEAT_OPTIONS, index=CAVEAT_OPTIONS.index(entry["face_to_face_caveat"]), key=f"c_{selected_id}_{idx}")
            entry["dca_question_refs"] = st.multiselect("Related DCA questions (reference only)", DCA_QUESTION_IDS, default=entry["dca_question_refs"], key=f"d_{selected_id}_{idx}")
            entry["analyst_commentary"] = st.text_area("Analyst Commentary", value=entry["analyst_commentary"], key=f"a_{selected_id}_{idx}")

    current["contextual_checks"] = st.multiselect("Contextual checks used", CONTEXTUAL_CHECKS, default=[x for x in current["contextual_checks"] if x in CONTEXTUAL_CHECKS])
    current["analyst_session_note"] = st.text_area("Analyst session note", value=current["analyst_session_note"])
    if st.button("Save interview session", type="primary"):
        save_session(DB_PATH, current)
        st.success("Session saved. DCA links remain references only; no chapter state or investment gate was changed.")

st.divider()
st.subheader("Research gaps linked to DCA Q01–Q59")
gap_text = st.text_area("Research gap")
gap_refs = st.multiselect("Related DCA questions", DCA_QUESTION_IDS, key="appb_gap_refs")
gap_session = st.selectbox("Related session (optional)", [""] + [s["session_id"] for s in sessions], format_func=lambda x: "No session" if not x else x)
if st.button("Add research gap", disabled=not gap_text.strip()):
    save_research_gap(DB_PATH, new_research_gap(ticker, gap_text, gap_refs, gap_session))
    st.rerun()

gaps = list_research_gaps(DB_PATH, ticker)
if gaps:
    st.dataframe(
        [{"Gap": g["gap_text"], "DCA refs": ", ".join(g["dca_question_refs"]), "Status": g["status"], "Session": g["session_id"]} for g in gaps],
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Boundary reminder"):
    st.write("No management/CEO/credibility/personality score; no BUY/HOLD/SELL; no intrinsic-value/MOS or Investment Research Gate change; no duplicate financial SSOT.")
    st.write("Meeting impressions and caveats are retained for analyst re-review only.")
