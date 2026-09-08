from __future__ import annotations

"""Chapter 11 deterministic research completion and analyst-owned M&A synthesis.

The completion gate measures research completeness only. It never scores M&A quality,
classifies an acquisition as successful/unsuccessful, forecasts synergy, changes valuation/MOS,
changes the Investment Research Gate, or creates an investment signal. V89 also preserves
explicit analyst re-review metadata across Streamlit reruns and durable save/load cycles.
"""

from copy import deepcopy
from typing import Any

import modules.deep_company_analysis.chapter11 as ch11


SYNTHESIS_STATUS_OPTIONS = ("Unknown", "Draft", "Reviewed", "Final")


def completion_gate(payload: dict[str, Any] | None) -> dict[str, Any]:
    p = ch11.normalize_payload(payload or {})
    questions: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    for q in ch11.QUESTION_KEYS:
        dims = ch11.dimension_ids(q)
        unresolved = [d for d in dims if p["dimension_status"].get(d, "Unknown") == "Unknown"]
        q_status = p["question_status"].get(q, "Unknown")
        confidence = p["confidence"].get(q, "Unknown")
        assessment = str(p["analyst_assessment"].get(q) or "").strip()
        ready = q_status in {"Answered", "N/A"} and confidence != "Unknown" and assessment not in {"", "Unknown"} and not unresolved
        reasons: list[str] = []
        if q_status not in {"Answered", "N/A"}:
            reasons.append("question status is not Answered/N/A")
        if confidence == "Unknown":
            reasons.append("confidence is Unknown")
        if assessment in {"", "Unknown"}:
            reasons.append("analyst assessment is missing")
        if unresolved:
            reasons.append(f"{len(unresolved)} evidence dimension(s) remain Unknown")
        questions[q] = {
            "ready": ready,
            "research_status": q_status,
            "confidence": confidence,
            "unresolved_dimensions": unresolved,
            "reasons": reasons,
        }
        if not ready:
            blockers.append(f"{q}: " + "; ".join(reasons))
    return {
        "ready": not blockers,
        "questions": questions,
        "blockers": blockers,
        "answered_questions": sum(p["question_status"].get(q) == "Answered" for q in ch11.QUESTION_KEYS),
        "total_questions": len(ch11.QUESTION_KEYS),
        "resolved_dimensions": sum(p["dimension_status"].get(d) != "Unknown" for d in ch11.dimension_ids()),
        "total_dimensions": len(ch11.dimension_ids()),
    }


def default_synthesis() -> dict[str, Any]:
    return {
        "status": "Unknown",
        "decision_process_takeaway": "",
        "motivation_and_fit_takeaway": "",
        "synergy_and_integration_takeaway": "",
        "historical_acquisition_takeaway": "",
        "price_and_financing_takeaway": "",
        "key_strengths": "",
        "key_concerns": "",
        "key_unknowns": "",
        "final_ma_synthesis": "",
        "analyst_note": "",
        "analyst_reviewed_at": "",
        "last_re_review_at": "",
        "last_re_review_note": "",
        "last_re_review_sections": [],
    }


def normalize_synthesis(value: dict[str, Any] | None) -> dict[str, Any]:
    out = default_synthesis()
    if isinstance(value, dict):
        for key in out:
            if key not in value:
                continue
            if key == "last_re_review_sections":
                raw = value.get(key)
                if isinstance(raw, (list, tuple)):
                    out[key] = [str(x).strip() for x in raw if str(x).strip()]
                elif str(raw or "").strip():
                    out[key] = [str(raw).strip()]
            else:
                out[key] = str(value.get(key) or "")
    if out["status"] not in SYNTHESIS_STATUS_OPTIONS:
        out["status"] = "Unknown"
    return out


def attach_synthesis(payload: dict[str, Any] | None, synthesis: dict[str, Any] | None) -> dict[str, Any]:
    p = ch11.normalize_payload(deepcopy(payload or {}))
    p["ma_synthesis"] = normalize_synthesis(synthesis)
    return p


def report_section(payload: dict[str, Any] | None) -> dict[str, Any]:
    p = ch11.normalize_payload(payload or {})
    gate = completion_gate(p)
    synthesis = normalize_synthesis((payload or {}).get("ma_synthesis") if isinstance(payload, dict) else None)
    rows = []
    for q in ch11.QUESTION_KEYS:
        rows.append({
            "Question": q,
            "Question Text": ch11.QUESTION_TITLES[q],
            "Research Status": p["question_status"].get(q, "Unknown"),
            "Confidence": p["confidence"].get(q, "Unknown"),
            "Analyst Assessment": p["analyst_assessment"].get(q, "Unknown"),
            "Research Ready": gate["questions"][q]["ready"],
        })
    return {
        "title": "Chapter 11 — Evaluating Mergers & Acquisitions",
        "source_lock": ch11.SOURCE_LOCK,
        "research_ready": gate["ready"],
        "completion": gate,
        "questions": rows,
        "synthesis": synthesis,
        "boundary_note": "Research completion is not an M&A Score, acquisition-success conclusion, synergy forecast, valuation conclusion, MOS change, Investment Research Gate change, or BUY/HOLD/SELL signal.",
    }


__all__ = [
    "SYNTHESIS_STATUS_OPTIONS", "completion_gate", "default_synthesis", "normalize_synthesis",
    "attach_synthesis", "report_section",
]
