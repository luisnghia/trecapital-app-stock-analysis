from __future__ import annotations

"""Idempotently wire Phase 4C.2 Q16/Q19 gap engines into the Chapter 4 unified page."""

from pathlib import Path


PATH = Path("modules/deep_company_analysis/chapter4_page_support.py")
text = PATH.read_text(encoding="utf-8")

import_block = '''from modules.deep_company_analysis.chapter4_evidence_c2 import (
    Phase4C2Engine,
    c2_quality_summary,
    merge_c2_candidates_into_evidence_matrix,
)
'''
marker = '''from modules.deep_company_analysis.chapter4_evidence import (
    Chapter4EvidenceAgent,
    candidate_coverage,
    evidence_quality_summary,
    merge_candidates_into_evidence_matrix,
    research_gaps,
)
'''
if import_block not in text:
    if marker not in text:
        raise SystemExit("Chapter 4 evidence import marker not found")
    text = text.replace(marker, marker + import_block, 1)

function_block = r'''

def render_phase4c2_gap_engine(ticker: str, company_name: str, industry_group: str) -> None:
    """Deepen the two material Phase 4C.1 gaps without auto-judgement."""
    safe = _safe_ticker(ticker)
    discovery = _auto_peer_discovery(safe)
    peer_df = discovery.get("peers")
    if not isinstance(peer_df, pd.DataFrame):
        peer_df = pd.DataFrame()

    record = load_record(safe, company_name)
    evidence_rows = record.get("evidence_matrix") if isinstance(record, dict) else []
    existing = pd.DataFrame(evidence_rows) if isinstance(evidence_rows, list) and evidence_rows else pd.DataFrame()
    if not existing.empty and "Data Origin" in existing.columns:
        existing = existing[existing["Data Origin"].astype(str).str.contains("Phase 4C.2", na=False)].copy()
    else:
        existing = pd.DataFrame()

    with st.container(border=True):
        st.markdown("### 🎯 Phase 4C.2 — Q16 Pricing Power + Q19 Competitor Intelligence")
        st.caption(
            "Q16 chỉ tìm explicit price evidence và phản ứng volume/customer/retention; Q19 dùng peer universe cùng ngành làm context rồi tìm "
            "evidence về direct competition, cách cạnh tranh, intensity, substitutes, low-cost countries và competitor failures. "
            "Peer cùng ngành chưa tự động là đối thủ trực tiếp; mọi kết luận vẫn thuộc Analyst."
        )

        if not existing.empty and "Question" in existing.columns:
            counts = existing["Question"].value_counts().to_dict()
            c1, c2, c3 = st.columns(3)
            c1.metric("Q16 evidence đã lưu", int(counts.get("Q16", 0)))
            c2.metric("Q19 evidence đã lưu", int(counts.get("Q19", 0)))
            c3.metric("Tổng Phase 4C.2", len(existing))
        else:
            st.info("Chưa có evidence Phase 4C.2 được lưu cho mã này.")

        if st.button("🎯 Đào sâu Q16 + Q19", use_container_width=True, key=f"ch4c2_deepen_{safe}"):
            with st.spinner(f"Đang đào sâu Pricing Power và Competitor Intelligence cho {safe}..."):
                result = Phase4C2Engine(m1.RAW_DIR).search(
                    safe,
                    company_name,
                    industry_group or str(discovery.get("industry_group") or ""),
                    peer_df,
                )
                latest = load_record(safe, company_name)
                latest = merge_c2_candidates_into_evidence_matrix(latest, result.combined_candidates)
                save_record(latest, create_snapshot=False)
                st.session_state[f"ch4c2_pricing_{safe}"] = result.pricing_candidates
                st.session_state[f"ch4c2_universe_{safe}"] = result.competitor_universe
                st.session_state[f"ch4c2_q19_{safe}"] = result.competitor_evidence
                st.session_state[f"ch4c2_note_{safe}"] = result.note
            st.success(result.note)

        pricing = st.session_state.get(f"ch4c2_pricing_{safe}")
        universe = st.session_state.get(f"ch4c2_universe_{safe}")
        q19 = st.session_state.get(f"ch4c2_q19_{safe}")

        if isinstance(pricing, pd.DataFrame) or isinstance(q19, pd.DataFrame):
            from modules.deep_company_analysis.chapter4_evidence_c2 import Phase4C2Result

            summary_result = Phase4C2Result(
                pricing_candidates=pricing if isinstance(pricing, pd.DataFrame) else pd.DataFrame(),
                competitor_universe=universe if isinstance(universe, pd.DataFrame) else pd.DataFrame(),
                competitor_evidence=q19 if isinstance(q19, pd.DataFrame) else pd.DataFrame(),
                combined_candidates=pd.DataFrame(),
                note=str(st.session_state.get(f"ch4c2_note_{safe}") or ""),
                audit={},
            )
            summary = c2_quality_summary(summary_result)
            st.markdown("**Phase 4C.2 Gap Audit**")
            st.dataframe(summary, use_container_width=True, hide_index=True)

        if isinstance(pricing, pd.DataFrame):
            with st.expander(f"Q16 — Pricing evidence ({len(pricing)})", expanded=True):
                if pricing.empty:
                    st.warning("Chưa tìm được explicit pricing evidence; Q16 phải giữ Unknown/Research Gap nếu analyst chưa có nguồn khác.")
                else:
                    cols = [c for c in [
                        "Period Candidate", "Explicitness", "Event Type Candidate", "Evidence Quality",
                        "Source Method", "Title", "URL", "Snippet"
                    ] if c in pricing.columns]
                    st.dataframe(pricing[cols].head(60), use_container_width=True, hide_index=True, height=330)
                    explicit = int(pricing["Explicitness"].astype(str).str.startswith("Explicit price + customer/volume").sum()) if "Explicitness" in pricing.columns else 0
                    if explicit == 0:
                        st.warning("Có nhắc giá nhưng chưa có bằng chứng đủ mạnh về phản ứng volume/customer. Không được kết luận Pricing Power.")
                    else:
                        st.info(f"Có {explicit} candidate chứa price + customer/volume response. Analyst vẫn phải phân biệt true Pricing Power với cost pass-through/commodity pricing.")

        if isinstance(universe, pd.DataFrame):
            with st.expander(f"Q19 — Same-industry competitor candidate universe ({len(universe)})", expanded=False):
                if universe.empty:
                    st.caption("Chưa có peer universe cùng ngành.")
                else:
                    st.dataframe(universe, use_container_width=True, hide_index=True, height=min(370, 75 + 27 * len(universe)))
                st.caption("Danh sách này là candidate context từ cùng ngành. Analyst phải xác nhận competitor overlap; app không tự gọi toàn bộ peer là đối thủ trực tiếp.")

        if isinstance(q19, pd.DataFrame):
            with st.expander(f"Q19 — Competitor intelligence evidence ({len(q19)})", expanded=True):
                if q19.empty:
                    st.warning("Chưa có competitor evidence đủ điều kiện; giữ Research Gap thay vì suy diễn từ peer universe.")
                else:
                    cols = [c for c in [
                        "Subtopic", "Direction", "Evidence Quality", "Period Candidate", "Source Method",
                        "Title", "URL", "Snippet"
                    ] if c in q19.columns]
                    st.dataframe(q19[cols].head(80), use_container_width=True, hide_index=True, height=380)
                    covered = int(q19["Subtopic"].nunique()) if "Subtopic" in q19.columns else 0
                    if covered < 4:
                        st.warning(f"Q19 mới có evidence ở {covered}/8 nhóm logic; chưa nên coi competitive landscape đã hiểu đầy đủ.")
                    else:
                        st.info(f"Q19 có evidence ở {covered}/8 nhóm logic. Các nhóm chưa có vẫn là Research Gap.")

        st.warning(
            "Guardrail: price-only, margin-only hoặc commodity-price evidence không được tự biến thành Pricing Power; "
            "same-industry peer không được tự biến thành direct competitor; Research Assistant không được chọn Competition Intensity/Ideal Company hay đổi Research Gate."
        )
'''

if "def render_phase4c2_gap_engine(" not in text:
    fmt_marker = "\n\ndef _fmt(value: Any, suffix: str = \"\") -> str:\n"
    if fmt_marker not in text:
        raise SystemExit("_fmt marker not found")
    text = text.replace(fmt_marker, function_block + fmt_marker, 1)

old_call = '''def render_chapter4_tab(default_ticker: str) -> None:
    safe, company_name, industry_group = render_quantitative_bridge(default_ticker)
    render_phase4c_evidence_bridge(safe, company_name, industry_group)
    render_chapter4(default_ticker=safe, company_name=company_name)
'''
new_call = '''def render_chapter4_tab(default_ticker: str) -> None:
    safe, company_name, industry_group = render_quantitative_bridge(default_ticker)
    render_phase4c_evidence_bridge(safe, company_name, industry_group)
    render_phase4c2_gap_engine(safe, company_name, industry_group)
    render_chapter4(default_ticker=safe, company_name=company_name)
'''
if old_call in text:
    text = text.replace(old_call, new_call, 1)
elif new_call not in text:
    raise SystemExit("render_chapter4_tab marker not found")

PATH.write_text(text, encoding="utf-8")
print("Phase 4C.2 UI patch applied")
