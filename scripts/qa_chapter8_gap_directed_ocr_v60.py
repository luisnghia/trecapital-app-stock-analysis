from __future__ import annotations

"""Live DGC acceptance for Chapter 8 Phase 8O gap-directed high-resolution OCR V60."""

import json
from pathlib import Path

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_official_file_ingestion_v60 import OfficialFileIngestionAgentV60
from modules.deep_company_analysis.chapter8_pdf_ocr import ocr_runtime_status
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
V59_REAL_NEWLY_COVERED = {("Q46", "shearn_action_5")}


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _covered_keys(frame: pd.DataFrame) -> set[tuple[str, str]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return set()
    mask = frame["Source Locked"].eq("Yes") & frame["Coverage Status"].eq("Candidate coverage — analyst verify")
    return set(zip(frame.loc[mask, "Question"].astype(str), frame.loc[mask, "Dimension Key"].astype(str)))


def main() -> int:
    ticker = "DGC"
    runtime_ok, runtime_note = ocr_runtime_status("vie+eng")
    assert runtime_ok, runtime_note

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
    assert not historical.empty and len(historical_open) == 40
    assert V59_REAL_NEWLY_COVERED.issubset(historical_open)
    v59_remaining = historical_open - V59_REAL_NEWLY_COVERED
    assert len(v59_remaining) == 39

    manifest = manifest_frame(DGC_REAL_OFFICIAL_SOURCES)
    manifest.to_csv(REPORTS / "CH8_DGC_GAP_OCR_MANIFEST_V60.csv", index=False, encoding="utf-8-sig")
    files, downloads = download_real_official_files(ticker, DGC_REAL_OFFICIAL_SOURCES)
    downloads.to_csv(REPORTS / "CH8_DGC_GAP_OCR_DOWNLOADS_V60.csv", index=False, encoding="utf-8-sig")
    fetched = downloads[downloads["Status"].eq("Fetched")]
    assert not fetched.empty, "No real DGC official PDF could be downloaded for V60 acceptance"

    agent = OfficialFileIngestionAgentV60("data_cache/chapter8_gap_ocr_v60")
    result = agent.ingest(
        ticker,
        files,
        existing_candidates=pd.DataFrame(columns=CANDIDATE_COLUMNS),
        manager_reference=manager_reference,
        max_targets=48,
        max_files=12,
        enable_ocr=True,
        ocr_languages="vie+eng",
        coarse_dpi=110,
        coarse_max_pages=36,
        coarse_workers=4,
        high_res_dpi=220,
        high_res_max_pages=10,
        neighbor_radius=1,
    )
    result.attempts.to_csv(REPORTS / "CH8_DGC_GAP_OCR_FILE_ATTEMPTS_V60.csv", index=False, encoding="utf-8-sig")
    result.documents.to_csv(REPORTS / "CH8_DGC_GAP_OCR_DOCUMENTS_V60.csv", index=False, encoding="utf-8-sig")
    result.new_candidates.to_csv(REPORTS / "CH8_DGC_GAP_OCR_NEW_CANDIDATES_V60.csv", index=False, encoding="utf-8-sig")
    result.after_coverage.to_csv(REPORTS / "CH8_DGC_GAP_OCR_COVERAGE_V60.csv", index=False, encoding="utf-8-sig")
    agent.last_diagnostics.to_csv(REPORTS / "CH8_DGC_GAP_OCR_DIAGNOSTICS_V60.csv", index=False, encoding="utf-8-sig")

    accepted = result.attempts[result.attempts["Status"].eq("Accepted")]
    assert not accepted.empty, "V60 produced no accepted real DGC scanned document"
    assert accepted["Official Provenance"].eq("Verified official URL").all()
    assert accepted["Ticker Match"].eq("Yes").all()
    assert not agent.last_diagnostics.empty
    selected_any = agent.last_diagnostics["High-res Selected Pages"].astype(str).str.len().gt(0).any()
    assert selected_any, "V60 did not select any gap-directed page for high-resolution OCR"

    if not result.new_candidates.empty:
        assert result.new_candidates["Status"].eq("Candidate — analyst verify").all()
        assert result.new_candidates["Select"].eq(False).all()
        ocr_candidates = result.new_candidates[result.new_candidates["Source Method"].str.contains("Phase 8O", na=False, regex=False)]
        assert not ocr_candidates.empty
        assert ocr_candidates["Evidence Text / Reference"].str.contains("OCR_PAGE", na=False, regex=False).all()

    real_covered = _covered_keys(result.after_coverage)
    additional_after_v59 = sorted(v59_remaining & real_covered)
    remaining = sorted(v59_remaining - set(additional_after_v59))
    pd.DataFrame([
        {
            "Question": question,
            "Dimension Key": key,
            "Prior Status": "Open after V59",
            "V60 Status": "Candidate coverage — analyst verify",
        }
        for question, key in additional_after_v59
    ]).to_csv(REPORTS / "CH8_DGC_V59_OPEN_GAPS_NEWLY_COVERED_V60.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([
        {"Question": question, "Dimension Key": key, "Status": "Still open after V60 gap-directed OCR pass"}
        for question, key in remaining
    ]).to_csv(REPORTS / "CH8_DGC_V59_OPEN_GAPS_REMAINING_V60.csv", index=False, encoding="utf-8-sig")

    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q47_share_count_is_proof"] is False

    q_distribution = result.new_candidates.groupby("Question").size().astype(int).to_dict() if not result.new_candidates.empty else {}
    highres_selected_total = 0
    highres_text_pages_total = 0
    for _, row in agent.last_diagnostics.iterrows():
        pages = [part for part in str(row.get("High-res Selected Pages", "")).split(",") if part.strip()]
        highres_selected_total += len(pages)
        highres_text_pages_total += int(row.get("High-res Pages With Text", 0) or 0)

    output = {
        "phase": "Chapter 8 Phase 8O Gap-Directed High-Resolution OCR Acceptance V60",
        "acceptance": "PASS",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": "TTM" if "TTM" in annual.astype(str).to_string() else "",
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "ocr_runtime": runtime_note,
        "real_manifest_documents": int(len(manifest)),
        "real_documents_downloaded": int(len(fetched)),
        "real_documents_accepted": int(len(accepted)),
        "gap_directed_ocr_document_passes": int(len(agent.last_diagnostics)),
        "high_res_selected_original_pages": int(highres_selected_total),
        "high_res_pages_with_text": int(highres_text_pages_total),
        "real_v60_candidates": int(len(result.new_candidates)),
        "candidate_distribution_by_question": q_distribution,
        "historical_v54_open_source_locked_dimensions": 40,
        "verified_v59_remaining_open_dimensions": 39,
        "v59_open_dimensions_newly_candidate_covered_by_v60": int(len(additional_after_v59)),
        "v59_open_dimensions_remaining_after_v60": int(len(remaining)),
        "newly_candidate_covered_dimensions_after_v59": [f"{q}:{k}" for q, k in additional_after_v59],
        "candidate_page_provenance_markers": True,
        "q43_dimension_contract": locks["q43_dimension_count"],
        "q46_source_locked_actions": locks["q46_source_locked_count"],
        "q47_share_count_decline_is_not_buyback_proof": True,
        "ocr_text_is_preapproved_evidence": False,
        "auto_promoted_evidence": False,
        "analyst_workspace_mutated": False,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "research_note": result.note,
    }
    (REPORTS / "CH8_DGC_GAP_OCR_ACCEPTANCE_V60.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
