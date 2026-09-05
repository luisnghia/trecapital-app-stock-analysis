from __future__ import annotations

"""Chapter 7 Phase 7D — Final Source Closure & Completion Gate.

This module closes Michael Shearn Chapter 7 Q33–Q38 as a research package. It never turns
research completeness into a Management Quality score, investment Research Gate, MOS, or
BUY/HOLD/SELL. All final management conclusions remain analyst-owned.
"""

from datetime import datetime
from typing import Any

import pandas as pd

from modules.deep_company_analysis.chapter7 import LION_HYENA_DIMENSIONS, QUESTION_KEYS


CLOSURE_BOUNDARY = (
    "Chapter 7 completion verifies research/source completeness only; it is not Management Quality, "
    "MOS, an investment Research Gate, portfolio sizing, or BUY/HOLD/SELL. Analyst owns final conclusions."
)

FINAL_CHECKLIST_STATUS_OPTIONS = ("Unknown", "Covered", "Evidence weak", "N/A")
FINAL_CHECKLIST_COLUMNS = ["ID", "Question", "Source-Locked Requirement", "Status", "Evidence / Rationale", "Analyst Note"]
RESIDUAL_UNKNOWN_STATUS_OPTIONS = ("Open", "Accepted Residual Unknown", "Resolved", "N/A")
RESIDUAL_UNKNOWN_COLUMNS = [
    "Question", "Unknown / Gap", "Materiality", "Evidence Attempted", "Status",
    "Acceptance Reason", "Accepted By Analyst", "Accepted At", "Analyst Note",
]

FINAL_CHECKLIST_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("7K01", "Q33/Q36", "Understand the background of senior managers."),
    ("7K02", "Q33/Q36", "Review a sufficiently long management track record when available, including favorable and difficult periods."),
    ("7K03", "Q34", "If outside management is relevant, review whether managers learned customers/employees/business before major changes."),
    ("7K04", "Q35", "Review all seven source-locked Lion/Hyena dimensions from Table 7.1 without a numerical score."),
    ("7K05", "Q36", "Verify functional experience and operating/customer exposure where evidence is available."),
    ("7K06", "Q36", "Treat corporate-suite-only background as a research issue, not an automatic penalty."),
    ("7K07", "Q37", "Separate cash compensation from actual equity ownership."),
    ("7K08", "Q37", "Review compensation metrics and measurement horizon when disclosed."),
    ("7K09", "Q37", "Keep actual shares, options, RSU/restricted awards and ESOP/unvested awards separate."),
    ("7K10", "Q37", "Review compensation consultant / benchmarking when disclosed."),
    ("7K11", "Q37", "Review material upfront, guaranteed, severance or similar compensation when disclosed."),
    ("7K12", "Q38", "Separate registered from executed insider transactions and identify transaction type."),
    ("7K13", "Q38", "Interpret insider transactions in context; never use them as a standalone Buy/Sell signal."),
    ("7K14", "Q33-Q38", "Review supporting evidence before finalizing the chapter."),
    ("7K15", "Q33-Q38", "Review counter-evidence / contradictory evidence before finalizing the chapter."),
    ("7K16", "All", "Resolve source conflicts or explicitly accept the residual uncertainty."),
    ("7K17", "All", "Close material research gaps or explicitly accept residual unknowns after documented research attempts."),
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_final_checklist_rows() -> list[dict[str, Any]]:
    return [
        {
            "ID": item_id,
            "Question": question,
            "Source-Locked Requirement": requirement,
            "Status": "Unknown",
            "Evidence / Rationale": "",
            "Analyst Note": "",
        }
        for item_id, question, requirement in FINAL_CHECKLIST_ITEMS
    ]


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return [dict(row) for row in value.where(pd.notna(value), None).to_dict("records")]
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    return []


def _is_accepted_unknown(row: dict[str, Any]) -> bool:
    return str(row.get("Status") or "") in {"Accepted Residual Unknown", "Resolved", "N/A"} and bool(
        row.get("Accepted By Analyst") or str(row.get("Status") or "") in {"Resolved", "N/A"}
    )


def accepted_unknown_for_question(payload: dict[str, Any], question: str) -> bool:
    q = str(question or "").upper()
    for row in _records(payload.get("chapter7_residual_unknowns")):
        rq = str(row.get("Question") or "").upper()
        if (rq == q or rq in {"ALL", "Q33-Q38"}) and _is_accepted_unknown(row):
            return True
    return False


