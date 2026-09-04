from __future__ import annotations

"""Idempotently integrate Phase 4C.3 into the unified Chapter-4 page."""

from pathlib import Path


PATH = Path("modules/deep_company_analysis/chapter4_page_support.py")
text = PATH.read_text(encoding="utf-8")

import_anchor = '''from modules.deep_company_analysis.chapter4_evidence_c2 import (\n    Phase4C2Engine,\n    c2_quality_summary,\n    merge_c2_candidates_into_evidence_matrix,\n)'''
import_replacement = '''from modules.deep_company_analysis.chapter4_evidence_c2 import (\n    Phase4C2Engine,\n    c2_quality_summary,\n    merge_c2_candidates_into_evidence_matrix,\n)\nfrom modules.deep_company_analysis.chapter4_evidence_c3 import (\n    Phase4C3Engine,\n    merge_c3_candidates_into_evidence_matrix,\n)'''
if import_replacement not in text:
    if import_anchor not in text:
        raise SystemExit("Phase 4C.2 import anchor not found")
    text = text.replace(import_anchor, import_replacement, 1)

function_anchor = '''\ndef _fmt(value: Any, suffix: str = "") -> str:\n'''
new_function = r'''

def render_phase4c3_close_gaps(ticker: str, company_name: str, industry_group: str) -> None:
    """Close Q16/Q19 evidence gaps with multi-source corroboration and full Shearn coverage audit."""
    safe = _safe_ticker(ticker)
    discovery = _auto_peer_discovery(safe)
    peer_df = discovery.get("peers")
    if not isinstance(peer_df, pd.DataFrame):
        peer_df = pd.DataFrame()

    with st.container(border=True):
        st.markdown("### 🧭 Phase 4C.3 — Q16 Corroboration + Q19 Full Shearn Coverage")
        st.caption(
            "Phase này sửa giới hạn first-match của Q19, audit đủ 8 nhóm logic cạnh tranh đang dùng trong workspace, "
            "và yêu cầu Q16 có corroboration đa nguồn theo kỳ. Coverage chỉ nói rằng có evidence để đọc; không phải kết luận "
            "Pricing Power hay Competition Intensity."
        )

        if st.button("🧭 Đóng gap Q16 + Q19 theo Shearn", use_container_width=True, key=f"ch4c3_close_{safe}"):
            pricing0 = st.session_state.get(f"ch4c2_pricing_{safe}")
            universe0 = st.session_state.get(f"ch4c2_universe_{safe}")
            q190 = st.session_state.get(f"ch4c2_q19_{safe}")
            baseline = None
            if isinstance(pricing0, pd.DataFrame) or isinstance(q190, pd.DataFrame):
                from modules.deep_company_analysis.chapter4_evidence_c2 import Phase4C2Result
                baseline = Phase4C2Result(
                    pricing_candidates=pricing0 if isinstance(pricing0, pd.DataFrame) else pd.DataFrame(),
                    competitor_universe=universe0 if isinstance(universe0, pd.DataFrame) else pd.DataFrame(),
                    competitor_evidence=q190 if isinstance(q190, pd.DataFrame) else pd.DataFrame(),
                    combined_candidates=pd.DataFrame(),
                    note="Reuse Phase 4C.2 session candidates",
                    audit={},
                )
            with st.spinner(f"Đang triangulate Q16 và đóng các Q19 evidence gap còn lại cho {safe}..."):
                result = Phase4C3Engine(m1.RAW_DIR).search(
                    safe,
                    company_name,
                    industry_group or str(discovery.get("industry_group") or ""),
                    peer_df,
                    baseline=baseline,
                )
                latest = load_record(safe, company_name)
                latest = merge_c3_candidates_into_evidence_matrix(latest, result.combined_candidates)
                save_record(latest, create_snapshot=False)
                st.session_state[f"ch4c3_pricing_{safe}"] = result.pricing_candidates
                st.session_state[f"ch4c3_corroboration_{safe}"] = result.pricing_corroboration
                st.session_state[f"ch4c3_q19_{safe}"] = result.q19_evidence
                st.session_state[f"ch4c3_coverage_{safe}"] = result.q19_coverage
                st.session_state[f"ch4c3_gaps_{safe}"] = result.gaps
                st.session_state[f"ch4c3_note_{safe}"] = result.note
            st.success(result.note)

        corroboration = st.session_state.get(f"ch4c3_corroboration_{safe}")
        coverage = st.session_state.get(f"ch4c3_coverage_{safe}")
        pricing = st.session_state.get(f"ch4c3_pricing_{safe}")
        q19 = st.session_state.get(f"ch4c3_q19_{safe}")
        gaps = st.session_state.get(f"ch4c3_gaps_{safe}")

        if isinstance(corroboration, pd.DataFrame):
            st.markdown("**Q16 — Multi-source Corroboration Audit**")
            if corroboration.empty:
                st.warning("Chưa có explicit price + customer/volume evidence đủ để triangulate. Q16 vẫn là Research Gap nếu analyst chưa có nguồn riêng.")
            else:
                st.dataframe(corroboration, use_container_width=True, hide_index=True)
                st.caption(
                    "Period-level corroboration chỉ xác nhận có ≥2 nguồn/domain trong cùng kỳ và có independent evidence. "
                    "Analyst vẫn phải mở nguồn để xác minh chúng đang nói về cùng pricing event và loại trừ commodity/cost pass-through."
                )

        if isinstance(coverage, pd.DataFrame):
            st.markdown("**Q19 — Full Shearn Coverage Matrix**")
            st.dataframe(coverage, use_container_width=True, hide_index=True, height=330)
            covered = int(coverage["Candidates"].fillna(0).astype(int).gt(0).sum()) if "Candidates" in coverage.columns else 0
            if covered < len(coverage):
                st.warning(f"Q19 mới có evidence candidate ở {covered}/{len(coverage)} nhóm. Các dòng Gap phải tiếp tục để mở.")
            else:
                st.info("8/8 nhóm đều có candidate evidence. Điều này chưa đồng nghĩa competitive landscape đã được Analyst kết luận.")

        if isinstance(gaps, list) and gaps:
            with st.expander(f"⚠ Phase 4C.3 Research Gaps còn mở ({len(gaps)})", expanded=True):
                for gap in gaps:
                    st.write(f"- {gap}")
        elif isinstance(gaps, list):
            st.success("Không còn coverage gap máy có thể nhận diện ở Q16/Q19; vẫn cần Analyst verify từng evidence trước khi khóa Chương 4.")

        if isinstance(pricing, pd.DataFrame) and not pricing.empty:
            with st.expander(f"Q16 — Candidate evidence sau triangulation ({len(pricing)})", expanded=False):
                cols = [c for c in [
                    "Period Candidate", "Explicitness", "Event Type Candidate", "Evidence Quality",
                    "Source Method", "Title", "URL", "Snippet"
                ] if c in pricing.columns]
                st.dataframe(pricing[cols].head(80), use_container_width=True, hide_index=True, height=340)

        if isinstance(q19, pd.DataFrame) and not q19.empty:
            with st.expander(f"Q19 — Multi-label evidence ({len(q19)})", expanded=False):
                cols = [c for c in [
                    "Subtopic", "Direction", "Evidence Quality", "Period Candidate", "Source Method",
                    "Title", "URL", "Snippet"
                ] if c in q19.columns]
                st.dataframe(q19[cols].head(140), use_container_width=True, hide_index=True, height=420)

        st.warning(
            "Guardrail Phase 4C.3: coverage ≠ conclusion; period-level corroboration ≠ event-level proof; cùng ngành ≠ direct competitor; "
            "Research Assistant không được tự chọn Pricing Power, Competition Intensity, Ideal Company, Research Gate hay BUY/HOLD/SELL."
        )
'''
if "def render_phase4c3_close_gaps(" not in text:
    if function_anchor not in text:
        raise SystemExit("_fmt anchor not found")
    text = text.replace(function_anchor, new_function + function_anchor, 1)

old_call = '''    render_phase4c_evidence_bridge(safe, company_name, industry_group)\n    render_phase4c2_gap_engine(safe, company_name, industry_group)\n    render_chapter4(default_ticker=safe, company_name=company_name)'''
new_call = '''    render_phase4c_evidence_bridge(safe, company_name, industry_group)\n    render_phase4c2_gap_engine(safe, company_name, industry_group)\n    render_phase4c3_close_gaps(safe, company_name, industry_group)\n    render_chapter4(default_ticker=safe, company_name=company_name)'''
if new_call not in text:
    if old_call not in text:
        raise SystemExit("render_chapter4_tab call anchor not found")
    text = text.replace(old_call, new_call, 1)

PATH.write_text(text, encoding="utf-8")
print("Phase 4C.3 UI patch applied")
