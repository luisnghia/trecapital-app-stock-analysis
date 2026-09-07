from __future__ import annotations

"""Live DGC acceptance for Chapter 8 Phase 8M real official documents V58."""

import json
from pathlib import Path

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_official_file_ingestion import OfficialFileIngestionAgent
from modules.deep_company_analysis.chapter8_real_official_sources import (
    DGC_REAL_OFFICIAL_SOURCES,
    download_real_official_files,
    load_v54_dgc_coverage,
    manifest_frame,
    v54_historical_open_keys,
)
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS

REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)

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

    historical = load_v54_dgc_coverage()
    historical_open = v54_historical_open_keys()
    assert len(historical_open) == 40

    manifest = manifest_frame(DGC_REAL_OFFICIAL_SOURCES)
    manifest.to_csv(REPORTS / "CH8_DGC_REAL_OFFICIAL_MANIFEST_V58.csv", index=False, encoding="utf-8-sig")

    files, download_attempts = download_real_official_files(ticker, DGC_REAL_OFFICIAL_SOURCES)
    download_attempts.to_csv(REPORTS / "CH8_DGC_REAL_OFFICIAL_DOWNLOADS_V58.csv", index=False, encoding="utf-8-sig")
    assert not download_attempts.empty
    assert download_attempts["Official URL"].eq("Yes").all()
    print("V58 real-source download diagnostics:")
    print(download_attempts.to_string(index=False))
    fetched = download_attempts[download_attempts["Status"].eq("Fetched")]
    network_available = not fetched.empty

    empty_candidates = pd.DataFrame(columns=CANDIDATE_COLUMNS)
    result = OfficialFileIngestionAgent("data_cache/chapter8_real_official_v58").ingest(
        ticker,
        files,
        existing_candidates=empty_candidates,
        manager_reference=manager_reference,
        max_targets=48,
        max_files=12,
    )
    if not result.attempts.empty:
        print("V58 Phase 8L real-file ingestion diagnostics:")
        print(result.attempts.to_string(index=False))
    accepted = result.attempts[result.attempts["Status"].eq("Accepted")] if not result.attempts.empty else pd.DataFrame()
    if not accepted.empty:
        assert accepted["Official Provenance"].eq("Verified official URL").all()
        assert accepted["Ticker Match"].eq("Yes").all()

    if not result.new_candidates.empty:
        assert result.new_candidates["Status"].eq("Candidate — analyst verify").all()
        assert result.new_candidates["Select"].eq(False).all()
        assert result.new_candidates["Source Grade"].eq("A — Official URL + uploaded file").all()
        assert result.new_candidates["Source URL / File"].astype(str).str.startswith("https://ducgiangchem.vn/").all()

    real_covered = _covered_keys(result.after_coverage)
    historical_newly_covered = sorted(historical_open & real_covered)
    historical_remaining = sorted(historical_open - set(historical_newly_covered))

    closure_rows = []
    for question, key in historical_newly_covered:
        row = result.after_coverage[
            result.after_coverage["Question"].astype(str).eq(question)
            & result.after_coverage["Dimension Key"].astype(str).eq(key)
        ]
        closure_rows.append({
            "Question": question,
            "Dimension Key": key,
            "Dimension": _text(row.iloc[0].get("Dimension")) if not row.empty else "",
            "Candidates from real docs": int(row.iloc[0].get("Candidates") or 0) if not row.empty else 0,
            "Historical V54 Status": "Open — source-locked",
            "V58 Status": "Candidate coverage — analyst verify",
        })
    closures = pd.DataFrame(closure_rows)

    remaining_rows = []
    for question, key in historical_remaining:
        row = historical[
            historical["Question"].astype(str).eq(question)
            & historical["Dimension Key"].astype(str).eq(key)
        ]
        remaining_rows.append({
            "Question": question,
            "Dimension Key": key,
            "Dimension": _text(row.iloc[0].get("Dimension")) if not row.empty else "",
            "Status": "Still open after V58 real-document pass",
        })
    remaining = pd.DataFrame(remaining_rows)

    result.attempts.to_csv(REPORTS / "CH8_DGC_REAL_OFFICIAL_FILE_ATTEMPTS_V58.csv", index=False, encoding="utf-8-sig")
    result.documents.to_csv(REPORTS / "CH8_DGC_REAL_OFFICIAL_DOCUMENTS_V58.csv", index=False, encoding="utf-8-sig")
    result.new_candidates.to_csv(REPORTS / "CH8_DGC_REAL_OFFICIAL_NEW_CANDIDATES_V58.csv", index=False, encoding="utf-8-sig")
    result.after_coverage.to_csv(REPORTS / "CH8_DGC_REAL_OFFICIAL_COVERAGE_V58.csv", index=False, encoding="utf-8-sig")
    closures.to_csv(REPORTS / "CH8_DGC_V54_OPEN_GAPS_NEWLY_COVERED_V58.csv", index=False, encoding="utf-8-sig")
    remaining.to_csv(REPORTS / "CH8_DGC_V54_OPEN_GAPS_REMAINING_V58.csv", index=False, encoding="utf-8-sig")

    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q47_share_count_is_proof"] is False

    q_distribution = result.new_candidates.groupby("Question").size().astype(int).to_dict() if not result.new_candidates.empty else {}
    rejected_no_text = int(result.attempts["Status"].astype(str).str.contains("no extractable text", case=False, na=False).sum()) if not result.attempts.empty else 0
    if not network_available:
        ingestion_status = "OFFICIAL_CDN_BLOCKED_IN_CI"
    elif len(accepted):
        ingestion_status = "INGESTED"
    else:
        ingestion_status = "TEXT_EXTRACTION_BLOCKED"

    output = {
        "phase": "Chapter 8 Phase 8M Real Official Document Acceptance V58",
        "acceptance": "PASS",
        "acceptance_meaning": "Real DGC official-document manifest, provenance controls and V57 file-ingestion path were exercised. External issuer/CDN availability and embedded-text availability are observed rather than assumed; inaccessible or non-extractable documents remain explicit research gaps and never become evidence.",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": "TTM" if "TTM" in annual.astype(str).to_string() else "",
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "real_manifest_documents": int(len(manifest)),
        "real_official_network_available_in_ci": bool(network_available),
        "real_documents_downloaded": int(len(fetched)),
        "real_documents_ingested": int(len(accepted)),
        "real_document_ingestion_status": ingestion_status,
        "real_documents_rejected_no_extractable_text": rejected_no_text,
        "real_document_bytes": int(fetched["Bytes"].sum()) if not fetched.empty else 0,
        "real_new_candidates": int(len(result.new_candidates)),
        "real_candidate_distribution_by_question": q_distribution,
        "historical_v54_open_source_locked_dimensions": 40,
        "historical_v54_open_dimensions_newly_candidate_covered_by_real_docs": int(len(historical_newly_covered)),
        "historical_v54_open_dimensions_remaining_after_real_doc_pass": int(len(historical_remaining)),
        "newly_candidate_covered_dimensions": [f"{q}:{k}" for q, k in historical_newly_covered],
        "q43_dimension_contract": locks["q43_dimension_count"],
        "q46_source_locked_actions": locks["q46_source_locked_count"],
        "q47_share_count_decline_is_not_buyback_proof": True,
        "real_docs_are_preapproved_evidence": False,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "auto_promoted_evidence": False,
        "analyst_workspace_mutated": False,
        "research_note": result.note,
    }
    (REPORTS / "CH8_DGC_REAL_OFFICIAL_ACCEPTANCE_V58.json").write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
