from __future__ import annotations

"""Idempotently wire Phase 4C.1 evidence-quality diagnostics into the Chapter 4 UI."""

from pathlib import Path


PATH = Path("modules/deep_company_analysis/chapter4_page_support.py")
text = PATH.read_text(encoding="utf-8")

old_import = '''from modules.deep_company_analysis.chapter4_evidence import (\n    Chapter4EvidenceAgent,\n    candidate_coverage,\n    merge_candidates_into_evidence_matrix,\n)'''
new_import = '''from modules.deep_company_analysis.chapter4_evidence import (\n    Chapter4EvidenceAgent,\n    candidate_coverage,\n    evidence_quality_summary,\n    merge_candidates_into_evidence_matrix,\n    research_gaps,\n)'''
if old_import in text:
    text = text.replace(old_import, new_import, 1)
elif new_import not in text:
    raise SystemExit("Phase 4C evidence import block not found")

text = text.replace(
    'st.markdown("### 🔎 Phase 4C — Research Assistant Evidence Bridge")',
    'st.markdown("### 🔎 Phase 4C.1 — Research Assistant Evidence Quality Bridge")',
)
text = text.replace(
    '"Research Assistant tìm supporting evidence + counter-evidence cho Q15–Q20 và tự đưa vào Evidence Matrix dưới trạng thái Candidate. "\n            "Nó không được đổi Assessment, Trend, Confidence, Conclusion hay Research Gate."',
    '"Research Assistant ưu tiên nguồn gốc: IR/BCTN/BCTC chính thức → independent sources → search snippets; "\n            "sau đó tìm supporting + counter-evidence cho Q15–Q20 và đưa vào Evidence Matrix dưới trạng thái Candidate. "\n            "Nó không được đổi Assessment, Trend, Confidence, Conclusion hay Research Gate."',
)
text = text.replace(
    'if st.button("🌐 Cập nhật Evidence Q15–Q20", use_container_width=True, key=f"ch4c_refresh_evidence_{safe}"):',
    'if st.button("🌐 Cập nhật Evidence chất lượng Q15–Q20", use_container_width=True, key=f"ch4c_refresh_evidence_{safe}"):')

old_ui = '''            coverage = candidate_coverage(candidates)\n            st.caption("Candidate coverage mới nhất: " + " | ".join(f"{q}: {coverage[q]}" for q in coverage))\n            show_cols = [c for c in ["Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness", "Title", "URL", "Snippet"] if c in candidates.columns]\n            st.dataframe(candidates[show_cols].head(80), use_container_width=True, hide_index=True, height=360)\n            st.warning("Direction và Explicitness đều là Research Assistant candidate. Analyst phải mở nguồn và xác minh trước khi dùng làm kết luận.")'''
new_ui = '''            coverage = candidate_coverage(candidates)\n            st.caption("Candidate coverage mới nhất: " + " | ".join(f"{q}: {coverage[q]}" for q in coverage))\n\n            quality = evidence_quality_summary(candidates)\n            if not quality.empty:\n                st.markdown("**Evidence Quality / Coverage Audit**")\n                st.dataframe(quality, use_container_width=True, hide_index=True, height=250)\n\n            gaps = research_gaps(candidates)\n            if gaps:\n                with st.expander(f"⚠ Research gaps còn mở ({len(gaps)})", expanded=True):\n                    for gap in gaps:\n                        st.write(f"- {gap}")\n            else:\n                st.success("Không còn coverage gap định lượng theo Phase 4C.1; analyst vẫn phải xác minh từng candidate trước khi kết luận.")\n\n            show_cols = [c for c in ["Question", "Subtopic", "Direction", "Evidence Quality", "Source Method", "Explicitness", "Title", "URL", "Snippet"] if c in candidates.columns]\n            st.dataframe(candidates[show_cols].head(100), use_container_width=True, hide_index=True, height=420)\n            st.warning("Nguồn A/B, Direction và Explicitness đều chỉ là Research Assistant classification. Analyst phải mở nguồn gốc và xác minh trước khi dùng làm kết luận.")'''
if old_ui in text:
    text = text.replace(old_ui, new_ui, 1)
elif new_ui not in text:
    raise SystemExit("Phase 4C candidate UI block not found")

PATH.write_text(text, encoding="utf-8")
print("Phase 4C.1 UI patch applied")
