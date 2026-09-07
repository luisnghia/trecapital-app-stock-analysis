from __future__ import annotations

"""Live DGC acceptance for Chapter 8 Phase 8P / V61 section-directed official retrieval."""

import json
from pathlib import Path

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_real_official_sources import v54_historical_open_keys
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS
from modules.deep_company_analysis.chapter8_section_directed_retrieval_runtime_v61 import SectionDirectedRetrievalAgentV61Runtime


REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)
V59_REAL_NEWLY_COVERED = {("Q46", "shearn_action_5")}
DGC_SECTION_SEEDS = (
    "https://ducgiangchem.vn/category/quan-he-co-dong/bao-cao-thuong-nien/",
    "https://ducgiangchem.vn/category/quan-he-co-dong/bao-cao-quan-tri/",
    "https://ducgiangchem.vn/category/quan-he-co-dong/dai-hoi-co-dong/",
    "https://ducgiangchem.vn/category/quan-he-co-dong/nghi-quyet-dai-hoi-co-dong/",
    "https://ducgiangchem.vn/category/quan-he-co-dong/thong-bao/",
)


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _covered_keys(frame: pd.DataFrame) -> set[tuple[str, str]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return set()
    mask = frame["Source Locked"].eq("Yes") & frame["Coverage Status"].eq("Candidate coverage — analyst verify")
    return set(zip(frame.loc[mask, "Question"].astype(str), frame.loc[mask, "Dimension Key"].astype(str)))


def main() -> int:
    ticker = "DGC"
    ok, paths, canonical_note = refresh_peer_canonical_bundle(ticker)
    assert ok and paths, canonical_note
    overview_path, annual_path, quarter_path = paths
    company = m1._load_overview_cached(str(overview_path), ticker)
    company_name = _text(getattr(company, "company_name", "")) or _text(getattr(company, "name", "")) or "CTCP Tập đoàn Hóa chất Đức Giang"
    annual_raw = m1._load_timeseries_cached(str(annual_path), ticker, "Y", 11)
    quarterly = m1._load_timeseries_cached(str(quarter_path), ticker, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    assert isinstance(annual, pd.DataFrame) and not annual.empty

    bridge = build_phase8b_context(ticker, annual, chapter7_payload=None, guidance_rows=None)
    assert bridge["financial_ssot"] == "Trecapital canonical financial data / Module 1"
    assert bridge["manager_ssot"] == "Chapter 7 manager master"
    manager_reference = bridge.get("manager_reference", pd.DataFrame())

    historical_open = v54_historical_open_keys()
    assert len(historical_open) == 40
    assert V59_REAL_NEWLY_COVERED.issubset(historical_open)
    v59_remaining = historical_open - V59_REAL_NEWLY_COVERED
    assert len(v59_remaining) == 39

    agent = SectionDirectedRetrievalAgentV61Runtime("data_cache/chapter8_section_retrieval_v61")
    result = agent.run(
        ticker,
        existing_candidates=pd.DataFrame(columns=CANDIDATE_COLUMNS),
        manager_reference=manager_reference,
        target_keys=v59_remaining,
        seed_urls=DGC_SECTION_SEEDS,
        max_targets=64,
        max_documents=12,
        max_files=7,
        max_scanned_ocr_docs=0,
        year_floor=2022,
    )

    result.targets.to_csv(REPORTS / "CH8_DGC_SECTION_TARGETS_V61.csv", index=False, encoding="utf-8-sig")
    result.section_plan.to_csv(REPORTS / "CH8_DGC_SECTION_PLAN_V61.csv", index=False, encoding="utf-8-sig")
    result.discovery.to_csv(REPORTS / "CH8_DGC_SECTION_DISCOVERY_V61.csv", index=False, encoding="utf-8-sig")
    result.downloads.to_csv(REPORTS / "CH8_DGC_SECTION_DOWNLOADS_V61.csv", index=False, encoding="utf-8-sig")
    result.ingestion.attempts.to_csv(REPORTS / "CH8_DGC_SECTION_FILE_ATTEMPTS_V61.csv", index=False, encoding="utf-8-sig")
    result.ingestion.documents.to_csv(REPORTS / "CH8_DGC_SECTION_DOCUMENTS_V61.csv", index=False, encoding="utf-8-sig")
    result.ingestion.new_candidates.to_csv(REPORTS / "CH8_DGC_SECTION_NEW_CANDIDATES_V61.csv", index=False, encoding="utf-8-sig")
    result.ingestion.after_coverage.to_csv(REPORTS / "CH8_DGC_SECTION_COVERAGE_V61.csv", index=False, encoding="utf-8-sig")
    getattr(agent, "last_ocr_diagnostics", pd.DataFrame()).to_csv(REPORTS / "CH8_DGC_SECTION_OCR_DIAGNOSTICS_V61.csv", index=False, encoding="utf-8-sig")

    assert len(result.targets) == 39, f"V61 should be aimed at the 39 V59-open source-locked dimensions, got {len(result.targets)}"
    assert not result.section_plan.empty
    assert set(result.section_plan["Questions"].astype(str).str.findall(r"Q4\d").explode().dropna()).issubset({f"Q{i}" for i in range(39, 48)})
    assert not result.discovery.empty, "V61 found no issuer archive documents"
    assert result.discovery["Official URL"].eq("Yes").all()
    historical_docs = result.discovery[pd.to_numeric(result.discovery["Year"], errors="coerce").fillna(0).between(2022, 2024)]
    assert not historical_docs.empty, "V61 did not expand into 2022-2024 official history"

    fetched = result.downloads[result.downloads["Status"].astype(str).str.startswith("Fetched")]
    assert not fetched.empty, "V61 could not download any section-directed official DGC document"
    selected_attempts = result.ingestion.attempts[result.ingestion.attempts["Status"].eq("Accepted")]
    assert not selected_attempts.empty, "V61 produced no ticker-validated accepted official document"
    assert selected_attempts["Official Provenance"].eq("Verified official URL").all()
    assert selected_attempts["Ticker Match"].eq("Yes").all()

    if not result.ingestion.new_candidates.empty:
        assert result.ingestion.new_candidates["Status"].eq("Candidate — analyst verify").all()
        assert result.ingestion.new_candidates["Select"].eq(False).all()

    real_covered = _covered_keys(result.ingestion.after_coverage)
    additional_after_v59 = sorted(v59_remaining & real_covered)
    remaining = sorted(v59_remaining - set(additional_after_v59))
    pd.DataFrame([
        {"Question": q, "Dimension Key": key, "Prior Status": "Open after V59", "V61 Status": "Candidate coverage — analyst verify"}
        for q, key in additional_after_v59
    ]).to_csv(REPORTS / "CH8_DGC_V59_OPEN_GAPS_NEWLY_COVERED_V61.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([
        {"Question": q, "Dimension Key": key, "Status": "Still open after V61 section-directed retrieval"}
        for q, key in remaining
    ]).to_csv(REPORTS / "CH8_DGC_V59_OPEN_GAPS_REMAINING_V61.csv", index=False, encoding="utf-8-sig")

    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q47_share_count_is_proof"] is False

    q_distribution = result.ingestion.new_candidates.groupby("Question").size().astype(int).to_dict() if not result.ingestion.new_candidates.empty else {}
    section_distribution = result.discovery.groupby("Section").size().astype(int).to_dict() if not result.discovery.empty else {}
    manifest_rows = int(result.discovery["Discovery Method"].astype(str).str.contains("manifest fallback", case=False, regex=False).sum())
    output = {
        "phase": "Chapter 8 Phase 8P Official Document Expansion + Section-Directed Retrieval V61",
        "acceptance": "PASS",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": "TTM" if "TTM" in annual.astype(str).to_string() else "",
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "v61_target_dimensions": int(len(result.targets)),
        "v61_section_plan_rows": int(len(result.section_plan)),
        "official_documents_discovered": int(len(result.discovery)),
        "verified_manifest_fallback_rows": manifest_rows,
        "historical_2022_2024_documents_discovered": int(len(historical_docs)),
        "official_documents_fetched": int(len(fetched)),
        "ticker_validated_documents_accepted": int(len(selected_attempts)),
        "document_distribution_by_section": section_distribution,
        "real_v61_candidates": int(len(result.ingestion.new_candidates)),
        "candidate_distribution_by_question": q_distribution,
        "historical_v54_open_source_locked_dimensions": 40,
        "verified_v59_remaining_open_dimensions": 39,
        "v59_open_dimensions_newly_candidate_covered_by_v61": int(len(additional_after_v59)),
        "v59_open_dimensions_remaining_after_v61": int(len(remaining)),
        "newly_candidate_covered_dimensions_after_v59": [f"{q}:{key}" for q, key in additional_after_v59],
        "q43_dimension_contract": locks["q43_dimension_count"],
        "q46_source_locked_actions": locks["q46_source_locked_count"],
        "q47_share_count_decline_is_not_buyback_proof": True,
        "auto_promoted_evidence": False,
        "analyst_workspace_mutated": False,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "research_note": result.note,
    }
    (REPORTS / "CH8_DGC_SECTION_ACCEPTANCE_V61.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
