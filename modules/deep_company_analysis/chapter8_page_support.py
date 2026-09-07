from __future__ import annotations

"""Chapter 8 Phase 8D Streamlit analyst workspace.

UI boundary: Phase 8B structured data and Phase 8C research are assistants. Only the
analyst edits conclusions/status/confidence and explicitly promotes evidence.
"""

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

import module1_dashboard as m1
from module1_engine import append_ttm_row
import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter7 import load_record as load_chapter7_record
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_completion import build_completion_gate, completion_gate_text
from modules.deep_company_analysis.chapter8_research_v52 import CANDIDATE_COLUMNS, Chapter8ResearchAgent
from modules.deep_company_analysis.chapter8_store import create_snapshot, list_snapshots, load_record, save_record
from modules.deep_company_analysis.chapter8_workspace import merge_research_gaps, promote_selected_candidates
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.table_format import render_static_table, sortable_data_editor


APP_DIR = Path(__file__).resolve().parents[2]


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _rows_frame(rows: Any, columns: list[str]) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        frame = rows.copy()
    elif isinstance(rows, list):
        frame = pd.DataFrame([dict(x) for x in rows if isinstance(x, dict)])
    else:
        frame = pd.DataFrame()
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def _editor(
    label: str,
    rows: Any,
    columns: list[str],
    key: str,
    *,
    height: int = 320,
    disabled: list[str] | None = None,
    column_config: dict[str, Any] | None = None,
    dynamic: bool = True,
) -> list[dict[str, Any]]:
    st.markdown(f"**{label}**")
    frame = _rows_frame(rows, columns)
    edited = sortable_data_editor(
        frame,
        key=key,
        hide_index=True,
        use_container_width=True,
        height=height,
        num_rows="dynamic" if dynamic else "fixed",
        disabled=disabled or [],
        column_config=column_config or {},
    )
    return edited.to_dict("records") if isinstance(edited, pd.DataFrame) else frame.to_dict("records")


def _active_or_cached_paths(ticker: str) -> tuple[Path, Path, Path] | None:
    safe = _safe_ticker(ticker)
    active = _safe_ticker(str(st.session_state.get("active_ticker") or ""))
    active_paths = (
        st.session_state.get("active_overview_csv"),
        st.session_state.get("active_year_csv"),
        st.session_state.get("active_quarter_csv"),
    )
    if active == safe and all(x and Path(str(x)).exists() for x in active_paths):
        return tuple(Path(str(x)) for x in active_paths)  # type: ignore[return-value]

    names = ("company_overview_sample.csv", "financial_timeseries_year.csv", "financial_timeseries_quarter.csv")
    candidates: list[tuple[float, tuple[Path, Path, Path]]] = []
    try:
        for root in m1.DATA_CACHE_DIR.iterdir():
            candidate_root = root / safe
            candidate = tuple(candidate_root / name for name in names)
            if all(path.exists() and path.stat().st_size > 20 for path in candidate):
                candidates.append((max(path.stat().st_mtime for path in candidate), candidate))
    except Exception:
        pass
    return max(candidates, key=lambda x: x[0])[1] if candidates else None


def _canonical_context(ticker: str) -> tuple[pd.DataFrame, str, str]:
    paths = _active_or_cached_paths(ticker)
    if not paths:
        return pd.DataFrame(), "", "Chưa có canonical bundle local. Bấm cập nhật canonical để lấy dữ liệu mới."
    overview_path, year_path, quarter_path = paths
    try:
        company = m1._load_overview_cached(str(overview_path), ticker)
        annual_raw = m1._load_timeseries_cached(str(year_path), ticker, "Y", 11)
        quarterly = m1._load_timeseries_cached(str(quarter_path), ticker, "Q", 20)
        annual = append_ttm_row(annual_raw, quarterly)
        company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
        return annual, company_name, f"{year_path.parent}"
    except Exception as exc:
        return pd.DataFrame(), "", f"Không đọc được canonical bundle: {exc}"


