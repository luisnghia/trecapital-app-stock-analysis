from __future__ import annotations

"""Chapter 10 Phase 10F — deterministic research completion and analyst-owned growth synthesis.

The completion gate measures research completeness only. It never scores growth quality,
forecasts growth, changes valuation/MOS, or creates an investment signal.
"""

from copy import deepcopy
from typing import Any

import modules.deep_company_analysis.chapter10 as ch10


SYNTHESIS_STATUS_OPTIONS = ("Unknown", "Draft", "Reviewed", "Final")


def completion_gate(payload: dict[str, Any] | None) -> dict[str, Any]:
    p = ch10.normalize_payload(payload or {})
    questions: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    for q in ch10.QUESTION_KEYS:
        dims = ch10.dimension_ids(q)
        dim_status = [p["dimension_status"].get(d, "Unknown") for d in dims]
        unresolved = [d for d, status in zip(dims, dim_status) if status == "Unknown"]
        q_status = p["question_status"].get(q, "Unknown")
        confidence = p["confidence"].get(q, "Unknown")
        assessment = str(p["analyst_assessment"].get(q) or "").strip()
        ready = q_status in {"Answered", "N/A"} and confidence != "Unknown" and assessment not in {"", "Unknown"} and not unresolved
        reasons: list[str] = []
        if q_status not in {"Answered", "N/A"}: reasons.append("question status is not Answered/N/A")
        if confidence == "Unknown": reasons.append("confidence is Unknown")
        if assessment in {"", "Unknown"}: reasons.append("analyst assessment is missing")
        if unresolved: reasons.append(f"{len(unresolved)} evidence dimension(s) remain Unknown")
        questions[q] = {"ready": ready, "research_status": q_status, "confidence": confidence, "unresolved_dimensions": unresolved, "reasons": reasons}
        if not ready: blockers.append(f"{q}: " + "; ".join(reasons))
    return {
        "ready": not blockers,
        "questions": questions,
        "blockers": blockers,
        "answered_questions": sum(p["question_status"].get(q) == "Answered" for q in ch10.QUESTION_KEYS),
        "total_questions": len(ch10.QUESTION_KEYS),
        "resolved_dimensions": sum(p["dimension_status"].get(d) != "Unknown" for d in ch10.dimension_ids()),
        "total_dimensions": len(ch10.dimension_ids()),
    }


def default_synthesis() -> dict[str, Any]:
    return {
        "status": "Unknown",
        "growth_route_takeaway": "",
        "profitability_takeaway": "",
        "runway_takeaway": "",
        "pace_and_funding_takeaway": "",
        "key_strengths": "",
        "key_concerns": "",
        "key_unknowns": "",
        "final_growth_synthesis": "",
        "analyst_note": "",
    }


def normalize_synthesis(value: dict[str, Any] | None) -> dict[str, Any]:
    out = default_synthesis()
    if isinstance(value, dict):
        for key in out:
            if key in value:
                out[key] = str(value[key] or "")
    if out["status"] not in SYNTHESIS_STATUS_OPTIONS:
        out["status"] = "Unknown"
    return out


def attach_synthesis(payload: dict[str, Any] | None, synthesis: dict[str, Any] | None) -> dict[str, Any]:
    p = ch10.normalize_payload(deepcopy(payload or {}))
    p["growth_synthesis"] = normalize_synthesis(synthesis)
    return p


def report_section(payload: dict[str, Any] | None) -> dict[str, Any]:
    p = ch10.normalize_payload(payload or {})
    gate = completion_gate(p)
    synthesis = normalize_synthesis((payload or {}).get("growth_synthesis") if isinstance(payload, dict) else None)
    rows = []
    for q in ch10.QUESTION_KEYS:
        rows.append({
            "Question": q,
            "Question Text": ch10.QUESTION_TITLES[q],
            "Research Status": p["question_status"].get(q, "Unknown"),
            "Confidence": p["confidence"].get(q, "Unknown"),
            "Analyst Assessment": p["analyst_assessment"].get(q, "Unknown"),
            "Research Ready": gate["questions"][q]["ready"],
        })
    return {
        "title": "Chapter 10 — Evaluating Growth Opportunities",
        "source_lock": ch10.SOURCE_LOCK,
        "research_ready": gate["ready"],
        "completion": gate,
        "questions": rows,
        "synthesis": synthesis,
        "boundary_note": "Research completion is not a Growth Score, forecast, valuation conclusion, MOS change, Research Gate change, or BUY/HOLD/SELL signal.",
    }


__all__ = ["SYNTHESIS_STATUS_OPTIONS", "completion_gate", "default_synthesis", "normalize_synthesis", "attach_synthesis", "report_section"]
