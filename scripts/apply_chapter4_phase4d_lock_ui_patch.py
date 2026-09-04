from __future__ import annotations

"""Idempotently integrate the Phase 4D final-lock panel into Chapter 4 unified page."""

from pathlib import Path

PATH = Path("modules/deep_company_analysis/chapter4_page_support.py")
text = PATH.read_text(encoding="utf-8")

import_marker = """from modules.deep_company_analysis.chapter4_evidence_c3 import (\n    Phase4C3Engine,\n    merge_c3_candidates_into_evidence_matrix,\n)\n"""
lock_import = """from modules.deep_company_analysis.chapter4_lock import (\n    LOCK_VERSION,\n    build_lock_audit,\n    finalize_record_for_lock,\n)\n"""
if lock_import not in text:
    if import_marker not in text:
        raise SystemExit("Phase 4C.3 import marker not found")
    text = text.replace(import_marker, import_marker + lock_import, 1)

fn_marker = "\ndef _fmt(value: Any, suffix: str = \"\") -> str:\n"
lock_fn = r'''

def render_phase4d_final_lock(ticker: str, company_name: str, industry_group: str) -> None:
    """Run final evidence hygiene/guardrail acceptance and persist Chapter-4 lock metadata."""
    safe = _safe_ticker(ticker)
    record = load_record(safe, company_name)
    lock_meta = record.get("chapter4_lock") if isinstance(record, dict) else {}
    lock_meta = lock_meta if isinstance(lock_meta, dict) else {}

    with st.container(border=True):
        st.markdown("### 🔒 Phase 4D — Final Acceptance & Chapter 4 Lock")
        st.caption(
            "LOCKED nghĩa là kiến trúc Q15–Q20, persistence, provenance, evidence hygiene và guardrails đã vượt final acceptance. "
            "Nó không có nghĩa mọi mã đã đủ evidence hoặc đã có kết luận đầu tư. Research Gap riêng của từng doanh nghiệp vẫn được giữ hiển thị."
        )
        if lock_meta.get("status") == "LOCKED":
            st.success(f"{LOCK_VERSION} | {lock_meta.get('locked_at') or 'đã khóa'}")
            gaps0 = lock_meta.get("open_research_gaps")
            if isinstance(gaps0, list) and gaps0:
                st.caption(f"Có {len(gaps0)} stock-specific Research Gap vẫn mở; đây không phải lỗi implementation.")

        if st.button("🔒 Chạy Final Acceptance & khóa Chương 4", use_container_width=True, key=f"ch4d_lock_{safe}"):
            discovery = _auto_peer_discovery(safe)
            peer_df = discovery.get("peers")
            if not isinstance(peer_df, pd.DataFrame):
                peer_df = pd.DataFrame()
            industry = industry_group or str(discovery.get("industry_group") or "")
            with st.spinner(f"Đang chạy final acceptance Chương 4 cho {safe}..."):
                result = Phase4C3Engine(m1.RAW_DIR).search(safe, company_name, industry, peer_df)
                audit = build_lock_audit(result, safe, company_name, industry)
                latest = load_record(safe, company_name)
                latest = merge_c3_candidates_into_evidence_matrix(latest, audit.retained_candidates)
                latest = finalize_record_for_lock(latest, audit)
                save_record(latest, create_snapshot=bool(audit.lock_ready))
                st.session_state[f"ch4d_audit_{safe}"] = audit
            if audit.lock_ready:
                st.success("CHAPTER 4 LOCK ACCEPTANCE: PASS — Chương 4 đã được khóa ở mức implementation/guardrail.")
            else:
                st.error("Chapter 4 chưa đủ điều kiện khóa. Xem các acceptance check FAIL bên dưới.")

        audit = st.session_state.get(f"ch4d_audit_{safe}")
        if audit is not None:
            st.markdown("**Final Acceptance Checks**")
            st.dataframe(audit.checks, use_container_width=True, hide_index=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Evidence giữ lại", len(audit.retained_candidates))
            c2.metric("Noise quarantine", len(audit.quarantined_candidates))
            covered = int(audit.q19_coverage["Candidates"].fillna(0).astype(int).gt(0).sum()) if not audit.q19_coverage.empty else 0
            c3.metric("Q19 A/B coverage", f"{covered}/8")

            if not audit.quarantined_candidates.empty:
                with st.expander(f"🧹 Evidence bị quarantine ({len(audit.quarantined_candidates)})", expanded=False):
                    cols = [c for c in ["Quarantine Reason", "Evidence Quality", "Title", "URL", "Snippet"] if c in audit.quarantined_candidates.columns]
                    st.dataframe(audit.quarantined_candidates[cols].head(60), use_container_width=True, hide_index=True, height=300)
                    st.caption("Quarantine không xóa dữ liệu; row được giữ để audit nhưng không được dùng đóng evidence coverage.")

            st.markdown("**Q19 A/B Lock Coverage**")
            st.dataframe(audit.q19_coverage, use_container_width=True, hide_index=True, height=330)

            if audit.research_gaps:
                with st.expander(f"📌 Stock-specific Research Gaps vẫn mở ({len(audit.research_gaps)})", expanded=True):
                    for gap in audit.research_gaps:
                        st.write(f"- {gap}")
            else:
                st.success("Không còn stock-specific Q19 coverage gap trong lần audit này.")

            if audit.failure_candidates.empty:
                st.info("Why Competitors Failed chưa có legitimate A/B evidence đủ mạnh: giữ Research Gap, không suy diễn nguyên nhân thất bại.")
            else:
                st.caption(f"Có {len(audit.failure_candidates)} legitimate competitor-failure candidate(s); Analyst vẫn phải verify root cause.")

            st.warning(
                "Final guardrail: Chapter 4 LOCK không tự đổi Moat, Pricing Power, Good/Bad Industry, Competition Intensity, Supplier Quality, "
                "Ideal Company, Research Gate hay BUY/HOLD/SELL."
            )
'''
if "def render_phase4d_final_lock(" not in text:
    if fn_marker not in text:
        raise SystemExit("_fmt marker not found")
    text = text.replace(fn_marker, lock_fn + fn_marker, 1)

old_footer = """    render_phase4c3_close_gaps(safe, company_name, industry_group)\n    render_chapter4(default_ticker=safe, company_name=company_name)\n"""
new_footer = """    render_phase4c3_close_gaps(safe, company_name, industry_group)\n    render_phase4d_final_lock(safe, company_name, industry_group)\n    render_chapter4(default_ticker=safe, company_name=company_name)\n"""
if new_footer not in text:
    if old_footer not in text:
        raise SystemExit("render_chapter4_tab footer marker not found")
    text = text.replace(old_footer, new_footer, 1)

PATH.write_text(text, encoding="utf-8")
print("Phase 4D lock UI patch applied")
