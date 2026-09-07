from __future__ import annotations

"""Idempotently wire Phase 8L official file ingestion into the Chapter 8 page."""

from pathlib import Path


PATH = Path("modules/deep_company_analysis/chapter8_page_support.py")
MARKER = "### Phase 8L — Official File / PDF Ingestion"

FUNCTION = r'''

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
'''


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    changed = False
    if MARKER not in text:
        anchor = "\ndef _render_question_status(ticker: str, payload: dict[str, Any]) -> None:\n"
        if anchor not in text:
            raise SystemExit("Phase 8L insertion anchor not found")
        text = text.replace(anchor, FUNCTION + anchor, 1)
        changed = True

    call = "        _render_direct_official_urls(ticker, company_name, annual, chapter7_payload)\n        payload = _render_research(ticker, company_name, chapter7_payload, payload)"
    replacement = "        _render_direct_official_urls(ticker, company_name, annual, chapter7_payload)\n        _render_official_files(ticker, company_name, annual, chapter7_payload)\n        payload = _render_research(ticker, company_name, chapter7_payload, payload)"
    if "_render_official_files(ticker, company_name, annual, chapter7_payload)" not in text:
        if call not in text:
            raise SystemExit("Phase 8L render-call anchor not found")
        text = text.replace(call, replacement, 1)
        changed = True

    if changed:
        PATH.write_text(text, encoding="utf-8")
        print("Applied Chapter 8 Phase 8L UI wiring")
    else:
        print("Chapter 8 Phase 8L UI wiring already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
