from __future__ import annotations

import streamlit as st

from modules.deep_company_analysis.appendix_a import (
    APPENDIX_TITLE,
    CONTACT_PRINCIPLES,
    HUMAN_SOURCE_TYPES,
    NOTE_STATEMENT_TYPES,
    NOTE_TAKING_PRINCIPLES,
    SECTION_KEYS,
    SECTION_TITLES,
    SOURCE_CLASS_OPTIONS,
)
from modules.deep_company_analysis.appendix_a_history import (
    build_interview_lineage,
    build_version_lineage,
    compare_versions,
)
from modules.deep_company_analysis.appendix_a_store import (
    create_appendix_a_snapshot,
    list_appendix_a_snapshots,
    load_appendix_a_workspace,
    save_appendix_a_workspace,
)
from modules.deep_company_analysis.appendix_a_workspace import (
    GAP_STATUS_OPTIONS,
    QUESTION_IDS,
    SECTION_STATUS_OPTIONS,
    make_interview_record,
    make_research_gap,
    make_source_record,
    normalize_workspace,
)
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav

st.set_page_config(page_title="Appendix A — Human Intelligence Network", layout="wide")
apply_full_width()
render_tre_sidebar_nav()

st.title(f"Appendix A — {APPENDIX_TITLE}")
st.caption("AI = Research Assistant. Nguồn tin và ghi chú hỗ trợ nghiên cứu; analyst sở hữu mọi diễn giải và kết luận. Không có source score, credibility score hay investment signal.")

ticker = st.text_input("Mã cổ phiếu", key="appa_ticker").strip().upper()
company_name = st.text_input("Doanh nghiệp", key="appa_company")
state_key = f"appendix_a_workspace::{ticker or '_'}"
if state_key not in st.session_state:
    st.session_state[state_key] = load_appendix_a_workspace(ticker, company_name=company_name) if ticker else normalize_workspace({}, ticker="", company_name=company_name)
ws = normalize_workspace(st.session_state[state_key], ticker=ticker, company_name=company_name)

with st.expander("Source-locked workflow status", expanded=False):
    for key in SECTION_KEYS:
        current = ws["sections"].get(key, "Unknown")
        ws["sections"][key] = st.selectbox(SECTION_TITLES[key], SECTION_STATUS_OPTIONS, index=SECTION_STATUS_OPTIONS.index(current), key=f"appa_section_{key}_{ticker}")

source_tab, interview_tab, gap_tab, synthesis_tab, history_tab = st.tabs(["Nguồn tin", "Phỏng vấn", "Research gaps", "Analyst synthesis", "History / lineage"])