def _render_source_lock() -> None:
    with st.expander("🔒 Source-lock Chương 8 — Management Competence: How Management Operates the Business", expanded=True):
        st.markdown(
            """
- Q39–Q47 bám theo **Michael Shearn — The Investment Checklist — Chapter 8**.
- **Chapter 7 manager master** là nguồn duy nhất cho Manager ID/background; Chương 8 không tạo manager giả.
- **Trecapital canonical financial data / Module 1** là financial SSOT. Web research chỉ là evidence/event candidate.
- Phase 8C chỉ tạo **Candidate — analyst verify**. Candidate chỉ vào Evidence Matrix sau khi analyst tick chọn và bấm **Promote**.
- `Unknown` và `Research Gap` là kết quả hợp lệ khi thiếu bằng chứng. App không lấp chỗ trống bằng suy đoán.
- Chương 8 **không có automatic management score và không thay đổi MOS / Research Gate / BUY-HOLD-SELL**.
            """
        )


def _render_bridge(ticker: str, annual: pd.DataFrame, chapter7_payload: dict[str, Any], payload: dict[str, Any]) -> None:
    st.markdown("### Phase 8B — Structured Context")
    bridge = build_phase8b_context(
        ticker,
        annual,
        chapter7_payload=chapter7_payload,
        guidance_rows=payload.get("q41_guidance_history"),
    )
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"Manager SSOT: {bridge['manager_ssot']}")
    with c2:
        st.caption(f"Financial SSOT: {bridge['financial_ssot']}")
    for warning in bridge.get("warnings", []):
        st.warning(str(warning))
    if not bridge["manager_reference"].empty:
        render_static_table(bridge["manager_reference"], height=230, sort_key=f"dca8_{ticker}_manager_ref")
    with st.expander("Q45 — Canonical cost context", expanded=False):
        render_static_table(bridge["q45_cost_context"], height=330, sort_key=f"dca8_{ticker}_q45_ctx")
    with st.expander("Q46 — 5 uses of excess FCF context", expanded=True):
        render_static_table(bridge["q46_capital_allocation_context"], height=350, sort_key=f"dca8_{ticker}_q46_ctx")
    with st.expander("Q47 — Explicit buyback context", expanded=False):
        render_static_table(bridge["q47_buyback_context"], height=320, sort_key=f"dca8_{ticker}_q47_ctx")


