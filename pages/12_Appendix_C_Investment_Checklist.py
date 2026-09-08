from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.deep_company_analysis import appendix_c as appc
from modules.deep_company_analysis import appendix_c_history as hist
from modules.deep_company_analysis import appendix_c_history_store as hist_store
from modules.deep_company_analysis import appendix_c_workspace as ws

st.set_page_config(page_title="Appendix C — Investment Checklist", layout="wide")
st.title("Appendix C — Your Investment Checklist")
st.caption("Michael Shearn source-locked Q01–Q59 consolidated research view. Read-only bridge to owner chapter SSOT; AI = Research Assistant, analyst owns conclusions.")

ticker = st.text_input("Ticker", value="", placeholder="e.g. DCM").strip().upper()
company_name = st.text_input("Company name (optional)", value="").strip()

if not ticker:
    st.info("Enter a ticker to load the live owner-chapter research state.")
    st.stop()

rows = ws.build_live_rows(ticker, company_name)
errors = ws.validate_read_only_rows(rows)
if errors:
    for error in errors:
        st.error(error)
    st.stop()

counts = ws.research_completeness(rows)
cols = st.columns(4)
for col, label in zip(cols, ws.STATUS_ORDER):
    col.metric(label, counts[label])

st.caption("These are neutral research-completeness counts only — not a score, rank, Research Gate, valuation signal, or BUY/HOLD/SELL recommendation.")

summary = pd.DataFrame(ws.section_summary(rows)).rename(columns={
    "section_title": "Section",
    "question_count": "Questions",
    "answered": "Answered",
    "partial": "Partial",
    "unknown": "Unknown",
    "n_a": "N/A",
})[["Section", "Questions", "Answered", "Partial", "Unknown", "N/A"]]
st.subheader("Section overview")
st.dataframe(summary, use_container_width=True, hide_index=True)

st.subheader("Q01–Q59 research navigation")
section_filter = st.selectbox("Section", ["All"] + [appc.SECTION_TITLES[k] for k in appc.SECTION_ORDER])
status_filter = st.selectbox("Research status", ["All"] + list(ws.STATUS_ORDER))

visible = rows
if section_filter != "All":
    visible = [r for r in visible if r["section_title"] == section_filter]
if status_filter != "All":
    visible = [r for r in visible if r["question_status"] == status_filter]

frame = pd.DataFrame(visible).rename(columns={
    "question_id": "Question",
    "question": "Source-locked wording",
    "section_title": "Section",
    "owner_chapter": "Owner chapter",
    "question_status": "Research status",
    "confidence": "Confidence",
    "analyst_assessment": "Analyst assessment",
    "navigation_target": "Research target",
})[["Question", "Source-locked wording", "Section", "Owner chapter", "Research status", "Confidence", "Research target", "Analyst assessment"]]
st.dataframe(frame, use_container_width=True, hide_index=True)

qid = st.selectbox("Open research target", [r["question_id"] for r in visible] if visible else appc.QUESTION_IDS)
item = appc.get_item(qid)
if item:
    st.info(f"{qid} is owned by Chapter {item['owner_chapter']}. Continue research in the existing Chapter {item['owner_chapter']} workspace; Appendix C does not store or overwrite the answer.")

with st.expander("History, lineage & explicit analyst re-review", expanded=False):
    current_snapshot = hist.build_snapshot_payload(rows)
    st.caption(f"Current referential fingerprint: {hist.snapshot_fingerprint(current_snapshot)[:16]}…")
    st.write("Snapshots store only Qxx reference, owner chapter, research-status and confidence labels. They do not copy analyst assessments, evidence, financials, valuation, MOS or Research Gate state.")
    if st.button("Create immutable checklist snapshot"):
        sid = hist_store.create_snapshot(ticker, company_name, current_snapshot)
        st.success(f"Created neutral checklist snapshot #{sid}.")

    snapshots = hist_store.list_snapshots(ticker, company_name)
    if snapshots:
        lineage = pd.DataFrame([{
            "Snapshot": f"#{s['snapshot_id']}",
            "Created at": s["created_at"],
            "Fingerprint": s["fingerprint"][:16],
            "Question refs": len(s["payload"].get("question_refs", [])),
        } for s in snapshots])
        st.dataframe(lineage, use_container_width=True, hide_index=True)
        selected = st.selectbox("Compare snapshot to current", [s["snapshot_id"] for s in snapshots], format_func=lambda x: f"Snapshot #{x}")
        before = next(s["payload"] for s in snapshots if s["snapshot_id"] == selected)
        delta = hist.compare_snapshots(before, current_snapshot)
        st.dataframe(delta, use_container_width=True, hide_index=True)
        st.caption("Delta vocabulary is neutral: Unchanged / Added / Removed / Changed. It is not an investment-quality judgment.")

    note = st.text_area("Analyst re-review note", value="", help="Explicit metadata only; saving this note does not alter any Qxx answer, confidence, valuation or Research Gate.")
    if st.button("Record explicit re-review"):
        rid = hist_store.add_re_review(ticker, company_name, note)
        st.success(f"Recorded explicit analyst re-review #{rid} without changing owner-chapter state.")
    reviews = hist_store.list_re_reviews(ticker, company_name)
    if reviews:
        st.dataframe(pd.DataFrame(reviews), use_container_width=True, hide_index=True)

with st.expander("Source lock & boundaries"):
    st.write(f"Source: {appc.SOURCE_LOCK}; printed pages {appc.SOURCE_PRINT_PAGES[0]}–{appc.SOURCE_PRINT_PAGES[1]}.")
    st.write("No weighted score, management/growth score, BUY/HOLD/SELL, intrinsic-value/MOS change, Investment Research Gate change, or duplicate financial/question SSOT is created here.")
