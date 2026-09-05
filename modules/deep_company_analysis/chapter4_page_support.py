from __future__ import annotations

"""Unified-page support for Chapter 4 Phase 4B quantitative bridge."""

from typing import Any

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.table_format import render_static_table

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter2_page_support import _active_paths, _path_signature
from modules.deep_company_analysis.chapter4 import INDUSTRY_PEER_COLUMNS, load_record, render_chapter4, save_record
from modules.deep_company_analysis.chapter4_quant import (
    build_company_snapshot,
    build_industry_distribution,
    build_peer_benchmark,
    build_peer_table,
    pricing_context,
    supply_chain_context,
)
from modules.deep_company_analysis.chapter4_peer_auto import (
    DEFAULT_MAX_PEERS,
    discover_same_industry_peers,
    peer_refresh_plan,
    refresh_peer_canonical_bundle,
    refresh_peer_canonical_universe,
)
from modules.deep_company_analysis.chapter4_peer_selection import (
    PEER_SELECTION_COLUMNS,
    build_peer_selection_table,
    normalize_ticker_list,
    selected_peer_tickers,
)
from modules.deep_company_analysis.chapter4_evidence import (
    Chapter4EvidenceAgent,
    candidate_coverage,
    evidence_quality_summary,
    merge_candidates_into_evidence_matrix,
    research_gaps,
)
from modules.deep_company_analysis.chapter4_evidence_c2 import (
    Phase4C2Engine,
    c2_quality_summary,
    merge_c2_candidates_into_evidence_matrix,
)
from modules.deep_company_analysis.chapter4_evidence_c3 import (
    Phase4C3Engine,
    merge_c3_candidates_into_evidence_matrix,
)
from modules.deep_company_analysis.chapter4_lock import (
    LOCK_VERSION,
    build_lock_audit,
    finalize_record_for_lock,
)


def _safe_ticker(value: str) -> str:
    try:
        return m1._safe_ticker(value)
    except Exception:
        return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


