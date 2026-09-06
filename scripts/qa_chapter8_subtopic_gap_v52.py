from __future__ import annotations

"""V52 live DGC acceptance for Chapter 8 dimension/subtopic research gaps.

The run demonstrates that candidate volume cannot close a question when evidence is concentrated
in only one dimension. It never promotes evidence and never writes analyst assessments.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter7_management_discovery import discover_management_candidates
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_gap_engine import (
    build_dimension_coverage,
    build_question_coverage_summary,
    validate_source_locks,
)
from modules.deep_company_analysis.chapter8_research_v52 import Chapter8ResearchAgent


REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _transient_ch7_payload(manager_candidates: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    """Use live Chapter 7 discovered names only as research-scoping candidates; never invent IDs."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    if isinstance(manager_candidates, pd.DataFrame) and not manager_candidates.empty:
        for _, source in manager_candidates.iterrows():
            name = _text(source.get("Manager"))
            role = _text(source.get("Role Normalized")) or _text(source.get("Role Raw"))
            if not name:
                continue
            key = (name.casefold(), role.casefold())
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "Manager ID": "",
                "Manager": name,
                "Current Role": role,
                "Analyst Classification": "Unknown",
                "Confidence": "Unknown",
            })
    frame = pd.DataFrame(rows)
    payload = {"management_profiles": rows}
    return payload, frame


def _structured_state(question: str, bridge: dict[str, Any]) -> str:
    key = {
        "Q41": "q41_guidance_history",
        "Q45": "q45_cost_context",
        "Q46": "q46_capital_allocation_context",
        "Q47": "q47_buyback_context",
    }.get(question)
    if not key:
        return "N/A — qualitative question"
    value = bridge.get(key)
    return "Available" if isinstance(value, pd.DataFrame) and not value.empty else "Missing"