def _render_research(ticker: str, company_name: str, chapter7_payload: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    st.markdown("### Phase 8C — Evidence Research Assistant")
    state_key = f"dca8_research_result_{ticker}"
    c1, c2 = st.columns([1, 2])
    with c1:
        run_research = st.button("🔎 Tự nghiên cứu Q39–Q47", use_container_width=True, key=f"dca8_{ticker}_research")
    with c2:
        st.caption("Tìm nguồn doanh nghiệp/IR + nguồn web tập trung. Kết quả vẫn là candidate, không tự thành analyst evidence.")
    if run_research:
        with st.spinner(f"Đang nghiên cứu {ticker} — Q39 đến Q47..."):
            result = Chapter8ResearchAgent(m1.RAW_DIR / "chapter8_phase8d_v45").search(
                ticker,
                company_name,
                chapter7_payload=chapter7_payload,
                max_results_per_query=2,
                max_official_documents=18,
            )
        st.session_state[state_key] = {
            "candidates": result.candidates.to_dict("records"),
            "quality": result.quality.to_dict("records"),
            "gaps": result.gaps.to_dict("records"),
            "manager_reference": result.manager_reference.to_dict("records"),
            "source_attempts": result.source_attempts.to_dict("records"),
            "note": result.note,
        }

    research = st.session_state.get(state_key)
    if not isinstance(research, dict):
        st.info("Chưa có research run trong session này. Analyst có thể làm workspace thủ công hoặc chạy Research Assistant.")
        return payload

    quality = pd.DataFrame(research.get("quality") or [])
    if not quality.empty:
        render_static_table(quality, height=310, sort_key=f"dca8_{ticker}_quality")

    candidates = _rows_frame(research.get("candidates"), CANDIDATE_COLUMNS)
    if not candidates.empty:
        st.markdown("**Evidence Candidates — tick Select sau khi đã mở/đọc nguồn**")
        candidates["Select"] = candidates["Select"].fillna(False).astype(bool)
        edited = sortable_data_editor(
            candidates,
            key=f"dca8_{ticker}_candidate_editor",
            hide_index=True,
            use_container_width=True,
            height=500,
            num_rows="fixed",
            disabled=[c for c in CANDIDATE_COLUMNS if c != "Select"],
            column_config={
                "Select": st.column_config.CheckboxColumn("Promote?"),
                "Source URL / File": st.column_config.LinkColumn("Mở nguồn", display_text="Open source"),
            },
        )
        research["candidates"] = edited.to_dict("records") if isinstance(edited, pd.DataFrame) else candidates.to_dict("records")
        st.session_state[state_key] = research
        if st.button("✅ Promote evidence đã chọn", use_container_width=True, key=f"dca8_{ticker}_promote"):
            payload, added = promote_selected_candidates(payload, edited)
            save_record(ticker, payload, company_name)
            st.success(f"Đã promote {added} evidence. Analyst Assessment/Confidence/Status không bị ghi đè.")
    else:
        st.info("Research run chưa tìm thấy evidence candidate đủ điều kiện; giữ Unknown/Research Gap thay vì suy đoán.")

    gaps = pd.DataFrame(research.get("gaps") or [])
    if not gaps.empty:
        st.markdown("**Research Gaps do assistant phát hiện**")
        render_static_table(gaps, height=330, sort_key=f"dca8_{ticker}_research_gaps_preview")
        if st.button("➕ Đưa Research Gaps vào analyst workspace", use_container_width=True, key=f"dca8_{ticker}_merge_gaps"):
            payload, added = merge_research_gaps(payload, gaps)
            save_record(ticker, payload, company_name)
            st.success(f"Đã thêm {added} research gap mới; các Analyst Note hiện có được giữ nguyên.")

    attempts = pd.DataFrame(research.get("source_attempts") or [])
    if not attempts.empty:
        with st.expander("Source attempt log", expanded=False):
            render_static_table(attempts, height=300, sort_key=f"dca8_{ticker}_attempts")
    note = str(research.get("note") or "")
    if note:
        with st.expander("Research run note", expanded=False):
            st.caption(note)
    return payload



def _render_direct_official_urls(
    ticker: str,
    company_name: str,
    annual: pd.DataFrame,
    chapter7_payload: dict[str, Any],
) -> None:
    """Phase 8K: explicit direct official URL ingestion without search-engine dependency."""
    st.markdown("### Phase 8K — Direct Official Source URLs")
    st.caption(
        "Dán URL trực tiếp từ website/IR doanh nghiệp, HOSE/HSX, HNX hoặc SSC. "
        "App chỉ nhận domain chính thức, kiểm tra đúng mã cổ phiếu rồi mới tạo Candidate — analyst verify."
    )
    state_key = f"dca8_research_result_{ticker}"
    raw_urls = st.text_area(
        "Official URL(s) — mỗi dòng một URL",
        value="",
        height=105,
        key=f"dca8_{ticker}_direct_official_urls",
        placeholder="https://staticfile.hsx.vn/Uploads/UploadDocuments/...pdf",
        help="Nguồn ngoài allow-list chính thức sẽ bị từ chối. Không tự promote evidence.",
    )
    ingest = st.button(
        "📥 Nạp nguồn chính thức trực tiếp",
        use_container_width=True,
        key=f"dca8_{ticker}_direct_official_ingest",
    )
    if not ingest:
        research = st.session_state.get(state_key)
        if isinstance(research, dict):
            direct_attempts = pd.DataFrame(research.get("direct_official_attempts") or [])
            if not direct_attempts.empty:
                with st.expander("Phase 8K — Direct official URL log", expanded=False):
                    render_static_table(direct_attempts, height=260, sort_key=f"dca8_{ticker}_direct_attempts")
        return

    urls = [line.strip() for line in str(raw_urls or "").replace(";", "\n").splitlines() if line.strip()]
    if not urls:
        st.warning("Hãy dán ít nhất một URL chính thức trước khi nạp.")
        return

    research = st.session_state.get(state_key)
    if not isinstance(research, dict):
        research = {}
    existing = _rows_frame(research.get("candidates"), CANDIDATE_COLUMNS)
    bridge = build_phase8b_context(
        ticker,
        annual,
        chapter7_payload=chapter7_payload,
        guidance_rows=None,
    )
    manager_reference = pd.DataFrame(research.get("manager_reference") or [])
    if manager_reference.empty:
        manager_reference = bridge.get("manager_reference", pd.DataFrame())

    with st.spinner(f"Đang nạp và kiểm tra nguồn chính thức cho {ticker}..."):
        agent = Chapter8ResearchAgent(m1.RAW_DIR / "chapter8_phase8k_v56")
        result = agent.ingest_official_urls(
            ticker,
            urls,
            existing_candidates=existing,
            manager_reference=manager_reference,
            max_targets=48,
            max_urls=20,
        )

    research["candidates"] = result.merged_candidates.to_dict("records")
    research["quality"] = result.quality.to_dict("records")
    research["gaps"] = result.remaining_gaps.to_dict("records")
    research["manager_reference"] = manager_reference.to_dict("records") if isinstance(manager_reference, pd.DataFrame) else []
    research.setdefault("source_attempts", [])
    research["direct_official_attempts"] = result.attempts.to_dict("records")
    prior_note = str(research.get("note") or "").strip()
    research["note"] = f"{prior_note} | {result.note}" if prior_note else result.note
    st.session_state[state_key] = research

    fetched = int(result.attempts["Status"].eq("Fetched").sum()) if not result.attempts.empty else 0
    st.success(
        f"Phase 8K: fetched {fetched}/{len(result.attempts)} URL chính thức; "
        f"tạo {len(result.new_candidates)} candidate mới. Candidate vẫn cần analyst kiểm tra/promote."
    )
    if not result.attempts.empty:
        render_static_table(result.attempts, height=260, sort_key=f"dca8_{ticker}_direct_attempts_now")


def _render_official_files(
    ticker: str,
    company_name: str,
    annual: pd.DataFrame,
    chapter7_payload: dict[str, Any],
) -> None:
    """Phase 8L: local official PDF/file ingestion when source CDNs are inaccessible."""
    st.markdown("### Phase 8L — Official File / PDF Ingestion")
    st.caption(
        "Tải trực tiếp BCTN/BCQT/CBTT chính thức để app đọc cục bộ, không phụ thuộc HOSE/HNX/CDN. "
        "File phải khớp mã cổ phiếu; evidence vẫn là Candidate — analyst verify."
    )
    state_key = f"dca8_research_result_{ticker}"
    uploads = st.file_uploader(
        "Official files",
        type=["pdf", "docx", "txt", "html", "htm"],
        accept_multiple_files=True,
        key=f"dca8_{ticker}_official_files_v57",
        help="Không OCR tự động. PDF scan không có text sẽ được giữ là gap thay vì suy đoán.",
    )
    c1, c2 = st.columns(2)
    with c1:
        issuer = st.selectbox(
            "Nguồn phát hành",
            ["Company/IR", "HOSE/HSX", "HNX", "SSC"],
            key=f"dca8_{ticker}_official_file_issuer_v57",
        )
    with c2:
        source_url = st.text_input(
            "URL nguồn chính thức (không bắt buộc)",
            value="",
            key=f"dca8_{ticker}_official_file_url_v57",
            help="Nếu nhập URL, URL phải thuộc allow-list nguồn chính thức. Nếu bỏ trống, provenance vẫn cần analyst xác nhận.",
        )
    confirmed = st.checkbox(
        "Tôi xác nhận file được tải từ nguồn chính thức đã chọn",
        value=False,
        key=f"dca8_{ticker}_official_file_confirm_v57",
    )
    ingest = st.button(
        "📄 Phân tích file chính thức",
        use_container_width=True,
        key=f"dca8_{ticker}_official_file_ingest_v57",
    )
    if not ingest:
        research = st.session_state.get(state_key)
        if isinstance(research, dict):
            attempts = pd.DataFrame(research.get("official_file_attempts") or [])
            if not attempts.empty:
                with st.expander("Phase 8L — Official file log", expanded=False):
                    render_static_table(attempts, height=300, sort_key=f"dca8_{ticker}_official_file_attempts")
        return

    if not uploads:
        st.warning("Hãy chọn ít nhất một PDF/DOCX/TXT/HTML chính thức.")
        return
    if not confirmed and not str(source_url or "").strip():
        st.warning("Nếu không có URL nguồn chính thức, analyst phải xác nhận provenance của file trước khi nạp.")
        return

    research = st.session_state.get(state_key)
    if not isinstance(research, dict):
        research = {}
    existing = _rows_frame(research.get("candidates"), CANDIDATE_COLUMNS)
    bridge = build_phase8b_context(
        ticker,
        annual,
        chapter7_payload=chapter7_payload,
        guidance_rows=None,
    )
    manager_reference = pd.DataFrame(research.get("manager_reference") or [])
    if manager_reference.empty:
        manager_reference = bridge.get("manager_reference", pd.DataFrame())

    file_items = [
        {
            "name": upload.name,
            "bytes": upload.getvalue(),
            "issuer": issuer,
            "source_url": str(source_url or "").strip(),
            "official_confirmed": bool(confirmed),
        }
        for upload in uploads
    ]
    with st.spinner(f"Đang đọc và kiểm tra {len(file_items)} file chính thức cho {ticker}..."):
        agent = Chapter8ResearchAgent(m1.RAW_DIR / "chapter8_phase8l_v57")
        result = agent.ingest_official_files(
            ticker,
            file_items,
            existing_candidates=existing,
            manager_reference=manager_reference,
            max_targets=48,
            max_files=12,
        )

    research["candidates"] = result.merged_candidates.to_dict("records")
    research["quality"] = result.quality.to_dict("records")
    research["gaps"] = result.remaining_gaps.to_dict("records")
    research["manager_reference"] = manager_reference.to_dict("records") if isinstance(manager_reference, pd.DataFrame) else []
    research.setdefault("source_attempts", [])
    research["official_file_attempts"] = result.attempts.to_dict("records")
    research["official_file_documents"] = result.documents.to_dict("records")
    research["official_file_raw_paths"] = list(result.raw_paths)
    prior_note = str(research.get("note") or "").strip()
    research["note"] = f"{prior_note} | {result.note}" if prior_note else result.note
    st.session_state[state_key] = research

    accepted = int(result.attempts["Status"].eq("Accepted").sum()) if not result.attempts.empty else 0
    st.success(
        f"Phase 8L: accepted {accepted}/{len(result.attempts)} file; "
        f"tạo {len(result.new_candidates)} candidate mới. Không evidence nào được auto-promote."
    )
    if not result.attempts.empty:
        render_static_table(result.attempts, height=320, sort_key=f"dca8_{ticker}_official_file_attempts_now")

def _render_question_status(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("### Analyst Status & Conclusions — Q39 đến Q47")
    for question in ch8.QUESTION_KEYS:
        title = ch8.QUESTION_TITLES[question]
        with st.expander(f"{question} — {title}", expanded=question in {"Q39", "Q46"}):
            c1, c2 = st.columns(2)
            statuses = list(ch8.QUESTION_STATUS_OPTIONS)
            confidences = list(ch8.CONFIDENCE_OPTIONS)
            current_status = str(payload["question_status"].get(question) or "Unknown")
            current_conf = str(payload["confidence"].get(question) or "Unknown")
            with c1:
                payload["question_status"][question] = st.selectbox(
                    "Research status",
                    statuses,
                    index=statuses.index(current_status) if current_status in statuses else 0,
                    key=f"dca8_{ticker}_{question}_status",
                )
            with c2:
                payload["confidence"][question] = st.selectbox(
                    "Analyst confidence",
                    confidences,
                    index=confidences.index(current_conf) if current_conf in confidences else 0,
                    key=f"dca8_{ticker}_{question}_confidence",
                )
            current = str(payload["analyst_assessment"].get(question) or "")
            payload["analyst_assessment"][question] = st.text_area(
                "Analyst Assessment / Conclusion",
                value="" if current == "Unknown" else current,
                key=f"dca8_{ticker}_{question}_assessment",
                help="Đây là kết luận của analyst. Research Assistant không ghi vào ô này.",
            ) or "Unknown"


def _render_source_tables(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("### Source-Locked Analyst Tables")
    payload["q39_stakeholders"] = _editor(
        "Q39 — Stakeholder Evidence",
        payload.get("q39_stakeholders"), ch8.STAKEHOLDER_EVIDENCE_COLUMNS, f"dca8_{ticker}_q39", height=360, dynamic=False,
    )
    payload["q40_operating_approach"] = _editor(
        "Q40 — Operating Approach", payload.get("q40_operating_approach"), ch8.OPERATING_APPROACH_COLUMNS, f"dca8_{ticker}_q40", height=350,
    )
    payload["q41_guidance_history"] = _editor(
        "Q41 — Guidance History", payload.get("q41_guidance_history"), ch8.GUIDANCE_HISTORY_COLUMNS, f"dca8_{ticker}_q41", height=350,
        column_config={"Guidance Event": st.column_config.SelectboxColumn("Guidance Event", options=list(ch8.GUIDANCE_EVENT_OPTIONS))},
    )
    payload["q42_organization_structure"] = _editor(
        "Q42 — Organization / Decision Rights", payload.get("q42_organization_structure"), ch8.ORG_STRUCTURE_COLUMNS, f"dca8_{ticker}_q42", height=350,
    )
    org_options = list(ch8.ORG_STRUCTURE_OPTIONS)
    current_org = str(payload.get("q42_analyst_structure") or "Unknown")
    payload["q42_analyst_structure"] = st.selectbox(
        "Q42 — Analyst structure conclusion",
        org_options,
        index=org_options.index(current_org) if current_org in org_options else 0,
        key=f"dca8_{ticker}_q42_structure",
    )
    payload["q43_employee_relations"] = _editor(
        "Q43 — 14 Employee-Relation Prompts", payload.get("q43_employee_relations"), ch8.EMPLOYEE_RELATION_COLUMNS, f"dca8_{ticker}_q43", height=470, dynamic=False,
        column_config={"Evidence Direction": st.column_config.SelectboxColumn("Evidence Direction", options=list(ch8.EVIDENCE_DIRECTION_OPTIONS))},
    )
    payload["q44_hiring_evidence"] = _editor(
        "Q44 — Hiring Evidence", payload.get("q44_hiring_evidence"), ch8.HIRING_EVIDENCE_COLUMNS, f"dca8_{ticker}_q44", height=370,
    )
    payload["q45_cost_actions"] = _editor(
        "Q45 — Cost Actions", payload.get("q45_cost_actions"), ch8.COST_ACTION_COLUMNS, f"dca8_{ticker}_q45", height=370,
    )
    payload["q46_capital_allocation"] = _editor(
        "Q46 — Capital Allocation Decision Register", payload.get("q46_capital_allocation"), ch8.CAPITAL_ALLOCATION_COLUMNS, f"dca8_{ticker}_q46", height=390,
    )
    payload["q47_buyback_history"] = _editor(
        "Q47 — Explicit Buyback History", payload.get("q47_buyback_history"), ch8.BUYBACK_HISTORY_COLUMNS, f"dca8_{ticker}_q47", height=390,
    )


def _render_evidence_gap_events(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("### Evidence Matrix, Research Gaps & Management Events")
    payload["evidence"] = _editor(
        "Promoted / Manual Evidence Matrix", payload.get("evidence"), ch8.EVIDENCE_COLUMNS, f"dca8_{ticker}_evidence", height=430,
        column_config={"Source URL / File": st.column_config.LinkColumn("Source URL / File", display_text="Open source")},
    )
    payload["research_gaps"] = _editor(
        "Research Gap Workflow", payload.get("research_gaps"), ch8.RESEARCH_GAP_COLUMNS, f"dca8_{ticker}_gaps", height=350,
    )
    payload["management_events"] = _editor(
        "Management Event Register", payload.get("management_events"), ch8.MANAGEMENT_EVENT_COLUMNS, f"dca8_{ticker}_events", height=340,
    )


def render_chapter8_tab(default_ticker: str = "DGC") -> None:
    ticker = _safe_ticker(st.text_input("Mã cổ phiếu", value=_safe_ticker(default_ticker) or "DGC", key="dca_ch8_ticker")) or "DGC"
    annual, canonical_company_name, canonical_note = _canonical_context(ticker)
    payload = load_record(ticker, canonical_company_name)
    payload["ticker"] = ticker

    st.title("🧭 Chương 8 — Năng lực vận hành của Ban điều hành")
    st.caption("Management Competence: How Management Operates the Business | Phase 8A–8F | final research-completion gate")
    _render_source_lock()

    c1, c2 = st.columns([3, 1])
    with c1:
        if annual.empty:
            st.warning(canonical_note)
        else:
            st.success(f"Đã nối Trecapital canonical cho {ticker}: {canonical_note}")
    with c2:
        if st.button("🔄 Cập nhật canonical", use_container_width=True, key=f"dca8_{ticker}_refresh_canonical"):
            with st.spinner(f"Đang cập nhật canonical bundle cho {ticker}..."):
                ok, _, note = refresh_peer_canonical_bundle(ticker)
            if ok:
                st.success(note)
                st.rerun()
            else:
                st.warning(note)

    payload["company_name"] = st.text_input(
        "Tên doanh nghiệp", value=str(payload.get("company_name") or canonical_company_name or ""), key=f"dca8_{ticker}_company_name"
    )
    company_name = str(payload.get("company_name") or canonical_company_name or "")
    chapter7_payload = load_chapter7_record(ticker)

    with st.container(border=True):
        _render_bridge(ticker, annual, chapter7_payload, payload)
    with st.container(border=True):
        _render_direct_official_urls(ticker, company_name, annual, chapter7_payload)
        _render_official_files(ticker, company_name, annual, chapter7_payload)
        payload = _render_research(ticker, company_name, chapter7_payload, payload)
    with st.container(border=True):
        _render_question_status(ticker, payload)
    with st.container(border=True):
        _render_source_tables(ticker, payload)
    with st.container(border=True):
        _render_evidence_gap_events(ticker, payload)

    completion_context = build_phase8b_context(
        ticker,
        annual,
        chapter7_payload=chapter7_payload,
        guidance_rows=payload.get("q41_guidance_history"),
    )
    completion_gate = build_completion_gate(
        payload,
        structured_context=completion_context,
        chapter7_payload=chapter7_payload,
    )
    with st.container(border=True):
        st.markdown("### ✅ Final Research Completion Gate — Q39–Q47")
        gate_text = completion_gate_text(completion_gate)
        if completion_gate["ready_for_chapter_close"]:
            st.success(gate_text)
        else:
            st.warning(gate_text)
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Closed questions", f"{completion_gate['closed_count']}/{completion_gate['total_questions']}")
        g2.metric("Open questions", len(completion_gate["open_questions"]))
        g3.metric("Q43 dimensions evidenced", f"{completion_gate['q43_dimensions_evidenced']}/{completion_gate['q43_dimensions_total']}")
        g4.metric("Q46 source lock", "PASS" if completion_gate["q46_source_lock_ok"] else "FAIL")
        render_static_table(completion_gate["table"], height=470, sort_key=f"dca8_{ticker}_completion_gate")
        st.caption(completion_gate["gate_boundary"])

    warnings = ch8.research_gap_warnings(payload)
    if warnings:
        st.warning("Research completeness:\n\n- " + "\n- ".join(warnings))

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Lưu Chapter 8 workspace", use_container_width=True, key=f"dca8_{ticker}_save"):
            save_record(ticker, payload, company_name)
            st.success("Đã lưu Chapter 8. Research/structured data không ghi đè Analyst Assessment.")
    with c2:
        if st.button("📸 Lưu snapshot Chapter 8", use_container_width=True, key=f"dca8_{ticker}_snapshot"):
            snapshot_id = create_snapshot(ticker, payload)
            st.success(f"Đã lưu snapshot #{snapshot_id}.")

    snapshots = pd.DataFrame(list_snapshots(ticker, 20))
    if not snapshots.empty:
        st.markdown("### Snapshot History")
        render_static_table(snapshots, height=300, sort_key=f"dca8_{ticker}_snapshots")


__all__ = ["render_chapter8_tab"]
