from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "modules" / "deep_company_analysis" / "chapter5_page_support.py"

text = SUPPORT.read_text(encoding="utf-8")

anchor = '''from modules.deep_company_analysis.chapter5_evidence import (
    Chapter5EvidenceAgent,
    evidence_quality_summary,
    guardrails as phase5c_guardrails,
    merge_candidates_into_record,
    research_gaps,
)
'''
lock_import = '''from modules.deep_company_analysis.chapter5_lock import (
    evaluate_chapter5_lock,
    guardrails as phase5d_guardrails,
)
'''
if lock_import not in text:
    if anchor not in text:
        raise SystemExit("chapter5_page_support.py: Phase 5C import anchor not found")
    text = text.replace(anchor, anchor + lock_import, 1)

marker = "\ndef render_chapter5_tab(default_ticker: str) -> None:\n"
if "def render_phase5d_lock_panel(" not in text:
    if marker not in text:
        raise SystemExit("chapter5_page_support.py: render_chapter5_tab marker not found")
    block = r'''

def _saved_phase5c_candidates(record: dict[str, Any]) -> pd.DataFrame:
    """Rehydrate saved Phase-5C candidate evidence for readiness display only."""
    rows = []
    for item in record.get("evidence_matrix", []) if isinstance(record, dict) else []:
        if not isinstance(item, dict):
            continue
        origin = str(item.get("Data Origin") or "")
        status = str(item.get("Status") or "")
        if "Chapter 5 Research Assistant Phase 5C" not in origin or status != "Candidate — Analyst verify":
            continue
        note = str(item.get("Analyst Note") or "")
        explicitness = note.split(" | Source method:", 1)[0].strip()
        source_method = note.split(" | Source method:", 1)[1].strip() if " | Source method:" in note else "Saved Phase 5C candidate"
        rows.append({
            "Question": str(item.get("Question") or ""),
            "Subtopic": str(item.get("Claim") or "").split(" — ", 1)[0],
            "Direction": str(item.get("Direction") or "Neutral — Candidate"),
            "Evidence Quality": str(item.get("Evidence Type") or ""),
            "Explicitness": explicitness,
            "Title": str(item.get("Source Title") or ""),
            "URL": str(item.get("Source URL / File") or ""),
            "Snippet": str(item.get("Evidence Text") or ""),
            "Source Group": "",
            "Query": "",
            "Focus": "",
            "Source Method": source_method,
        })
    return pd.DataFrame(rows)


def _wrapped_html_table(df: pd.DataFrame, max_height_px: int = 430) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return "<div style='color:#64748b;font-size:0.92rem'>Không có dữ liệu.</div>"
    show = df.copy().where(pd.notna(df), "—")
    html = show.to_html(index=False, escape=True, border=0)
    return f"""
    <div style="max-height:{int(max_height_px)}px;overflow:auto;border:1px solid #e2e8f0;border-radius:10px">
      <style>
        .ch5d-table table {{width:100%;border-collapse:collapse;table-layout:fixed;font-size:0.88rem;}}
        .ch5d-table th {{position:sticky;top:0;background:#f8fafc;z-index:1;text-align:left;padding:8px;border-bottom:1px solid #cbd5e1;white-space:normal;overflow-wrap:anywhere;}}
        .ch5d-table td {{vertical-align:top;padding:8px;border-bottom:1px solid #e2e8f0;white-space:normal;overflow-wrap:anywhere;word-break:break-word;}}
        .ch5d-table tr:last-child td {{border-bottom:0;}}
      </style>
      <div class="ch5d-table">{html}</div>
    </div>
    """


def render_phase5d_lock_panel(ticker: str, company_name: str = "") -> None:
    safe = _safe_ticker(ticker) or "DGC"
    record = load_record(safe, company_name)
    quant_ctx, quant_error = load_chapter5_quant(safe, record)
    candidates = st.session_state.get(f"ch5c_result_{safe}")
    if not isinstance(candidates, pd.DataFrame):
        candidates = _saved_phase5c_candidates(record)

    chapter4_record = None
    try:
        from modules.deep_company_analysis.chapter4 import load_record as load_chapter4_record
        chapter4_record = load_chapter4_record(safe)
    except Exception:
        chapter4_record = None

    report = evaluate_chapter5_lock(record, quant_ctx, candidates, chapter4_record)

    with st.container(border=True):
        st.markdown("### 🔒 Phase 5D — Chapter 5 End-to-End Lock & QA")
        st.caption(
            "Implementation Lock kiểm tra kiến trúc Q21–Q26, Single Source of Truth, no-fabrication và analyst ownership. "
            "PASS không phải điểm chất lượng doanh nghiệp, không phải Research Gate và không phải BUY/HOLD/SELL."
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Implementation Lock", report.implementation_status)
        ready_count = int(report.research_readiness["Readiness"].astype(str).str.startswith("Research-ready").sum()) if not report.research_readiness.empty else 0
        c2.metric("Research-ready Q", f"{ready_count}/6")
        c3.metric("Cross-question diagnostics", len(report.cross_question_diagnostics))

        if report.passed:
            st.success(report.note)
        else:
            st.error(report.note)

        st.markdown("**Implementation Lock Checks — hard methodology/architecture checks**")
        lock_table = report.implementation_checks.copy()
        lock_table["PASS"] = lock_table["PASS"].map(lambda x: "PASS" if bool(x) else "FAIL")
        st.html(_wrapped_html_table(lock_table, 420))

        st.markdown("**Ticker Research Readiness — không phải investment-quality score**")
        st.html(_wrapped_html_table(report.research_readiness, 360))
        if quant_ctx is None and quant_error:
            st.warning(f"Canonical readiness: {quant_error}")

        no_counter = report.research_readiness["Counter-Evidence Candidates"].eq(0) if not report.research_readiness.empty else pd.Series(dtype=bool)
        if len(no_counter) and bool(no_counter.any()):
            questions = ", ".join(report.research_readiness.loc[no_counter, "Question"].astype(str).tolist())
            st.info(
                f"Chưa tìm thấy Counter-Evidence Candidate cho: {questions}. Điều này KHÔNG có nghĩa là an toàn/tốt; "
                "chỉ có nghĩa hệ thống chưa thu được counter-evidence trong tập nguồn hiện tại."
            )

        if report.cross_question_diagnostics:
            with st.expander("⚠️ Cross-question diagnostics Ch4 ↔ Ch5", expanded=True):
                for item in report.cross_question_diagnostics:
                    st.warning(item)
                st.caption("Diagnostic chỉ yêu cầu analyst review; không tự thay assessment ở Chương 4 hoặc Chương 5.")

        with st.expander("🛡️ Phase 5D lock semantics & guardrails", expanded=False):
            st.write(phase5d_guardrails())
            st.caption(
                "Implementation PASS chỉ khóa methodology/guardrails. Research Readiness chỉ cho biết dữ liệu/evidence có đủ để analyst tiếp tục hay chưa. "
                "Không có cơ chế auto-conclusion từ số lượng evidence, canonical ratios hoặc ROIC."
            )
'''
    text = text.replace(marker, block + marker, 1)

old_tab = '''def render_chapter5_tab(default_ticker: str) -> None:\n    safe, company_name = render_phase5b_quantitative_bridge(default_ticker)\n    render_phase5c_research_assistant(safe, company_name)\n    render_chapter5(default_ticker=safe, company_name=company_name)'''
new_tab = '''def render_chapter5_tab(default_ticker: str) -> None:\n    safe, company_name = render_phase5b_quantitative_bridge(default_ticker)\n    render_phase5c_research_assistant(safe, company_name)\n    render_phase5d_lock_panel(safe, company_name)\n    render_chapter5(default_ticker=safe, company_name=company_name)'''
if old_tab in text:
    text = text.replace(old_tab, new_tab, 1)
elif new_tab not in text:
    raise SystemExit("chapter5_page_support.py: Phase 5D tab-body marker not found")

SUPPORT.write_text(text, encoding="utf-8")
print("Applied Chapter 5 Phase 5D Lock & QA UI integration")
