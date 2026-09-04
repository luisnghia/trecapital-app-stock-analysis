from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "modules" / "deep_company_analysis" / "chapter5_page_support.py"

text = SUPPORT.read_text(encoding="utf-8")

old_import = "from modules.deep_company_analysis.chapter5 import load_record, render_chapter5\n"
new_import = "from modules.deep_company_analysis.chapter5 import load_record, render_chapter5, save_record\n"
if old_import in text:
    text = text.replace(old_import, new_import, 1)
elif new_import not in text:
    raise SystemExit("chapter5_page_support.py: Chapter 5 import marker not found")

quant_import = "from modules.deep_company_analysis.chapter5_quant import build_chapter5_quant_context\n"
evidence_import = '''from modules.deep_company_analysis.chapter5_evidence import (\n    Chapter5EvidenceAgent,\n    evidence_quality_summary,\n    guardrails as phase5c_guardrails,\n    merge_candidates_into_record,\n    research_gaps,\n)\n'''
if evidence_import not in text:
    if quant_import not in text:
        raise SystemExit("chapter5_page_support.py: quant import marker not found")
    text = text.replace(quant_import, quant_import + evidence_import, 1)

marker = "\ndef render_chapter5_tab(default_ticker: str) -> None:\n"
if "def render_phase5c_research_assistant(" not in text:
    if marker not in text:
        raise SystemExit("chapter5_page_support.py: render_chapter5_tab marker not found")
    block = r'''

def render_phase5c_research_assistant(ticker: str, company_name: str = "") -> None:
    """Research evidence only; never mutates analyst conclusions automatically."""
    safe = _safe_ticker(ticker) or "DGC"
    session_key = f"ch5c_result_{safe}"
    gaps_key = f"ch5c_gaps_{safe}"
    note_key = f"ch5c_note_{safe}"
    audit_key = f"ch5c_audit_{safe}"

    with st.container(border=True):
        st.markdown("### 🔎 Phase 5C — Research Assistant Q21–Q26")
        st.caption(
            "Assistant tìm Candidate Evidence + Counter-Evidence và Research Gaps. "
            "Không tự sửa Q21–Q26, không tự chọn KPI critical, không chấm Frequency/Severity, "
            "không kết luận Strong/Weak Balance Sheet, High-quality ROIC hay Compounder."
        )
        st.info(
            "Ưu tiên: nguồn doanh nghiệp/IR & công bố chính thức → nguồn tài chính độc lập → nguồn bối cảnh. "
            "Search result/link điều hướng không được coi là bằng chứng."
        )

        c1, c2 = st.columns([2, 1])
        with c1:
            run = st.button(
                "🔎 Nghiên cứu tự động Q21–Q26",
                use_container_width=True,
                key=f"ch5c_run_{safe}",
                type="primary",
            )
        with c2:
            if st.button("🧹 Xóa kết quả tạm", use_container_width=True, key=f"ch5c_clear_{safe}"):
                for key in (session_key, gaps_key, note_key, audit_key):
                    st.session_state.pop(key, None)
                st.rerun()

        if run:
            record = load_record(safe, company_name)
            quant_ctx, _ = load_chapter5_quant(safe, record)
            raw_dir = Path(__file__).resolve().parents[2] / "data_cache" / "deep_company_analysis_evidence"
            with st.spinner(f"Đang nghiên cứu source-first cho {safe} — Q21 đến Q26..."):
                result = Chapter5EvidenceAgent(raw_dir).search(safe, company_name, max_results_per_query=4)
                gaps = research_gaps(result.candidates, quant_ctx)
            st.session_state[session_key] = result.candidates
            st.session_state[gaps_key] = gaps
            st.session_state[note_key] = result.note
            st.session_state[audit_key] = result.source_audit

        candidates = st.session_state.get(session_key)
        gaps = st.session_state.get(gaps_key, [])
        note = str(st.session_state.get(note_key, ""))
        if isinstance(candidates, pd.DataFrame):
            if note:
                st.success(note)
            summary = evidence_quality_summary(candidates)
            st.markdown("**Evidence Coverage — Research completeness, không phải investment-quality score**")
            st.dataframe(summary, use_container_width=True, hide_index=True, height=250)

            if not candidates.empty:
                display_cols = [
                    "Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness",
                    "Title", "URL", "Snippet", "Source Method",
                ]
                st.markdown("**Candidate Evidence / Counter-Evidence**")
                st.dataframe(
                    candidates[[c for c in display_cols if c in candidates.columns]],
                    use_container_width=True,
                    hide_index=True,
                    height=430,
                )
                st.caption(
                    "Direction chỉ là hướng candidate để chống confirmation bias; analyst phải mở nguồn gốc và xác minh. "
                    "Không có Candidate nào tự chuyển thành Verified."
                )
            else:
                st.warning("Chưa lấy được Candidate Evidence usable. App không bịa evidence để lấp chỗ trống.")

            if gaps:
                st.markdown("**Research Gaps được gợi ý**")
                st.dataframe(pd.DataFrame(gaps), use_container_width=True, hide_index=True, height=min(360, 80 + 45 * len(gaps)))

            if st.button(
                "➕ Lưu Candidate Evidence + Research Gaps vào Chương 5",
                use_container_width=True,
                key=f"ch5c_save_{safe}",
                disabled=candidates.empty and not gaps,
            ):
                current = load_record(safe, company_name)
                before_analyst = {
                    q: dict(current.get(q, {})) for q in ("q21", "q22", "q23", "q24", "q25", "q26")
                }
                merged = merge_candidates_into_record(current, candidates, gaps)
                # Hard runtime assertion: research refresh must not alter analyst judgement objects.
                after_analyst = {
                    q: dict(merged.get(q, {})) for q in ("q21", "q22", "q23", "q24", "q25", "q26")
                }
                if after_analyst != before_analyst:
                    raise RuntimeError("Phase 5C guardrail breach: analyst Q21–Q26 fields changed")
                save_record(merged, create_snapshot=False)
                st.success(
                    "Đã lưu dưới trạng thái Candidate — Analyst verify. Không tạo analyst snapshot mới và không thay kết luận Q21–Q26."
                )

            with st.expander("🛡️ Phase 5C guardrails & source audit", expanded=False):
                st.write(phase5c_guardrails())
                st.write(st.session_state.get(audit_key, {}))
                st.caption(
                    "Missing evidence = Research Gap, không phải Low Risk. Media attention không phải Severity. "
                    "Canonical financial data vẫn thuộc Trecapital Data Layer / Phase 5B."
                )
        else:
            st.caption("Bấm Nghiên cứu tự động để tạo evidence candidates. Không chạy ngầm và không tự thay analyst judgement.")
'''
    text = text.replace(marker, block + marker, 1)

old_tab = '''def render_chapter5_tab(default_ticker: str) -> None:\n    safe, company_name = render_phase5b_quantitative_bridge(default_ticker)\n    render_chapter5(default_ticker=safe, company_name=company_name)'''
new_tab = '''def render_chapter5_tab(default_ticker: str) -> None:\n    safe, company_name = render_phase5b_quantitative_bridge(default_ticker)\n    render_phase5c_research_assistant(safe, company_name)\n    render_chapter5(default_ticker=safe, company_name=company_name)'''
if old_tab in text:
    text = text.replace(old_tab, new_tab, 1)
elif new_tab not in text:
    raise SystemExit("chapter5_page_support.py: render_chapter5_tab body marker not found")

SUPPORT.write_text(text, encoding="utf-8")
print("Applied Chapter 5 Phase 5C Research Assistant UI integration")