with source_tab:
    st.subheader("Human source records")
    with st.form(f"appa_source_form_{ticker}", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        source_name = c1.text_input("Source Name / Alias")
        source_class = c2.selectbox("Source Class", SOURCE_CLASS_OPTIONS)
        source_type = c3.selectbox("Source Type", HUMAN_SOURCE_TYPES)
        organization = st.text_input("Organization / Context")
        relationship = st.text_input("First-hand Relationship")
        tenure = st.text_input("Industry Tenure / History")
        why_know = st.text_area("Why This Source May Know")
        introduced_by = st.text_input("Introduced / Referred By")
        analyst_note = st.text_area("Analyst Note")
        if st.form_submit_button("Thêm nguồn") and source_name.strip():
            ws["sources"].append(make_source_record(source_name=source_name, source_class=source_class, source_type=source_type, organization_context=organization, first_hand_relationship=relationship, industry_tenure_history=tenure, why_source_may_know=why_know, introduced_by=introduced_by, analyst_note=analyst_note))
            ws = normalize_workspace(ws)
    if ws["sources"]:
        st.dataframe(ws["sources"], use_container_width=True, hide_index=True)
    with st.expander("Nguyên tắc liên hệ nguồn", expanded=False):
        for item in CONTACT_PRINCIPLES:
            st.write(f"• {item}")

with interview_tab:
    st.subheader("Interview database")
    source_ids = [item["source_id"] for item in ws["sources"]]
    if not source_ids:
        st.info("Tạo ít nhất một source record trước khi ghi interview.")
    else:
        with st.form(f"appa_interview_form_{ticker}", clear_on_submit=True):
            source_id = st.selectbox("Source ID", source_ids)
            interview_date = st.date_input("Interview Date").isoformat()
            prompt = st.text_area("Question / Prompt")
            response = st.text_area("Source Response / Observation", help="Ghi lời nguồn/quan sát riêng, không chèn diễn giải analyst.")
            statement_type = st.selectbox("Statement Type", NOTE_STATEMENT_TYPES)
            uncertainty = st.text_area("Uncertainty Noted", help="Nếu ý nghĩa chưa chắc chắn, ghi rõ thay vì tự hợp lý hóa.")
            refs = st.multiselect("Related DCA Questions", QUESTION_IDS)
            commentary = st.text_area("Analyst Commentary", help="Diễn giải của analyst được lưu riêng khỏi lời nguồn.")
            if st.form_submit_button("Lưu interview"):
                ws["interviews"].append(make_interview_record(source_id=source_id, interview_date=interview_date, question_prompt=prompt, source_response_observation=response, statement_type=statement_type, uncertainty_noted=uncertainty, related_question_refs=refs, analyst_commentary=commentary))
                ws = normalize_workspace(ws)
    if ws["interviews"]:
        st.dataframe(ws["interviews"], use_container_width=True, hide_index=True)
    with st.expander("Nguyên tắc ghi chép", expanded=False):
        for item in NOTE_TAKING_PRINCIPLES:
            st.write(f"• {item}")

with gap_tab:
    st.subheader("Research-gap linkage")
    st.caption("Q01–Q59 ở đây chỉ là reference. Appendix A không đọc/ghi Research Gate hoặc kết luận của chapter gốc.")
    with st.form(f"appa_gap_form_{ticker}", clear_on_submit=True):
        gap_question = st.text_area("Unanswered Question / Assumption")
        preferred = st.selectbox("Preferred Source Type", HUMAN_SOURCE_TYPES)
        why_matters = st.text_area("Why First-hand Evidence Matters")
        refs = st.multiselect("Related DCA Questions", QUESTION_IDS, key=f"appa_gap_refs_{ticker}")
        status = st.selectbox("Status", GAP_STATUS_OPTIONS)
        note = st.text_area("Analyst Note", key=f"appa_gap_note_{ticker}")
        if st.form_submit_button("Thêm research gap") and gap_question.strip():
            ws["research_gaps"].append(make_research_gap(unanswered_question_assumption=gap_question, preferred_source_type=preferred, why_first_hand_evidence_matters=why_matters, related_question_refs=refs, status=status, analyst_note=note))
            ws = normalize_workspace(ws)
    if ws["research_gaps"]:
        st.dataframe(ws["research_gaps"], use_container_width=True, hide_index=True)

with synthesis_tab:
    ws["analyst_synthesis"] = st.text_area("Analyst synthesis", value=ws.get("analyst_synthesis", ""), height=220, help="Chỉ analyst viết kết luận; hệ thống không tự suy luận từ nguồn tin.")

with history_tab:
    st.subheader("Immutable research history")
    st.caption("Delta chỉ cho biết hồ sơ nghiên cứu thay đổi. Không đánh giá credibility, không tạo score và không thay BUY/HOLD/SELL, MOS hay Research Gate.")
    lineage = build_interview_lineage(ws)
    if lineage.empty:
        st.info("Chưa có interview để hiển thị lineage.")
    else:
        st.markdown("**Interview lineage**")
        st.dataframe(lineage, use_container_width=True, hide_index=True)
    snapshots = list_appendix_a_snapshots(ticker) if ticker else []
    if snapshots:
        st.markdown("**Version lineage**")
        st.dataframe(build_version_lineage(snapshots), use_container_width=True, hide_index=True)
        choices = {f"Snapshot #{item['snapshot_id']} — {item['created_at']}": item for item in snapshots}
        selected_label = st.selectbox("So sánh snapshot với workspace hiện tại", list(choices), key=f"appa_history_compare_{ticker}")
        selected = choices[selected_label]
        delta = compare_versions(selected["payload"], ws, before_label=selected_label, after_label="Current workspace")
        changed_only = st.checkbox("Chỉ hiện thay đổi", value=True, key=f"appa_changed_only_{ticker}")
        if changed_only:
            delta = delta[delta["Delta"] != "Unchanged"]
        st.dataframe(delta, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có snapshot. Lưu workspace rồi tạo snapshot để bắt đầu version lineage.")

st.session_state[state_key] = normalize_workspace(ws, ticker=ticker, company_name=company_name)
button_col1, button_col2 = st.columns(2)
if button_col1.button("Lưu Appendix A workspace", type="primary", disabled=not bool(ticker)):
    saved = save_appendix_a_workspace(st.session_state[state_key])
    st.session_state[state_key] = saved
    st.success("Đã lưu human-source workspace. Không thay đổi Research Gate/MOS/investment conclusion.")
if button_col2.button("Tạo immutable snapshot", disabled=not bool(ticker)):
    saved = save_appendix_a_workspace(st.session_state[state_key])
    snapshot = create_appendix_a_snapshot(saved)
    st.success(f"Đã tạo Snapshot #{snapshot['snapshot_id']}. Snapshot chỉ lưu analyst-owned research state.")