@st.cache_data(ttl=120, show_spinner=False)
def _snapshot_cached(
    ticker: str,
    overview_path: str,
    year_path: str,
    quarter_path: str,
    overview_sig: tuple[int, int],
    year_sig: tuple[int, int],
    quarter_sig: tuple[int, int],
    source_label: str,
):
    del overview_sig, year_sig, quarter_sig
    safe = _safe_ticker(ticker)
    company = m1._load_overview_cached(overview_path, safe)
    annual_raw = m1._load_timeseries_cached(year_path, safe, "Y", 11)
    quarterly = m1._load_timeseries_cached(quarter_path, safe, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    return build_company_snapshot(safe, company_name, annual, source_label=source_label)


def load_quant_snapshot(ticker: str):
    safe = _safe_ticker(ticker)
    paths, source_label = _active_paths(safe)
    if not paths:
        return None, f"{safe}: chưa có canonical statement cache trên máy."
    overview, year, quarter = paths
    try:
        snapshot = _snapshot_cached(
            safe,
            str(overview),
            str(year),
            str(quarter),
            _path_signature(overview),
            _path_signature(year),
            _path_signature(quarter),
            source_label,
        )
        return snapshot or None, "" if snapshot else f"{safe}: canonical bundle chưa có dữ liệu usable."
    except Exception as exc:
        return None, f"{safe}: không dựng được quantitative snapshot: {exc}"


def _parse_peer_tickers(value: Any, target: str) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        text = str(value or "").replace(";", ",").replace("\n", ",")
        raw = [part.strip() for part in text.split(",")]
    out: list[str] = []
    for item in [target, *raw]:
        safe = _safe_ticker(str(item))
        if len(safe) >= 3 and safe not in out:
            out.append(safe)
        if len(out) >= 12:
            break
    return out


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def _industry_discovery_cached(ticker: str, raw_dir: str, max_peers: int = DEFAULT_MAX_PEERS):
    discovery = discover_same_industry_peers(ticker, raw_dir, max_peers=max_peers)
    return {
        "target": discovery.target,
        "industry_group": discovery.industry_group,
        "peers": discovery.peers,
        "tickers": discovery.tickers,
        "note": discovery.note,
        "raw_path": discovery.raw_path,
        "truncated": discovery.truncated,
    }


def _auto_peer_discovery(ticker: str):
    safe = _safe_ticker(ticker)
    try:
        return _industry_discovery_cached(safe, str(m1.RAW_DIR), DEFAULT_MAX_PEERS)
    except Exception as exc:
        return {"target": safe, "industry_group": "", "peers": pd.DataFrame(), "tickers": [safe], "note": f"Không lấy được danh sách cùng ngành: {exc}", "raw_path": "", "truncated": False}


def _phase4c_existing_rows(record: dict[str, Any]) -> pd.DataFrame:
    rows = record.get("evidence_matrix") if isinstance(record, dict) else []
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "Data Origin" not in df.columns:
        return pd.DataFrame()
    return df[df["Data Origin"].astype(str).str.contains("Chapter 4 Research Assistant Evidence Bridge", na=False)].copy()


def render_phase4c_evidence_bridge(ticker: str, company_name: str, industry_group: str) -> None:
    safe = _safe_ticker(ticker)
    record = load_record(safe, company_name)
    existing = _phase4c_existing_rows(record)
    with st.container(border=True):
        st.markdown("### 🔎 Phase 4C.1 — Research Assistant Evidence Quality Bridge")
        st.caption(
            "Research Assistant ưu tiên nguồn gốc: IR/BCTN/BCTC chính thức → independent sources → search snippets; "
            "sau đó tìm supporting + counter-evidence cho Q15–Q20 và đưa vào Evidence Matrix dưới trạng thái Candidate. "
            "Nó không được đổi Assessment, Trend, Confidence, Conclusion hay Research Gate."
        )
        if not existing.empty and "Question" in existing.columns:
            counts = existing["Question"].value_counts().to_dict()
            cols = st.columns(6)
            for idx, q in enumerate(("Q15", "Q16", "Q17", "Q18", "Q19", "Q20")):
                cols[idx].metric(q, int(counts.get(q, 0)))
            st.caption(f"Đang lưu {len(existing)} evidence candidate(s) Phase 4C trong Evidence Matrix.")
        else:
            st.info("Chưa có evidence candidate Phase 4C được lưu cho mã này.")

        if st.button("🌐 Cập nhật Evidence chất lượng Q15–Q20", use_container_width=True, key=f"ch4c_refresh_evidence_{safe}"):
            with st.spinner(f"Research Assistant đang tìm supporting/counter-evidence cho {safe}..."):
                result = Chapter4EvidenceAgent(m1.RAW_DIR).search(safe, company_name, industry_group, max_results_per_query=4)
                latest = load_record(safe, company_name)
                latest = merge_candidates_into_evidence_matrix(latest, result.candidates)
                save_record(latest, create_snapshot=False)
                st.session_state[f"ch4c_candidates_{safe}"] = result.candidates
                st.session_state[f"ch4c_note_{safe}"] = result.note
            st.success(result.note)

        candidates = st.session_state.get(f"ch4c_candidates_{safe}")
        if isinstance(candidates, pd.DataFrame) and not candidates.empty:
            coverage = candidate_coverage(candidates)
            st.caption("Candidate coverage mới nhất: " + " | ".join(f"{q}: {coverage[q]}" for q in coverage))

            quality = evidence_quality_summary(candidates)
            if not quality.empty:
                st.markdown("**Evidence Quality / Coverage Audit**")
                render_static_table(quality, use_container_width=True, hide_index=True, height=250)

            gaps = research_gaps(candidates)
            if gaps:
                with st.expander(f"⚠ Research gaps còn mở ({len(gaps)})", expanded=True):
                    for gap in gaps:
                        st.write(f"- {gap}")
            else:
                st.success("Không còn coverage gap định lượng theo Phase 4C.1; analyst vẫn phải xác minh từng candidate trước khi kết luận.")

            show_cols = [c for c in ["Question", "Subtopic", "Direction", "Evidence Quality", "Source Method", "Explicitness", "Title", "URL", "Snippet"] if c in candidates.columns]
            render_static_table(candidates[show_cols].head(100), use_container_width=True, hide_index=True, height=420)
            st.warning("Nguồn A/B, Direction và Explicitness đều chỉ là Research Assistant classification. Analyst phải mở nguồn gốc và xác minh trước khi dùng làm kết luận.")
        elif not existing.empty:
            show_cols = [c for c in ["Question", "Claim", "Direction", "Evidence Type", "Source Title", "Source URL / File", "Evidence Text", "Status"] if c in existing.columns]
            render_static_table(existing[show_cols].tail(60), use_container_width=True, hide_index=True, height=320)


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
            render_static_table(summary, use_container_width=True, hide_index=True)

        if isinstance(pricing, pd.DataFrame):
            with st.expander(f"Q16 — Pricing evidence ({len(pricing)})", expanded=True):
                if pricing.empty:
                    st.warning("Chưa tìm được explicit pricing evidence; Q16 phải giữ Unknown/Research Gap nếu analyst chưa có nguồn khác.")
                else:
                    cols = [c for c in [
                        "Period Candidate", "Explicitness", "Event Type Candidate", "Evidence Quality",
                        "Source Method", "Title", "URL", "Snippet"
                    ] if c in pricing.columns]
                    render_static_table(pricing[cols].head(60), use_container_width=True, hide_index=True, height=330)
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
                    render_static_table(universe, use_container_width=True, hide_index=True, height=min(370, 75 + 27 * len(universe)))
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
                    render_static_table(q19[cols].head(80), use_container_width=True, hide_index=True, height=380)
                    covered = int(q19["Subtopic"].nunique()) if "Subtopic" in q19.columns else 0
                    if covered < 4:
                        st.warning(f"Q19 mới có evidence ở {covered}/8 nhóm logic; chưa nên coi competitive landscape đã hiểu đầy đủ.")
                    else:
                        st.info(f"Q19 có evidence ở {covered}/8 nhóm logic. Các nhóm chưa có vẫn là Research Gap.")

        st.warning(
            "Guardrail: price-only, margin-only hoặc commodity-price evidence không được tự biến thành Pricing Power; "
            "same-industry peer không được tự biến thành direct competitor; Research Assistant không được chọn Competition Intensity/Ideal Company hay đổi Research Gate."
        )



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
                render_static_table(corroboration, use_container_width=True, hide_index=True)
                st.caption(
                    "Period-level corroboration chỉ xác nhận có ≥2 nguồn/domain trong cùng kỳ và có independent evidence. "
                    "Analyst vẫn phải mở nguồn để xác minh chúng đang nói về cùng pricing event và loại trừ commodity/cost pass-through."
                )

        if isinstance(coverage, pd.DataFrame):
            st.markdown("**Q19 — Full Shearn Coverage Matrix**")
            render_static_table(coverage, use_container_width=True, hide_index=True, height=330)
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
                render_static_table(pricing[cols].head(80), use_container_width=True, hide_index=True, height=340)

        if isinstance(q19, pd.DataFrame) and not q19.empty:
            with st.expander(f"Q19 — Multi-label evidence ({len(q19)})", expanded=False):
                cols = [c for c in [
                    "Subtopic", "Direction", "Evidence Quality", "Period Candidate", "Source Method",
                    "Title", "URL", "Snippet"
                ] if c in q19.columns]
                render_static_table(q19[cols].head(140), use_container_width=True, hide_index=True, height=420)

        st.warning(
            "Guardrail Phase 4C.3: coverage ≠ conclusion; period-level corroboration ≠ event-level proof; cùng ngành ≠ direct competitor; "
            "Research Assistant không được tự chọn Pricing Power, Competition Intensity, Ideal Company, Research Gate hay BUY/HOLD/SELL."
        )


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
            render_static_table(audit.checks, use_container_width=True, hide_index=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Evidence giữ lại", len(audit.retained_candidates))
            c2.metric("Noise quarantine", len(audit.quarantined_candidates))
            covered = int(audit.q19_coverage["Candidates"].fillna(0).astype(int).gt(0).sum()) if not audit.q19_coverage.empty else 0
            c3.metric("Q19 A/B coverage", f"{covered}/8")

            if not audit.quarantined_candidates.empty:
                with st.expander(f"🧹 Evidence bị quarantine ({len(audit.quarantined_candidates)})", expanded=False):
                    cols = [c for c in ["Quarantine Reason", "Evidence Quality", "Title", "URL", "Snippet"] if c in audit.quarantined_candidates.columns]
                    render_static_table(audit.quarantined_candidates[cols].head(60), use_container_width=True, hide_index=True, height=300)
                    st.caption("Quarantine không xóa dữ liệu; row được giữ để audit nhưng không được dùng đóng evidence coverage.")

            st.markdown("**Q19 A/B Lock Coverage**")
            render_static_table(audit.q19_coverage, use_container_width=True, hide_index=True, height=330)

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

def _fmt(value: Any, suffix: str = "") -> str:
    try:
        if value is None or pd.isna(value):
            return "—"
        return f"{float(value):,.1f}{suffix}"
    except Exception:
        return "—"


def _styled_numeric(df: pd.DataFrame):
    if df is None or df.empty:
        return df
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    styler = df.style.format({c: "{:,.1f}" for c in numeric_cols}, na_rep="—")
    if numeric_cols:
        def _heat(v):
            try:
                value = float(v)
            except Exception:
                return ""
            if value < 0:
                return "color:#B91C1C;font-weight:700;"
            if value > 0:
                return "color:#047857;"
            return ""
        styler = styler.map(_heat, subset=numeric_cols)
    return styler


def _merge_q17_peer_rows(record: dict[str, Any], peer_df: pd.DataFrame, preserve_unmatched: bool = True) -> dict[str, Any]:
    """Refresh canonical numeric columns while preserving comments for retained peers.

    ``preserve_unmatched=False`` is used after analyst-curated peer confirmation so removed peers
    do not silently come back into Q17.
    """
    existing = record.get("q17_industry_peers") if isinstance(record, dict) else []
    existing = existing if isinstance(existing, list) else []
    existing_by_company = {
        _safe_ticker(str(row.get("Company") or "")): row
        for row in existing if isinstance(row, dict) and _safe_ticker(str(row.get("Company") or ""))
    }
    generated: list[dict[str, Any]] = []
    if isinstance(peer_df, pd.DataFrame) and not peer_df.empty:
        for _, item in peer_df.iterrows():
            ticker = _safe_ticker(str(item.get("Company") or ""))
            if not ticker:
                continue
            old = existing_by_company.get(ticker, {})
            row = {col: old.get(col, "") for col in INDUSTRY_PEER_COLUMNS}
            row.update({
                "Company": ticker,
                "ROIC Latest": item.get("ROIC Latest"),
                "ROIC 5Y Median": item.get("ROIC 5Y Median"),
                "ROIC 10Y Median": item.get("ROIC 10Y Median"),
                "ROIC Min": item.get("ROIC Min"),
                "ROIC Max": item.get("ROIC Max"),
                "EBIT Margin": item.get("EBIT Margin"),
                "CCC": item.get("CCC"),
                "Comment": old.get("Comment", ""),
            })
            generated.append(row)
    generated_tickers = {_safe_ticker(str(row.get("Company") or "")) for row in generated}
    if preserve_unmatched:
        for row in existing:
            if not isinstance(row, dict):
                continue
            key = _safe_ticker(str(row.get("Company") or ""))
            if not key or key not in generated_tickers:
                generated.append(row)
    record["q17_industry_peers"] = generated
    return record


def _refresh_target_data(ticker: str) -> tuple[bool, str]:
    safe = _safe_ticker(ticker)
    try:
        st.session_state["last_query_ticker"] = safe
        st.session_state["last_query_source"] = "FireAnt + Vietstock"
        m1._search_and_bind(safe, "FireAnt + Vietstock")
        checker = getattr(m1, "_active_bundle_has_data_for_ticker", None)
        ok = bool(checker(safe)) if callable(checker) else _safe_ticker(str(st.session_state.get("active_ticker", ""))) == safe
        if ok:
            for key in ("active_ticker", "shared_ticker", "module1_ticker", "module2_ticker"):
                st.session_state[key] = safe
            _snapshot_cached.clear()
            return True, f"Đã cập nhật canonical data cho {safe}."
        return False, f"Chưa lấy được canonical data cho {safe}; app không dùng dữ liệu mã khác thay thế."
    except Exception as exc:
        return False, f"Cập nhật canonical data chưa thành công: {exc}"


def render_quantitative_bridge(ticker: str) -> tuple[str, str, str]:
    safe = _safe_ticker(ticker) or "DGC"
    target_snapshot, target_error = load_quant_snapshot(safe)
    company_name = str((target_snapshot or {}).get("company_name") or "")
    record = load_record(safe, company_name)

    stored_peers = record.get("quantitative_peer_tickers", [])
    if not isinstance(stored_peers, list):
        stored_peers = []
    confirmed_peers = normalize_ticker_list(stored_peers, safe, max_peers=DEFAULT_MAX_PEERS)
    industry_group = str(record.get("quantitative_industry_group") or "")

    discovery_key = f"ch4q_discovery_{safe}"
    selection_key = f"ch4q_selection_seed_{safe}"
    version_key = f"ch4q_selection_version_{safe}"
    discovery = st.session_state.get(discovery_key)

    with st.container(border=True):
        st.markdown("### 📊 Phase 4B — Quantitative Bridge từ Trecapital canonical data")
        st.caption(
            "Q17/Q19 dùng quy trình 2 bước: (1) tải danh sách cùng ngành để Analyst lọc/thêm/bớt; "
            "(2) chỉ khi bấm Xác nhận & cập nhật thì app mới tải BCTC canonical cho danh sách đã chọn. "
            "Không tự kết luận Good/Bad Industry, Competition hay Ideal Company."
        )
        c1, c2 = st.columns([3, 1])
        with c1:
            if target_snapshot:
                prov = target_snapshot.get("provenance", {})
                st.success(
                    f"{safe} — {company_name or 'Doanh nghiệp'} | kỳ dữ liệu {target_snapshot.get('latest_period') or '—'} | "
                    f"{prov.get('source_label') or 'Trecapital'}"
                )
            else:
                st.warning(target_error)
        with c2:
            if st.button("🔄 Cập nhật data target", use_container_width=True, key=f"ch4q_refresh_target_{safe}"):
                with st.spinner(f"Đang cập nhật {safe}..."):
                    ok, note = _refresh_target_data(safe)
                (st.success if ok else st.warning)(note)
                if ok:
                    st.rerun()

        st.markdown("#### Bước 1 — Tải và lọc danh sách doanh nghiệp cùng ngành")
        l1, l2 = st.columns([2, 3])
        with l1:
            load_clicked = st.button(
                "1️⃣ Tải / tải lại danh sách cùng ngành",
                use_container_width=True,
                key=f"ch4q_load_industry_{safe}",
            )
        with l2:
            if confirmed_peers:
                st.info(
                    f"Peer set đã xác nhận đang dùng: {len(confirmed_peers) - 1} peer + {safe} target. "
                    "Danh sách này không tự mở rộng khi nguồn discovery xuất hiện mã mới."
                )
            else:
                st.caption("Chưa có peer set đã xác nhận; Q17 chỉ dùng target cho đến khi Analyst xác nhận.")

        if load_clicked:
            try:
                _industry_discovery_cached.clear()
            except Exception:
                pass
            discovery = _auto_peer_discovery(safe)
            st.session_state[discovery_key] = discovery
            peer_df_seed = discovery.get("peers") if isinstance(discovery, dict) else pd.DataFrame()
            if not isinstance(peer_df_seed, pd.DataFrame):
                peer_df_seed = pd.DataFrame()
            saved_for_seed = stored_peers if stored_peers else None
            st.session_state[selection_key] = build_peer_selection_table(peer_df_seed, safe, saved_for_seed)
            st.session_state[version_key] = int(st.session_state.get(version_key, 0)) + 1
            if isinstance(discovery, dict):
                industry_group = str(discovery.get("industry_group") or industry_group)

        selection_df = None
        if isinstance(discovery, dict):
            industry_group = str(discovery.get("industry_group") or industry_group)
            seed = st.session_state.get(selection_key)
            if not isinstance(seed, pd.DataFrame):
                peer_df_seed = discovery.get("peers")
                if not isinstance(peer_df_seed, pd.DataFrame):
                    peer_df_seed = pd.DataFrame()
                seed = build_peer_selection_table(peer_df_seed, safe, stored_peers if stored_peers else None)
                st.session_state[selection_key] = seed
            st.success(
                f"Nguồn discovery nhận diện: {industry_group or 'chưa rõ'} | "
                f"{max(0, len(seed) - 1)} candidate peer. Hãy bỏ chọn/xóa peer không sát hoặc thêm mã mới trước khi cập nhật dữ liệu."
            )
            version = int(st.session_state.get(version_key, 0))
            selection_df = st.data_editor(
                seed,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                height=min(500, 90 + 29 * max(1, len(seed))),
                key=f"ch4q_peer_editor_{safe}_{version}",
                column_config={
                    "Use?": st.column_config.CheckboxColumn("Dùng?", help="Chỉ các dòng được chọn mới được tải/cập nhật canonical data."),
                    "Ticker": st.column_config.TextColumn("Mã", required=True),
                },
            )
            st.caption(str(discovery.get("note") or ""))
            st.caption(f"Target {safe} luôn được giữ làm mốc benchmark dù có vô tình bỏ chọn/xóa trong editor.")
        elif stored_peers:
            st.caption("Bấm 'Tải / tải lại danh sách cùng ngành' để chỉnh peer set. Peer set đã xác nhận hiện tại vẫn được giữ nguyên.")

        st.markdown("#### Bước 2 — Xác nhận danh sách rồi mới tải/cập nhật BCTC")
        update_disabled = not isinstance(selection_df, pd.DataFrame)
        if st.button(
            "2️⃣ Xác nhận peer đã chọn & cập nhật dữ liệu Q17/Q19",
            use_container_width=True,
            disabled=update_disabled,
            key=f"ch4q_confirm_refresh_{safe}",
        ):
            selected = selected_peer_tickers(selection_df, safe, max_peers=DEFAULT_MAX_PEERS)
            if len(selected) < 2:
                st.warning("Danh sách chỉ có target. Hãy chọn/thêm ít nhất 1 doanh nghiệp so sánh trước khi cập nhật ngành.")
            else:
                progress = st.progress(0.02, text=f"Đang cập nhật canonical BCTC cho {len(selected)} mã đã được Analyst xác nhận...")
                refresh_results = refresh_peer_canonical_universe(selected, max_workers=3)
                notes = [note for _peer, _ok, _paths, note in refresh_results]
                ok_count = sum(1 for _peer, ok, _paths, _note in refresh_results if ok)
                progress.progress(0.90, text="Đang dựng ROIC/CCC/margins từ peer set đã xác nhận...")
                _snapshot_cached.clear()
                snapshots_after = []
                for peer in selected:
                    snap, _ = load_quant_snapshot(peer)
                    if snap:
                        snapshots_after.append(snap)
                peer_df_after = build_peer_table(snapshots_after)
                latest_record = load_record(safe, company_name)
                latest_record["quantitative_peer_tickers"] = [p for p in selected if p != safe]
                latest_record["quantitative_industry_group"] = industry_group
                latest_record["quantitative_peer_source"] = "Analyst-curated same-industry peer set + Trecapital canonical statements"
                latest_record["quantitative_peer_selection_updated_at"] = pd.Timestamp.now().isoformat()
                latest_record = _merge_q17_peer_rows(latest_record, peer_df_after, preserve_unmatched=False)
                save_record(latest_record, create_snapshot=False)
                st.session_state[selection_key] = build_peer_selection_table(
                    discovery.get("peers") if isinstance(discovery.get("peers"), pd.DataFrame) else pd.DataFrame(),
                    safe,
                    latest_record["quantitative_peer_tickers"],
                )
                progress.empty()
                st.success(
                    f"Đã xác nhận {len(selected)-1} peer; cập nhật thành công {ok_count}/{len(selected)} mã. "
                    f"Q17/Q19 chỉ dùng {len(peer_df_after)} mã có canonical data trong peer set này."
                )
                if notes:
                    with st.expander("Chi tiết cập nhật peer", expanded=False):
                        st.write(chr(10).join(f"- {x}" for x in notes))
                st.rerun()

        # Only the saved/confirmed list is used below. Discovery candidates alone never enter Q17/Q19.
        record = load_record(safe, company_name)
        stored_peers = record.get("quantitative_peer_tickers", []) if isinstance(record, dict) else []
        if not isinstance(stored_peers, list):
            stored_peers = []
        peers = normalize_ticker_list(stored_peers, safe, max_peers=DEFAULT_MAX_PEERS)
        if len(peers) == 1 and not stored_peers:
            peers = [safe]
        industry_group = str(record.get("quantitative_industry_group") or industry_group)

        snapshots: list[dict[str, Any]] = []
        missing: list[str] = []
        for peer in peers:
            snap, _ = load_quant_snapshot(peer)
            if snap:
                snapshots.append(snap)
            else:
                missing.append(peer)
        peer_df = build_peer_table(snapshots)

        if target_snapshot:
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("ROIC latest", _fmt(target_snapshot.get("roic_latest"), "%"))
            k2.metric("Gross Margin", _fmt(target_snapshot.get("gross_margin_latest"), "%"))
            k3.metric("EBIT Margin", _fmt(target_snapshot.get("ebit_margin_latest"), "%"))
            k4.metric("CCC", _fmt(target_snapshot.get("ccc_latest"), " ngày"))
            k5.metric("Inventory Turns", _fmt(target_snapshot.get("inventory_turnover_latest"), "x"))

        if missing:
            st.info("Mã trong peer set đã xác nhận nhưng chưa có canonical cache: " + ", ".join(missing))

        with st.expander("Q16 — Historical margin context (không suy Pricing Power)", expanded=False):
            context = pricing_context(target_snapshot or {})
            if context.empty:
                st.caption("Chưa có lịch sử canonical đủ dùng.")
            else:
                render_static_table(_styled_numeric(context), use_container_width=True, hide_index=True)
            st.caption(
                "Gross/EBIT margin chỉ là bằng chứng hỗ trợ. Không được suy 'đã tăng giá' hoặc 'có Pricing Power' từ margin tăng. "
                "Pricing Event vẫn cần explicit price/volume/customer evidence."
            )

        with st.expander("Q17 — Industry ROIC Distribution / Peer Economics", expanded=True):
            if peer_df.empty:
                st.caption("Chưa có canonical data trong peer set đã xác nhận.")
            else:
                display_cols = [c for c in (
                    "Company", "Company Name", "ROIC Latest", "ROIC 5Y Median", "ROIC 10Y Median",
                    "ROIC Min", "ROIC Max", "EBIT Margin", "CCC", "Data Period"
                ) if c in peer_df.columns]
                render_static_table(_styled_numeric(peer_df[display_cols]), use_container_width=True, hide_index=True)
                dist = build_industry_distribution(peer_df)
                if dist:
                    d1, d2, d3, d4, d5 = st.columns(5)
                    d1.metric("Peer có ROIC", dist.get("peer_count", 0))
                    d2.metric("Median ROIC", _fmt(dist.get("median_roic"), "%"))
                    d3.metric("P25 / P75", f"{_fmt(dist.get('p25_roic'), '%')} / {_fmt(dist.get('p75_roic'), '%')}")
                    d4.metric("ROIC Spread", _fmt(dist.get("spread_roic"), " đpt"))
                    d5.metric("ROIC dương", _fmt(dist.get("positive_roic_pct"), "%"))
                if len(peer_df) < 3:
                    st.warning("Peer set còn nhỏ; chưa nên xem đây là đại diện cho economics toàn ngành.")
            st.caption(
                "Q17 chỉ sử dụng peer set đã được Analyst xác nhận. Discovery candidate không tự đi vào bảng. "
                "'Good / Mixed / Bad Industry' vẫn chỉ Analyst được chọn."
            )

        with st.expander("Q19 — Table 4.2 quantitative peer benchmark", expanded=False):
            bench = build_peer_benchmark(peer_df, safe)
            if bench.empty:
                st.caption("Chưa có peer canonical data để dựng benchmark.")
            else:
                render_static_table(_styled_numeric(bench), use_container_width=True, hide_index=True)
            st.caption(
                "Benchmark dùng cùng peer set Analyst đã xác nhận ở Q17. Peer Min/Max chỉ là mô tả; app không tự chọn Ideal Company."
            )

        with st.expander("Q20 — Supply-chain operating context", expanded=False):
            supply = supply_chain_context(target_snapshot or {})
            if supply.empty:
                st.caption("Chưa có canonical inventory/receivable/payable data đủ để tính lịch sử.")
            else:
                render_static_table(_styled_numeric(supply), use_container_width=True, hide_index=True)
            st.caption(
                "Inventory Turnover và CCC là operating evidence. DPO tăng không tự động nghĩa là supplier relationship tốt; "
                "Supplier Reliability/Relationship/Concentration vẫn là analyst judgement dựa trên disclosure/evidence."
            )

        if snapshots:
            with st.expander("🔎 Data provenance — Phase 4B", expanded=False):
                prov_rows = []
                for snap in snapshots:
                    prov = snap.get("provenance", {})
                    prov_rows.append({
                        "Ticker": snap.get("ticker"),
                        "Doanh nghiệp": snap.get("company_name"),
                        "Kỳ dữ liệu": snap.get("latest_period"),
                        "Source Module": prov.get("source_module"),
                        "Data Origin": prov.get("data_origin"),
                        "Source Label": prov.get("source_label"),
                    })
                render_static_table(pd.DataFrame(prov_rows), use_container_width=True, hide_index=True)

    return safe, company_name, industry_group


def render_chapter4_tab(default_ticker: str) -> None:
    safe, company_name, industry_group = render_quantitative_bridge(default_ticker)
    render_phase4c_evidence_bridge(safe, company_name, industry_group)
    render_phase4c2_gap_engine(safe, company_name, industry_group)
    render_phase4c3_close_gaps(safe, company_name, industry_group)
    render_phase4d_final_lock(safe, company_name, industry_group)
    render_chapter4(default_ticker=safe, company_name=company_name)