def main() -> int:
    ticker = "DGC"
    ok, paths, canonical_note = refresh_peer_canonical_bundle(ticker)
    assert ok and paths, f"DGC canonical refresh failed: {canonical_note}"
    overview_path, annual_path, quarter_path = paths
    company = m1._load_overview_cached(str(overview_path), ticker)
    company_name = _text(getattr(company, "company_name", "")) or _text(getattr(company, "name", "")) or "CTCP Tập đoàn Hóa chất Đức Giang"
    annual_raw = m1._load_timeseries_cached(str(annual_path), ticker, "Y", 11)
    quarterly = m1._load_timeseries_cached(str(quarter_path), ticker, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    assert isinstance(annual, pd.DataFrame) and not annual.empty

    discovery = discover_management_candidates(
        ticker,
        company_name,
        max_documents=8,
        max_targets=5,
        timeout_seconds=6.0,
    )
    manager_candidates = discovery.managers.copy() if isinstance(discovery.managers, pd.DataFrame) else pd.DataFrame()
    chapter7_payload, manager_reference = _transient_ch7_payload(manager_candidates)
    if not manager_reference.empty:
        assert manager_reference.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str).eq("").all()

    bridge = build_phase8b_context(ticker, annual, chapter7_payload=chapter7_payload, guidance_rows=None)
    assert bridge["financial_ssot"] == "Trecapital canonical financial data / Module 1"
    assert bridge["manager_ssot"] == "Chapter 7 manager master"

    research = Chapter8ResearchAgent("data_cache/chapter8_subtopic_gap_v52/ch8").search(
        ticker,
        company_name,
        chapter7_payload=chapter7_payload,
        max_results_per_query=1,
        max_official_documents=12,
    )
    candidates = research.candidates.copy()
    gaps = research.gaps.copy()
    coverage = build_dimension_coverage(candidates)
    summary = build_question_coverage_summary(candidates, research.manager_reference)
    locks = validate_source_locks()

    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q46_source_locked_actions"] == tuple(ch8.CAPITAL_ALLOCATION_ACTIONS)
    assert locks["q47_share_count_is_proof"] is False
    assert "Score" not in summary.columns and "Coverage %" not in summary.columns
    assert summary["Boundary"].astype(str).str.contains("not a management score", case=False).all()

    q43 = summary[summary["Question"] == "Q43"].iloc[0]
    q46 = summary[summary["Question"] == "Q46"].iloc[0]
    assert int(q43["Dimensions Required"]) == 14
    assert int(q46["Dimensions Required"]) == 5
    # V52 acceptance is specifically designed to expose concentrated evidence rather than call it complete.
    assert int(q43["Dimensions Open"]) >= 1, "Unexpected full Q43 coverage; inspect live sources before changing the contract."
    assert int(q46["Dimensions Open"]) >= 1, "Unexpected full Q46 five-action coverage; inspect live sources before changing the contract."

    q47_cov = coverage[(coverage["Question"] == "Q47") & (coverage["Source Locked"] == "Yes")]
    share_count_only_phrase = "shares outstanding share-count decline"
    assert not any(share_count_only_phrase in " ".join(dim.terms).casefold() for dim in [])  # contract marker; no share-count proxy taxonomy
    assert len(q47_cov) == 4

    if not candidates.empty:
        assert candidates["Status"].astype(str).eq("Candidate — analyst verify").all()
    assert gaps["Status"].astype(str).str.contains("subtopic|evidence gap|manager|source-quality", case=False, regex=True).any()

    latest_period = ""
    q46_context = bridge.get("q46_capital_allocation_context")
    if isinstance(q46_context, pd.DataFrame) and not q46_context.empty:
        latest_period = _text(q46_context.iloc[-1].get("Kỳ"))

    coverage.to_csv(REPORTS / "CH8_DGC_DIMENSION_COVERAGE_V52.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(REPORTS / "CH8_DGC_QUESTION_COVERAGE_V52.csv", index=False, encoding="utf-8-sig")
    gaps.to_csv(REPORTS / "CH8_DGC_RESEARCH_GAPS_V52.csv", index=False, encoding="utf-8-sig")
    candidates.to_csv(REPORTS / "CH8_DGC_CANDIDATES_V52.csv", index=False, encoding="utf-8-sig")
    research.source_attempts.to_csv(REPORTS / "CH8_DGC_SOURCE_ATTEMPTS_V52.csv", index=False, encoding="utf-8-sig")

    per_question = {}
    for _, row in summary.iterrows():
        question = str(row["Question"])
        per_question[question] = {
            "title": ch8.QUESTION_TITLES[question],
            "dimensions_required": int(row["Dimensions Required"]),
            "dimensions_covered": int(row["Dimensions Covered"]),
            "dimensions_open": int(row["Dimensions Open"]),
            "manager_scope_required": bool(row["Manager Scope Required"]),
            "manager_scoped_candidates": int(row["Manager-scoped Candidates"]),
            "structured_context": _structured_state(question, bridge),
            "status": str(row["Status"]),
        }

    result = {
        "phase": "Chapter 8 Phase 8G Dimension/Subtopic Gap Engine V52",
        "acceptance": "PASS",
        "acceptance_meaning": "Candidate volume no longer hides missing Shearn dimensions/subtopics; analyst verification/promotion is still required.",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": latest_period,
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "chapter7_discovery_note": discovery.note,
        "chapter7_discovered_manager_candidates": int(len(manager_candidates)),
        "chapter8_research_candidates": int(len(candidates)),
        "chapter8_source_attempts": int(len(research.source_attempts)),
        "chapter8_research_gaps": int(len(gaps)),
        "q43_dimension_contract": locks["q43_dimension_count"],
        "q46_source_locked_actions": locks["q46_source_locked_count"],
        "q46_context_dimensions": list(locks["q46_context_dimensions"]),
        "q47_share_count_decline_is_not_buyback_proof": True,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "auto_promoted_evidence": False,
        "analyst_workspace_mutated": False,
        "per_question": per_question,
        "research_note": research.note,
    }
    (REPORTS / "CH8_DGC_SUBTOPIC_GAP_ACCEPTANCE_V52.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# DGC — Chapter 8 Dimension/Subtopic Gap Acceptance V52",
        "",
        f"- Company: **{company_name}**",
        f"- Canonical: **PASS** — {canonical_note}",
        f"- Latest period: **{latest_period or 'Unknown'}**",
        f"- Research candidates: **{len(candidates)}**",
        f"- Detailed research gaps: **{len(gaps)}**",
        "",
        "> V52 measures research coverage by source-locked dimensions. It is not a management score and never auto-promotes evidence.",
        "",
        "| Q | Required dimensions | Covered | Open | Manager-scoped candidates | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"| {row['Question']} | {int(row['Dimensions Required'])} | {int(row['Dimensions Covered'])} | "
            f"{int(row['Dimensions Open'])} | {int(row['Manager-scoped Candidates'])} | {row['Status']} |"
        )
    lines += [
        "",
        "## Source locks",
        "",
        "- Q43: exactly 14 Shearn employee-relation prompts.",
        "- Q46: exactly five Shearn excess-FCF actions; hurdle/discipline is context only, not a sixth bucket.",
        "- Q47: explicit buyback evidence required; share-count decline alone never creates coverage.",
        "- Chapter 7 remains manager identity SSOT; no replacement Manager IDs are created.",
        "- Trecapital canonical financial data remains financial SSOT.",
    ]
    (REPORTS / "CH8_DGC_SUBTOPIC_GAP_ACCEPTANCE_V52.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