def source_coverage_matrix(
    payload: dict[str, Any],
    conflicts: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    evidence = _records(payload.get("evidence_matrix"))
    gaps = _records(payload.get("research_gaps_table"))
    unresolved_conflicts = [c for c in (conflicts or []) if str(c.get("status") or "Needs analyst review") == "Needs analyst review"]
    rows: list[dict[str, Any]] = []
    for q in QUESTION_KEYS:
        q_evidence = [row for row in evidence if str(row.get("Question") or "").upper() == q]
        grades = [str(row.get("Source Grade") or row.get("Evidence Type") or "") for row in q_evidence]
        directions = [str(row.get("Direction") or "") for row in q_evidence]
        q_gaps = [row for row in gaps if str(row.get("Question") or "").upper() == q and not _gap_closed(row)]
        a_count = sum(1 for value in grades if value.startswith("A —") or "Primary official" in value)
        b_count = sum(1 for value in grades if value.startswith("B —"))
        c_count = sum(1 for value in grades if value.startswith("C —"))
        counter_count = sum(1 for value in directions if "counter" in value.casefold() or "contradict" in value.casefold())
        if q_evidence and a_count:
            coverage = "Covered"
        elif q_evidence:
            coverage = "Evidence weak"
        else:
            coverage = "Unknown"
        rows.append(
            {
                "Question": q,
                "Evidence Candidates/Promoted": len(q_evidence),
                "A — Official": a_count,
                "B — Independent": b_count,
                "C — Secondary": c_count,
                "Counter-Evidence": counter_count,
                "Open Research Gaps": len(q_gaps),
                "Open Source Conflicts": len(unresolved_conflicts),
                "Coverage": coverage,
                "Boundary": "Coverage only — not Management Quality",
            }
        )
    return pd.DataFrame(rows)


def _parse_date(value: Any) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def career_coverage_audit(payload: dict[str, Any]) -> pd.DataFrame:
    rows = _records(payload.get("career_timeline"))
    managers = sorted({str(r.get("Manager") or "").strip() for r in rows if str(r.get("Manager") or "").strip()})
    starts = [_parse_date(r.get("From")) for r in rows]
    ends = [_parse_date(r.get("To")) for r in rows]
    dates = [x for x in starts + ends if x is not None]
    years_covered: float | None = None
    if dates:
        years_covered = round((max(dates) - min(dates)).days / 365.25, 1)
    functions = sorted({str(r.get("Functional Area") or "").strip() for r in rows if str(r.get("Functional Area") or "").strip()})
    potential_gaps = sum(1 for r in rows if str(r.get("Career Gap?") or "").casefold() in {"yes", "true", "potential", "unknown"})
    unresolved_gaps = sum(
        1 for r in rows
        if str(r.get("Career Gap?") or "").casefold() in {"yes", "true", "potential"}
        and str(r.get("Gap Explanation") or "").strip().casefold() in {"", "unknown", "—"}
    )
    return pd.DataFrame([
        {"Metric": "Senior managers with career records", "Value": f"{len(managers)}/5" if len(managers) <= 5 else str(len(managers)), "Boundary": "Coverage only"},
        {"Metric": "Historical years covered", "Value": "—" if years_covered is None else f"{years_covered:.1f}", "Boundary": "No fake dates"},
        {"Metric": "Known role episodes", "Value": len(rows), "Boundary": "Source chronology"},
        {"Metric": "Functional categories observed", "Value": len(functions), "Boundary": "Research cue only"},
        {"Metric": "Potential career gaps", "Value": potential_gaps, "Boundary": "Potential gap ≠ unemployment/problem"},
        {"Metric": "Unresolved career gaps", "Value": unresolved_gaps, "Boundary": "Unknown if source does not explain"},
        {"Metric": "Oldest verified career date", "Value": min(dates).strftime("%d/%m/%Y") if dates else "—", "Boundary": "As disclosed"},
        {"Metric": "Latest verified career date", "Value": max(dates).strftime("%d/%m/%Y") if dates else "—", "Boundary": "As disclosed"},
    ])


def compensation_ownership_reconciliation(payload: dict[str, Any]) -> pd.DataFrame:
    comp = _records(payload.get("compensation_history"))
    own = _records(payload.get("ownership_history"))
    checks = [
        ("Cash compensation source/unknown", bool(comp), "Do not invent individual amounts from aggregate disclosure"),
        ("Aggregate vs individual scope retained", all(str(r.get("Compensation Scope") or "").strip() for r in comp) if comp else False, "No pro-rata allocation"),
        ("Actual shares separated", any(r.get("Actual Shares") not in (None, "") for r in own), "Actual economic ownership"),
        ("Options separate", bool(own) and all("Options" in r for r in own), "Potential ownership kept separate"),
        ("RSU / restricted separate", bool(own) and all("RSU / Restricted" in r for r in own), "Potential ownership kept separate"),
        ("Unvested / ESOP awards separate", bool(own) and all("Unvested Awards" in r for r in own), "Potential ownership kept separate"),
        ("Ownership origin reviewed", any(str(r.get("Ownership Origin") or "").strip() not in {"", "Unknown"} for r in own), "Unknown is allowed when undisclosed"),
        ("Compensation metric reviewed", any(str(r.get("Performance Metric") or "").strip() for r in comp), "Unknown if undisclosed"),
        ("Measurement horizon reviewed", any(str(r.get("Measurement Horizon") or "").strip() for r in comp), "Unknown if undisclosed"),
        ("Consultant / guaranteed / severance fields retained", bool(comp) and all("Compensation Consultant" in r and "Guaranteed Component" in r and "Severance (tỷ)" in r for r in comp), "Research signal only"),
    ]
    return pd.DataFrame([
        {"Check": label, "Status": "Covered" if ok else "Unknown", "Boundary": note}
        for label, ok, note in checks
    ])


def insider_context_audit(payload: dict[str, Any]) -> pd.DataFrame:
    tx = _records(payload.get("insider_transactions"))
    checks = [
        ("Registered shares field retained", bool(tx) and all("Registered Shares" in r for r in tx)),
        ("Executed shares field retained", bool(tx) and all("Executed Shares" in r for r in tx)),
        ("Transaction type identified/Unknown", bool(tx) and all("Transaction Type" in r for r in tx)),
        ("Ownership before/after kept separate", bool(tx) and all("Ownership Before" in r and "Ownership After" in r for r in tx)),
        ("Stated reason only as disclosed", bool(tx) and all("Stated Reason" in r for r in tx)),
        ("Analyst materiality/interpretation fields retained", bool(tx) and all("Analyst Materiality" in r and "Analyst Interpretation" in r for r in tx)),
    ]
    return pd.DataFrame([
        {"Check": label, "Status": "Covered" if ok else "Unknown", "Boundary": "No automatic conviction / Buy-Sell signal"}
        for label, ok in checks
    ])


def _gap_closed(row: dict[str, Any]) -> bool:
    status = str(row.get("Status") or "").casefold()
    return any(token in status for token in ("closed", "resolved", "accepted", "n/a", "covered"))


def _checklist_complete(payload: dict[str, Any]) -> bool:
    rows = _records(payload.get("chapter7_final_checklist"))
    if len(rows) != len(FINAL_CHECKLIST_ITEMS):
        return False
    expected_ids = {item[0] for item in FINAL_CHECKLIST_ITEMS}
    ids = {str(row.get("ID") or "") for row in rows}
    if ids != expected_ids:
        return False
    return all(str(row.get("Status") or "") in {"Covered", "N/A"} for row in rows)


def _lion_matrix_valid(payload: dict[str, Any]) -> bool:
    rows = _records(payload.get("lion_hyena_matrix"))
    expected = [item[0] for item in LION_HYENA_DIMENSIONS]
    observed = [str(row.get("Dimension") or "") for row in rows]
    return len(rows) == len(expected) and set(observed) == set(expected)


def chapter7_completion_status(
    payload: dict[str, Any],
    *,
    open_conflicts: list[dict[str, Any]] | None = None,
    open_review_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    statuses = payload.get("question_status") or {}
    for q in QUESTION_KEYS:
        if str(statuses.get(q) or "Unknown") not in {"Answered", "N/A"}:
            blockers.append(f"{q} chưa ở trạng thái Answered/N/A.")

    if str(statuses.get("Q33") or "") == "Answered":
        if not _records(payload.get("management_profiles")):
            blockers.append("Q33 chưa có Management Profile / manager identity evidence.")
        analyst_class = str((payload.get("q33") or {}).get("analyst_classification") or "Unknown")
        if analyst_class == "Unknown" and str(payload.get("final_management_classification") or "Unknown") == "Unknown" and not accepted_unknown_for_question(payload, "Q33"):
            blockers.append("Q33 chưa có analyst classification hoặc accepted residual unknown.")

    if str(statuses.get("Q34") or "") == "Answered":
        applicable = str((payload.get("q34") or {}).get("applicable") or "Unknown")
        if applicable not in {"No", "N/A"} and not _records(payload.get("outside_transitions")) and not accepted_unknown_for_question(payload, "Q34"):
            blockers.append("Q34 chưa có outside-management transition evidence hoặc accepted residual unknown.")

    if str(statuses.get("Q35") or "") == "Answered":
        if not _lion_matrix_valid(payload):
            blockers.append("Q35 phải giữ đúng đủ 7 dimensions của Table 7.1.")
        if str((payload.get("q35") or {}).get("overall_classification") or "Unknown") == "Unknown" and not accepted_unknown_for_question(payload, "Q35"):
            blockers.append("Q35 overall analyst classification còn Unknown mà chưa accepted residual unknown.")

    if str(statuses.get("Q36") or "") == "Answered" and not _records(payload.get("career_timeline")) and not accepted_unknown_for_question(payload, "Q36"):
        blockers.append("Q36 Career Timeline còn trống và chưa có accepted residual unknown.")

    if str(statuses.get("Q37") or "") == "Answered":
        if (not _records(payload.get("compensation_history")) or not _records(payload.get("ownership_history"))) and not accepted_unknown_for_question(payload, "Q37"):
            blockers.append("Q37 cần Compensation + Ownership evidence hoặc accepted residual unknown.")

    if str(statuses.get("Q38") or "") == "Answered" and not _records(payload.get("insider_transactions")) and not accepted_unknown_for_question(payload, "Q38"):
        blockers.append("Q38 chưa có Insider Transaction evidence và chưa có accepted residual unknown.")

    if not _checklist_complete(payload):
        blockers.append("Final Source-Locked Checklist 7K01–7K17 chưa Covered/N/A đầy đủ.")

    open_gaps = [row for row in _records(payload.get("research_gaps_table")) if not _gap_closed(row)]
    if open_gaps:
        blockers.append(f"Còn {len(open_gaps)} Research Gap chưa Closed/Resolved/Accepted/N/A.")

    residual = _records(payload.get("chapter7_residual_unknowns"))
    unresolved_residual = [row for row in residual if str(row.get("Status") or "Open") == "Open"]
    if unresolved_residual:
        blockers.append(f"Còn {len(unresolved_residual)} Residual Unknown ở trạng thái Open.")

    unresolved_conflicts = [row for row in (open_conflicts or []) if str(row.get("status") or "Needs analyst review") == "Needs analyst review"]
    if unresolved_conflicts:
        blockers.append(f"Còn {len(unresolved_conflicts)} source/data conflict cần analyst review.")

    pending_reviews = [row for row in (open_review_items or []) if str(row.get("status") or "Open") == "Open"]
    if pending_reviews:
        blockers.append(f"Còn {len(pending_reviews)} management event review item chưa review.")

    if not str(payload.get("analyst_summary") or "").strip():
        blockers.append("Final analyst management background summary còn trống.")

    if str(payload.get("final_management_classification") or "Unknown") == "Unknown":
        warnings.append("Final Management Classification vẫn Unknown; chỉ chấp nhận khi analyst đã document residual uncertainty phù hợp.")

    confirmed = bool(payload.get("chapter7_complete_confirmed"))
    ready = not blockers
    if confirmed and pending_reviews:
        status = "Complete — Review Required"
    elif confirmed and ready:
        status = "Complete — Analyst Confirmed"
    elif ready:
        status = "Ready for Analyst Confirmation"
    elif any(str(statuses.get(q) or "Unknown") != "Unknown" for q in QUESTION_KEYS):
        status = "In Progress"
    else:
        status = "Not Started"
    return {
        "status": status,
        "ready": ready,
        "confirmed": confirmed,
        "blockers": blockers,
        "warnings": warnings,
        "completion_boundary": CLOSURE_BOUNDARY,
    }


def mark_residual_unknown_accepted(row: dict[str, Any], reason: str) -> dict[str, Any]:
    out = dict(row)
    out["Status"] = "Accepted Residual Unknown"
    out["Accepted By Analyst"] = True
    out["Accepted At"] = _now()
    out["Acceptance Reason"] = str(reason or out.get("Acceptance Reason") or "").strip()
    return out


__all__ = [
    "CLOSURE_BOUNDARY",
    "FINAL_CHECKLIST_STATUS_OPTIONS",
    "FINAL_CHECKLIST_COLUMNS",
    "RESIDUAL_UNKNOWN_STATUS_OPTIONS",
    "RESIDUAL_UNKNOWN_COLUMNS",
    "FINAL_CHECKLIST_ITEMS",
    "default_final_checklist_rows",
    "accepted_unknown_for_question",
    "source_coverage_matrix",
    "career_coverage_audit",
    "compensation_ownership_reconciliation",
    "insider_context_audit",
    "chapter7_completion_status",
    "mark_residual_unknown_accepted",
]
