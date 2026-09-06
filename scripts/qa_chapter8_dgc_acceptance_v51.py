from __future__ import annotations

"""V51 live DGC Chapter 8 evidence-coverage acceptance.

This acceptance does not auto-promote research candidates and does not close Q39-Q47.
It combines live DGC canonical data, Chapter 7 management discovery, and Chapter 8
research to show the analyst exactly where candidate coverage exists and where evidence
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
from modules.deep_company_analysis.chapter7_research import Chapter7ResearchAgent
from modules.deep_company_analysis.chapter8_completion import build_completion_gate
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_research import Chapter8ResearchAgent


REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _chapter7_discovery_payload(manager_candidates: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    """Build a transient Chapter-7-shaped reference from Chapter 7 discovery only.

    Manager IDs are deliberately left blank. This is research scoping, not a replacement
    for analyst-confirmed Chapter 7 management profiles.
    """
    if not isinstance(manager_candidates, pd.DataFrame) or manager_candidates.empty:
        empty = pd.DataFrame(columns=["Manager ID", "Manager", "Current Role", "As-of Date", "Source URL / File", "Research Status"])
        return {"management_profiles": []}, empty

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
        rows.append(
            {
                "Manager ID": "",  # never fabricate an analyst manager ID
                "Manager": name,
                "Current Role": role,
                "As-of Date": _text(source.get("As-of Date")),
                "Source URL / File": _text(source.get("Source URL / File")),
                "Research Status": "Chapter 7 discovered candidate — analyst verify",
            }
        )

    frame = pd.DataFrame(rows)
    payload = {
        "management_profiles": [
            {
                "Manager ID": row["Manager ID"],
                "Manager": row["Manager"],
                "Current Role": row["Current Role"],
                "Analyst Classification": "Unknown",
                "Confidence": "Unknown",
            }
            for row in rows
        ]
    }
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


def _q47_explicit_buyback(bridge: dict[str, Any]) -> bool:
    frame = bridge.get("q47_buyback_context")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return False
    col = "Explicit buyback field available?"
    return bool(col in frame.columns and frame[col].astype(str).str.casefold().eq("yes").any())


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
        b_count = int(grades.str.startswith("B —").sum())
        c_count = int(grades.str.startswith("C —").sum())
        count = int(len(sub))
        gap_count, gap_status, next_action = _gap_action(gaps, question)
        if count == 0:
            coverage = "Evidence gap"
        elif a_count == 0:
            coverage = "Candidate coverage — source-quality gap"
        else:
            coverage = "Candidate coverage — analyst verify"

        top_source = ""
        if not sub.empty:
            preferred = sub[grades.str.startswith("A —")]
            chosen = preferred.iloc[0] if not preferred.empty else sub.iloc[0]
            top_source = _text(chosen.get("Source URL / File"))

        rows.append(
            {
                "Question": question,
                "Source-Locked Question": ch8.QUESTION_TITLES[question],
                "Coverage State": coverage,
                "Candidates": count,
                "A — Official": a_count,
                "B — Independent": b_count,
                "C — Secondary": c_count,
                "Manager-Scoped Candidates": int(managers.str.strip().ne("").sum()) if not managers.empty else 0,
                "Supporting Cues": int(directions.str.startswith("Supporting").sum()) if not directions.empty else 0,
                "Counter-evidence Cues": int(directions.str.startswith("Counter").sum()) if not directions.empty else 0,
                "Mixed Cues": int(directions.str.startswith("Mixed").sum()) if not directions.empty else 0,
                "Neutral / Context Cues": int(directions.str.startswith("Neutral").sum()) if not directions.empty else 0,
                "Structured Context": _structured_state(question, bridge),
                "Open Research Gaps": gap_count,
                "Gap Status": gap_status,
                "Next Evidence Action": next_action,
                "Top Candidate Source": top_source,
                "Analyst Closure": "OPEN — analyst verification/promotion required",
            }
        )
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

    # 1) Live Chapter 7 discovery is used only to scope manager-targeted Chapter 8 research.
    ch7 = Chapter7ResearchAgent("data_cache/chapter8_dgc_acceptance_v51/ch7").search(
        ticker,
        company_name,
        managers=[],
        max_results_per_query=2,
    )
    manager_candidates = ch7.manager_candidates.copy() if isinstance(ch7.manager_candidates, pd.DataFrame) else pd.DataFrame()
    chapter7_payload, managers = _chapter7_discovery_payload(manager_candidates)
    assert managers.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str).eq("").all(), "V51 must never fabricate Manager IDs"

    # 2) Canonical financial context + Chapter 7-discovered manager names.
    bridge = build_phase8b_context(
        ticker,
        annual,
        chapter7_payload=chapter7_payload,
        guidance_rows=None,
    )
    assert bridge["financial_ssot"] == "Trecapital canonical financial data / Module 1"
    assert bridge["manager_ssot"] == "Chapter 7 manager master"
    assert tuple(ch8.CAPITAL_ALLOCATION_ACTIONS) == (
        "Reinvest in business / new projects",
        "Hold cash",
        "Pay dividends",
        "Buy back stock",
        "Make acquisitions",
    )
    assert len(ch8.EMPLOYEE_RELATION_DIMENSIONS) == 14

    # 3) Live Chapter 8 research. Candidates remain candidates — no auto promotion.
    research = Chapter8ResearchAgent("data_cache/chapter8_dgc_acceptance_v51/ch8").search(
        ticker,
        company_name,
        chapter7_payload=chapter7_payload,
        max_results_per_query=2,
        max_official_documents=18,
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

    # 4) The live acceptance does not pretend an analyst has closed anything.
    live_payload = ch8.empty_payload(ticker, company_name)
    gate = build_completion_gate(live_payload, structured_context=bridge, chapter7_payload=chapter7_payload)
    assert gate["ready_for_chapter_close"] is False
    assert set(gate["open_questions"]) == set(ch8.QUESTION_KEYS)
    assert gate["automatic_management_score"] is False
    assert gate["automatic_investment_signal"] is False

    # Q47 source semantics: share-count change can never substitute for an explicit buyback field.
    explicit_buyback = _q47_explicit_buyback(bridge)
    q47_row = coverage.loc[coverage["Question"].eq("Q47")].iloc[0]
    assert "analyst verification" in str(q47_row["Analyst Closure"]).casefold()

    latest_period = ""
    q46 = bridge.get("q46_capital_allocation_context")
    if isinstance(q46, pd.DataFrame) and not q46.empty:
        latest_period = _text(q46.iloc[-1].get("Kỳ"))

    # Persist only reports, never analyst workspace state.
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

    md_lines = [
        "# DGC — Chapter 8 Q39–Q47 Live Evidence Acceptance V51",
        "",
        f"- Company: **{company_name}**",
        f"- Canonical: **PASS** — {canonical_note}",
        f"- Latest period: **{latest_period or 'Unknown'}**",
        f"- Chapter 7 discovered manager reference rows: **{len(managers)}** (Manager IDs intentionally blank)",
        f"- Chapter 8 candidates: **{len(candidates)}**",
        f"- Research gaps: **{len(gaps)}**",
        f"- Completion gate: **{'READY' if gate['ready_for_chapter_close'] else 'OPEN'}**",
        "",
        "> This acceptance never promotes evidence or writes analyst conclusions. Candidate coverage is not a management-quality rating.",
        "",
        "| Q | Coverage | Candidates | A-official | Manager-scoped | Structured | Gaps |",
        "|---|---|---:|---:|---:|---|---:|",
    ]
    for _, row in coverage.iterrows():
        md_lines.append(
            f"| {row['Question']} | {row['Coverage State']} | {int(row['Candidates'])} | {int(row['A — Official'])} | "
            f"{int(row['Manager-Scoped Candidates'])} | {row['Structured Context']} | {int(row['Open Research Gaps'])} |"
        )
    md_lines += ["", "## Exact next evidence actions", ""]
    for _, row in coverage.iterrows():
        action = str(row["Next Evidence Action"] or "No machine-detected gap; analyst still verifies candidates before closure.")
        md_lines.append(f"- **{row['Question']}** — {action}")
    md_lines += [
        "",
        "## Boundaries",
        "",
        "- Financial SSOT: Trecapital canonical financial data / Module 1.",
        "- Manager identity SSOT: Chapter 7. Live discovered names here are research targets, not replacement analyst IDs.",
        "- Q43 remains exactly 14 employee-relation dimensions.",
        "- Q46 remains exactly five Shearn capital-allocation uses.",
        "- Q47 requires explicit buyback evidence; share-count decline alone is not proof.",
        "- No automatic management score, MOS/Research Gate mutation or BUY/HOLD/SELL.",
    ]
    (REPORTS / "CH8_DGC_ACCEPTANCE_V51.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
