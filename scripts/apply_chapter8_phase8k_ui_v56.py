from __future__ import annotations

"""Idempotently wire Phase 8K direct official URL ingestion into the Chapter 8 UI."""

from pathlib import Path


PAGE = Path("modules/deep_company_analysis/chapter8_page_support.py")

FUNCTION_MARKER = "def _render_direct_official_urls("
FUNCTION_INSERT_BEFORE = "\ndef _render_question_status(ticker: str, payload: dict[str, Any]) -> None:\n"
CALL_OLD = """    with st.container(border=True):\n        payload = _render_research(ticker, company_name, chapter7_payload, payload)\n"""
CALL_NEW = """    with st.container(border=True):\n        _render_direct_official_urls(ticker, company_name, annual, chapter7_payload)\n        payload = _render_research(ticker, company_name, chapter7_payload, payload)\n"""

FUNCTION = r'''
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
'''


def main() -> int:
    text = PAGE.read_text(encoding="utf-8")
    changed = False

    if FUNCTION_MARKER not in text:
        if FUNCTION_INSERT_BEFORE not in text:
            raise SystemExit("Cannot locate Chapter 8 question-status insertion point")
        text = text.replace(FUNCTION_INSERT_BEFORE, "\n" + FUNCTION + FUNCTION_INSERT_BEFORE, 1)
        changed = True

    if CALL_NEW not in text:
        if CALL_OLD not in text:
            raise SystemExit("Cannot locate Chapter 8 research container call")
        text = text.replace(CALL_OLD, CALL_NEW, 1)
        changed = True

    if changed:
        PAGE.write_text(text, encoding="utf-8")
        print("Applied Chapter 8 Phase 8K UI wiring")
    else:
        print("Chapter 8 Phase 8K UI wiring already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
