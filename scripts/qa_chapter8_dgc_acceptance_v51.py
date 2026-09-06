from __future__ import annotations

"""V51 live DGC Chapter 8 evidence-coverage acceptance.

This acceptance does not auto-promote research candidates and does not close Q39-Q47.
It combines live DGC canonical data, bounded Chapter 7 management discovery, and
Chapter 8 research to show exactly where candidate coverage exists and where evidence
or source-quality gaps remain.
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
from modules.deep_company_analysis.chapter8_completion import build_completion_gate
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_research import Chapter8ResearchAgent


REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _chapter7_discovery_payload(manager_candidates: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    """Transient Chapter-7-shaped reference; Manager IDs are never fabricated."""
    columns = ["Manager ID", "Manager", "Current Role", "As-of Date", "Source URL / File", "Research Status"]
    if not isinstance(manager_candidates, pd.DataFrame) or manager_candidates.empty:
        return {"management_profiles": []}, pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
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
            "As-of Date": _text(source.get("As-of Date")),
            "Source URL / File": _text(source.get("Source URL / File")),
            "Research Status": "Chapter 7 discovered candidate — analyst verify",
        })

    payload = {"management_profiles": [
        {
            "Manager ID": "",
            "Manager": row["Manager"],
            "Current Role": row["Current Role"],
            "Analyst Classification": "Unknown",
            "Confidence": "Unknown",
        }
        for row in rows
    ]}
    return payload, pd.DataFrame(rows, columns=columns)


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


def _q47_explicit_buyback(bridge: dict[str, Any]) -> bool:
    frame = bridge.get("q47_buyback_context")
    col = "Explicit buyback field available?"
    return bool(
        isinstance(frame, pd.DataFrame)
        and not frame.empty
        and col in frame.columns
        and frame[col].astype(str).str.casefold().eq("yes").any()
    )


def _gap_action(gaps: pd.DataFrame, question: str) -> tuple[int, str, str]:
    if not isinstance(gaps, pd.DataFrame) or gaps.empty or "Question" not in gaps.columns:
        return 0, "", ""
    sub = gaps[gaps["Question"].astype(str).eq(question)]
    if sub.empty:
        return 0, "", ""
    statuses = "; ".join(dict.fromkeys(sub.get("Status", pd.Series(dtype="object")).fillna("").astype(str)))
    actions = " | ".join(dict.fromkeys(sub.get("Next Action", pd.Series(dtype="object")).fillna("").astype(str)))
    return int(len(sub)), statuses, actions


def _coverage_table(research: Any, bridge: dict[str, Any]) -> pd.DataFrame:
    candidates = research.candidates if isinstance(research.candidates, pd.DataFrame) else pd.DataFrame()
    gaps = research.gaps if isinstance(research.gaps, pd.DataFrame) else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for question in ch8.QUESTION_KEYS:
        sub = candidates[candidates["Question"].astype(str).eq(question)].copy() if not candidates.empty else pd.DataFrame()
        grades = sub.get("Source Grade", pd.Series(dtype="object")).fillna("").astype(str)
        directions = sub.get("Direction", pd.Series(dtype="object")).fillna("").astype(str)
        managers = sub.get("Manager", pd.Series(dtype="object")).fillna("").astype(str)
        a_count = int(grades.str.startswith("A —").sum())
        count = int(len(sub))
        gap_count, gap_status, next_action = _gap_action(gaps, question)
        coverage = (
            "Evidence gap" if count == 0
            else "Candidate coverage — source-quality gap" if a_count == 0
            else "Candidate coverage — analyst verify"
        )
        top_source = ""
        if not sub.empty:
            preferred = sub[grades.str.startswith("A —")]
            chosen = preferred.iloc[0] if not preferred.empty else sub.iloc[0]
            top_source = _text(chosen.get("Source URL / File"))
        rows.append({
            "Question": question,
            "Source-Locked Question": ch8.QUESTION_TITLES[question],
            "Coverage State": coverage,
            "Candidates": count,
            "A — Official": a_count,
            "B — Independent": int(grades.str.startswith("B —").sum()),
            "C — Secondary": int(grades.str.startswith("C —").sum()),
            "Manager-Scoped Candidates": int(managers.str.strip().ne("").sum()) if not managers.empty else 0,
            "Supporting Cues": int(directions.str.startswith("Supporting").sum()),
            "Counter-evidence Cues": int(directions.str.startswith("Counter").sum()),
            "Mixed Cues": int(directions.str.startswith("Mixed").sum()),
            "Neutral / Context Cues": int(directions.str.startswith("Neutral").sum()),
            "Structured Context": _structured_state(question, bridge),
            "Open Research Gaps": gap_count,
            "Gap Status": gap_status,
            "Next Evidence Action": next_action,
            "Top Candidate Source": top_source,
            "Analyst Closure": "OPEN — analyst verification/promotion required",
        })
    return pd.DataFrame(rows)


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

    # Bounded live Chapter 7 discovery only; no need to rerun all Q33-Q38 research for Chapter 8 scoping.
    ch7_discovery = discover_management_candidates(
        ticker,
        company_name,
        max_documents=8,
        max_targets=5,
        timeout_seconds=6.0,
    )
    manager_candidates = ch7_discovery.managers.copy() if isinstance(ch7_discovery.managers, pd.DataFrame) else pd.DataFrame()
    chapter7_payload, managers = _chapter7_discovery_payload(manager_candidates)
    assert managers.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str).eq("").all(), "V51 must never fabricate Manager IDs"

    bridge = build_phase8b_context(ticker, annual, chapter7_payload=chapter7_payload, guidance_rows=None)
    assert bridge["financial_ssot"] == "Trecapital canonical financial data / Module 1"
    assert bridge["manager_ssot"] == "Chapter 7 manager master"
    assert len(ch8.EMPLOYEE_RELATION_DIMENSIONS) == 14
    assert tuple(ch8.CAPITAL_ALLOCATION_ACTIONS) == (
        "Reinvest in business / new projects", "Hold cash", "Pay dividends", "Buy back stock", "Make acquisitions"
    )

    # V44 proved one-result/12-document bounded research yields useful official-source coverage while staying finite.
    research = Chapter8ResearchAgent("data_cache/chapter8_dgc_acceptance_v51/ch8").search(
        ticker,
        company_name,
        chapter7_payload=chapter7_payload,
        max_results_per_query=1,
        max_official_documents=12,
    )
    candidates = research.candidates.copy()
    gaps = research.gaps.copy()
    assert list(research.quality["Question"].astype(str)) == list(ch8.QUESTION_KEYS)
    assert len(research.source_attempts) >= 1, "No DGC official/company source attempted"
    if not candidates.empty:
        assert candidates["Status"].astype(str).eq("Candidate — analyst verify").all()
        assert candidates["Manager ID"].fillna("").astype(str).eq("").all(), "Chapter 8 invented Manager IDs"

    coverage = _coverage_table(research, bridge)
    assert list(coverage["Question"].astype(str)) == list(ch8.QUESTION_KEYS)

    # No real analyst decisions are synthesized during acceptance.
    live_payload = ch8.empty_payload(ticker, company_name)
    gate = build_completion_gate(live_payload, structured_context=bridge, chapter7_payload=chapter7_payload)
    assert gate["ready_for_chapter_close"] is False
    assert set(gate["open_questions"]) == set(ch8.QUESTION_KEYS)
    assert gate["automatic_management_score"] is False
    assert gate["automatic_investment_signal"] is False

    explicit_buyback = _q47_explicit_buyback(bridge)
    q47_row = coverage.loc[coverage["Question"].eq("Q47")].iloc[0]
    assert "analyst verification" in str(q47_row["Analyst Closure"]).casefold()

    q46 = bridge.get("q46_capital_allocation_context")
    latest_period = _text(q46.iloc[-1].get("Kỳ")) if isinstance(q46, pd.DataFrame) and not q46.empty else ""

    managers.to_csv(REPORTS / "CH8_DGC_MANAGERS_FROM_CH7_V51.csv", index=False, encoding="utf-8-sig")
    candidates.to_csv(REPORTS / "CH8_DGC_CANDIDATES_V51.csv", index=False, encoding="utf-8-sig")
    gaps.to_csv(REPORTS / "CH8_DGC_RESEARCH_GAPS_V51.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(REPORTS / "CH8_DGC_Q39_Q47_EVIDENCE_COVERAGE_V51.csv", index=False, encoding="utf-8-sig")
    research.source_attempts.to_csv(REPORTS / "CH8_DGC_SOURCE_ATTEMPTS_V51.csv", index=False, encoding="utf-8-sig")

    per_question = {
        str(row["Question"]): {
            "title": str(row["Source-Locked Question"]),
            "coverage_state": str(row["Coverage State"]),
            "candidates": int(row["Candidates"]),
            "official_A": int(row["A — Official"]),
            "manager_scoped_candidates": int(row["Manager-Scoped Candidates"]),
            "structured_context": str(row["Structured Context"]),
            "research_gaps": int(row["Open Research Gaps"]),
            "gap_status": str(row["Gap Status"]),
            "next_evidence_action": str(row["Next Evidence Action"]),
            "analyst_closure": str(row["Analyst Closure"]),
        }
        for _, row in coverage.iterrows()
    }

    result = {
        "acceptance": "PASS",
        "acceptance_meaning": "Engineering/evidence workflow works; DGC Q39-Q47 remain analyst-open until evidence is verified/promoted and conclusions are entered.",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": latest_period,
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "chapter7_discovery_note": ch7_discovery.note,
        "chapter7_discovered_manager_candidates": int(len(manager_candidates)),
        "chapter7_unique_manager_reference_rows": int(len(managers)),
        "chapter7_reference_mode": "Transient live Chapter 7 discovery for research scoping; not an analyst-confirmed replacement manager master; Manager IDs intentionally blank.",
        "chapter8_research_candidates": int(len(candidates)),
        "chapter8_source_attempts": int(len(research.source_attempts)),
        "chapter8_research_gaps": int(len(gaps)),
        "q43_dimension_contract": len(ch8.EMPLOYEE_RELATION_DIMENSIONS),
        "q46_source_locked_actions": len(ch8.CAPITAL_ALLOCATION_ACTIONS),
        "q47_explicit_buyback_field_available": explicit_buyback,
        "q47_share_count_decline_is_not_buyback_proof": True,
        "live_completion_gate_ready": bool(gate["ready_for_chapter_close"]),
        "live_open_questions": list(gate["open_questions"]),
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "auto_promoted_evidence": False,
        "analyst_workspace_mutated": False,
        "per_question": per_question,
        "research_note": research.note,
    }
    (REPORTS / "CH8_DGC_ACCEPTANCE_V51.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    lines = [
        "# DGC — Chapter 8 Q39–Q47 Live Evidence Acceptance V51", "",
        f"- Company: **{company_name}**", f"- Canonical: **PASS** — {canonical_note}",
        f"- Latest period: **{latest_period or 'Unknown'}**",
        f"- Chapter 7 discovered manager reference rows: **{len(managers)}** (Manager IDs intentionally blank)",
        f"- Chapter 8 candidates: **{len(candidates)}**", f"- Research gaps: **{len(gaps)}**",
        f"- Completion gate: **{'READY' if gate['ready_for_chapter_close'] else 'OPEN'}**", "",
        "> This acceptance never promotes evidence or writes analyst conclusions. Candidate coverage is not a management-quality rating.", "",
        "| Q | Coverage | Candidates | A-official | Manager-scoped | Structured | Gaps |",
        "|---|---|---:|---:|---:|---|---:|",
    ]
    for _, row in coverage.iterrows():
        lines.append(
            f"| {row['Question']} | {row['Coverage State']} | {int(row['Candidates'])} | {int(row['A — Official'])} | "
            f"{int(row['Manager-Scoped Candidates'])} | {row['Structured Context']} | {int(row['Open Research Gaps'])} |"
        )
    lines += ["", "## Exact next evidence actions", ""]
    for _, row in coverage.iterrows():
        action = str(row["Next Evidence Action"] or "No machine-detected gap; analyst still verifies candidates before closure.")
        lines.append(f"- **{row['Question']}** — {action}")
    lines += ["", "## Boundaries", "",
        "- Financial SSOT: Trecapital canonical financial data / Module 1.",
        "- Manager identity SSOT: Chapter 7. Live discovered names here are research targets, not replacement analyst IDs.",
        "- Q43 remains exactly 14 employee-relation dimensions.",
        "- Q46 remains exactly five Shearn capital-allocation uses.",
        "- Q47 requires explicit buyback evidence; share-count decline alone is not proof.",
        "- No automatic management score, MOS/Research Gate mutation or BUY/HOLD/SELL.",
    ]
    (REPORTS / "CH8_DGC_ACCEPTANCE_V51.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
