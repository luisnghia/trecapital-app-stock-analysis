from __future__ import annotations

"""DGC acceptance for Chapter 8 Phase 8L local official-file ingestion.

The uploaded-file fixture is synthetic and exists only to validate the local ingestion contract.
It is never presented as real DGC evidence. Real analyst files remain subject to provenance and
analyst verification.
"""

import json
from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.pdfgen import canvas

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_official_file_ingestion import OfficialFileIngestionAgent
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS


REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)


def _fixture_pdf() -> bytes:
    stream = BytesIO()
    c = canvas.Canvas(stream)
    c.drawString(72, 760, "DGC official-file ingestion fixture — test only, not investment evidence")
    c.drawString(72, 735, "employee training culture recruitment dividend capital allocation cost efficiency")
    c.drawString(72, 710, "reinvest acquisitions cash reserve share repurchase authorization")
    c.save()
    return stream.getvalue()


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _open_count(frame: pd.DataFrame) -> int:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return 0
    return int((frame["Source Locked"].eq("Yes") & ~frame["Coverage Status"].eq("Candidate coverage — analyst verify")).sum())


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

    result = OfficialFileIngestionAgent("data_cache/chapter8_official_file_v57/qa").ingest(
        ticker,
        [{
            "name": "DGC_phase8l_contract_fixture.pdf",
            "bytes": _fixture_pdf(),
            "issuer": "Company/IR",
            "source_url": "",
            "official_confirmed": True,
            "title": "Synthetic DGC ingestion-contract fixture — not real evidence",
        }],
        existing_candidates=pd.DataFrame(columns=CANDIDATE_COLUMNS),
        manager_reference=pd.DataFrame(),
        max_targets=48,
        max_files=4,
    )

    assert len(result.attempts) == 1
    assert result.attempts.iloc[0]["Status"] == "Accepted"
    assert result.attempts.iloc[0]["Ticker Match"] == "Yes"
    assert result.attempts.iloc[0]["Source Grade"].startswith("A?")
    assert result.raw_paths and Path(result.raw_paths[0]).exists()
    assert not result.new_candidates.empty
    assert result.new_candidates["Status"].eq("Candidate — analyst verify").all()
    assert result.new_candidates["Select"].eq(False).all()
    assert result.new_candidates["Data Origin"].str.contains("analyst provenance", case=False, regex=False).all()
    assert _open_count(result.after_coverage) <= _open_count(result.before_coverage)

    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q47_share_count_is_proof"] is False

    q46 = bridge.get("q46_capital_allocation_context")
    latest_period = _text(q46.iloc[-1].get("Kỳ")) if isinstance(q46, pd.DataFrame) and not q46.empty else ""

    result.attempts.to_csv(REPORTS / "CH8_DGC_OFFICIAL_FILE_ATTEMPTS_V57.csv", index=False, encoding="utf-8-sig")
    result.documents.to_csv(REPORTS / "CH8_DGC_OFFICIAL_FILE_DOCUMENTS_V57.csv", index=False, encoding="utf-8-sig")
    result.new_candidates.to_csv(REPORTS / "CH8_DGC_OFFICIAL_FILE_NEW_CANDIDATES_V57.csv", index=False, encoding="utf-8-sig")
    result.before_coverage.to_csv(REPORTS / "CH8_DGC_DIMENSION_COVERAGE_BEFORE_FILE_V57.csv", index=False, encoding="utf-8-sig")
    result.after_coverage.to_csv(REPORTS / "CH8_DGC_DIMENSION_COVERAGE_AFTER_FILE_V57.csv", index=False, encoding="utf-8-sig")
    result.remaining_gaps.to_csv(REPORTS / "CH8_DGC_REMAINING_GAPS_FILE_V57.csv", index=False, encoding="utf-8-sig")

    output = {
        "phase": "Chapter 8 Phase 8L Official File/PDF Ingestion V57",
        "acceptance": "PASS",
        "acceptance_meaning": "Local official-file ingestion contract passes using a synthetic DGC fixture; fixture is not real DGC investment evidence.",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": latest_period,
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "fixture_is_real_evidence": False,
        "official_files_received": 1,
        "official_files_accepted": int(result.attempts["Status"].eq("Accepted").sum()),
        "local_file_text_extraction": True,
        "network_required_for_uploaded_file": False,
        "new_candidates_from_fixture": int(len(result.new_candidates)),
        "open_source_locked_dimensions_before_fixture": _open_count(result.before_coverage),
        "open_source_locked_dimensions_after_fixture": _open_count(result.after_coverage),
        "remaining_research_gaps_fixture_context": int(len(result.remaining_gaps)),
        "q43_dimension_contract": locks["q43_dimension_count"],
        "q46_source_locked_actions": locks["q46_source_locked_count"],
        "q47_share_count_decline_is_not_buyback_proof": True,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "auto_promoted_evidence": False,
        "analyst_workspace_mutated": False,
        "research_note": result.note,
    }
    (REPORTS / "CH8_DGC_OFFICIAL_FILE_ACCEPTANCE_V57.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
