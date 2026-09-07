from __future__ import annotations

"""Chapter 9 Phase 9H — consolidated report and snapshot delta review.

This module is intentionally descriptive. It exposes analyst-owned Chapter 9 state to the
printable consolidated report and compares two immutable workspace payloads. A delta means that
recorded research state changed; it never means management became better/worse and it never
creates a management score, character classification, MOS/Research Gate change, or
BUY/HOLD/SELL signal.

Source / ownership boundaries
-----------------------------
- Q48-Q52 and the 26 Phase 9B source dimensions remain source-locked.
- Chapter 7 manager master remains the manager identity/role SSOT.
- Analyst Assessment, Research Status and Confidence are displayed verbatim and never rewritten.
- Evidence/gap/event deltas are set/history changes only; additions are not automatically positive
  and removals are not automatically negative.
- Completion deltas reuse Phase 9G research-closure semantics only.
"""

from copy import deepcopy
from hashlib import sha1
from typing import Any
import json

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
from modules.deep_company_analysis.chapter9_completion import (
    build_dimension_closure,
    build_question_completion,
    completion_snapshot,
)
from modules.deep_company_analysis.chapter9_workspace import WORKSPACE_EVIDENCE_COLUMNS


HISTORY_BOUNDARY = (
    "Snapshot/history delta review only — descriptive changes in analyst-owned research records; "
    "not a Management Quality Score, character classification, investment signal, MOS change, "
    "investment Research Gate, or BUY/HOLD/SELL."
)

QUESTION_REPORT_COLUMNS = [
    "Question",
    "Question Title",
    "Research Status",
    "Analyst Confidence",
    "Analyst Assessment",
    "Source Dimensions",
    "Closed Dimensions",
    "Review Dimensions",
    "Open / Blocked Dimensions",
    "Completion Status",
]

QUESTION_DELTA_COLUMNS = ["Question", "Field", "Before", "After", "Change Type"]
EVIDENCE_DELTA_COLUMNS = [
    "Change",
    "Question",
    "Dimension Key",
    "Manager ID",
    "Manager",
    "Evidence / Reference",
    "Source URL / File",
]
GAP_DELTA_COLUMNS = [
    "Change",
    "Question",
    "Dimension Key",
    "Manager ID",
    "Research Gap",
    "Before Status",
    "After Status",
]
EVENT_DELTA_COLUMNS = [
    "Change",
    "Event Date",
    "Manager ID",
    "Manager",
    "Context / Situation",
    "Source",
]
CLOSURE_DELTA_COLUMNS = [
    "Question",
    "Dimension Key",
    "Before Closure",
    "After Closure",
    "Change",
]

_CLOSED_PREFIXES = ("closed", "resolved", "done", "completed", "n/a", "na")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    return []


def _frame(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def _canonical_json(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _fingerprint(row: dict[str, Any]) -> str:
    return sha1(_canonical_json(row).encode("utf-8", errors="ignore")).hexdigest()


def _evidence_identity(row: dict[str, Any]) -> str:
    candidate_id = _text(row.get("Candidate ID"))
    if candidate_id:
        return f"candidate:{candidate_id}"
    parts = [
        _text(row.get("Question")),
        _text(row.get("Dimension Key")),
        _text(row.get("Manager ID")),
        _text(row.get("Source URL / File")),
        _text(row.get("Evidence Text / Reference")),
        _text(row.get("Observation / Claim")),
    ]
    return "manual:" + sha1("|".join(parts).encode("utf-8", errors="ignore")).hexdigest()


def _gap_identity(row: dict[str, Any]) -> str:
    parts = [
        _text(row.get("Question")),
        _text(row.get("Dimension Key")),
        _text(row.get("Manager ID")),
        _text(row.get("Research Gap")),
    ]
    return sha1("|".join(parts).encode("utf-8", errors="ignore")).hexdigest()


def _event_identity(row: dict[str, Any]) -> str:
    parts = [
        _text(row.get("Event Date")),
        _text(row.get("Manager ID")),
        _text(row.get("Context / Situation")),
        _text(row.get("Source")),
    ]
    return sha1("|".join(parts).encode("utf-8", errors="ignore")).hexdigest()


def _index_unique(rows: list[dict[str, Any]], identity_fn) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    collisions: dict[str, int] = {}
    for row in rows:
        base = identity_fn(row)
        key = base
        if key in indexed:
            collisions[base] = collisions.get(base, 1) + 1
            key = f"{base}#{collisions[base]}"
        indexed[key] = dict(row)
    return indexed


def _is_closed_status(value: Any) -> bool:
    key = _text(value).casefold()
    return any(key.startswith(prefix) for prefix in _CLOSED_PREFIXES)


def build_chapter9_summary(
    payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build report-level completeness metadata; never a management-quality score."""
    data = ch9.normalize_payload(payload or {})
    statuses = data.get("question_status") or {}
    assessments = data.get("analyst_assessment") or {}
    confidence = data.get("confidence") or {}
    evidence = _rows(data.get("evidence"))
    gaps = _rows(data.get("research_gaps"))
    completion = completion_snapshot(data, chapter7_payload)

    counts = {status: 0 for status in ch9.QUESTION_STATUS_OPTIONS}
    for question in ch9.QUESTION_KEYS:
        status = _text(statuses.get(question)) or "Unknown"
        if status not in counts:
            status = "Unknown"
        counts[status] += 1

    return {
        "total_questions": len(ch9.QUESTION_KEYS),
        "answered": counts["Answered"],
        "partial": counts["Partial"],
        "unknown": counts["Unknown"],
        "not_applicable": counts["N/A"],
        "analyst_conclusions": sum(
            1 for q in ch9.QUESTION_KEYS if _text(assessments.get(q)) not in {"", "Unknown"}
        ),
        "confidence_known": sum(
            1 for q in ch9.QUESTION_KEYS if _text(confidence.get(q)) not in {"", "Unknown"}
        ),
        "evidence_rows": len(evidence),
        "research_gaps_total": len(gaps),
        "research_gaps_open": sum(1 for row in gaps if not _is_closed_status(row.get("Status"))),
        "source_dimension_count": completion["source_dimension_count"],
        "closed_dimensions": completion["closed_dimensions"],
        "review_dimensions": completion["review_dimensions"],
        "open_dimensions": completion["open_dimensions"],
        "blocked_dimensions": completion["blocked_dimensions"],
        "ready_questions": completion["ready_questions"],
        "research_completion_gate": completion["research_completion_gate"],
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
    }


def build_question_report(
    payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None = None,
) -> pd.DataFrame:
    data = ch9.normalize_payload(payload or {})
    completion = build_question_completion(data, chapter7_payload).set_index("Question")
    rows: list[dict[str, Any]] = []
    for question in ch9.QUESTION_KEYS:
        comp = completion.loc[question] if question in completion.index else {}
        rows.append(
            {
                "Question": question,
                "Question Title": ch9.QUESTION_TITLES[question],
                "Research Status": _text((data.get("question_status") or {}).get(question)) or "Unknown",
                "Analyst Confidence": _text((data.get("confidence") or {}).get(question)) or "Unknown",
                "Analyst Assessment": _text((data.get("analyst_assessment") or {}).get(question)) or "Unknown",
                "Source Dimensions": int(comp.get("Source Dimensions", 0)) if hasattr(comp, "get") else 0,
                "Closed Dimensions": int(comp.get("Closed Dimensions", 0)) if hasattr(comp, "get") else 0,
                "Review Dimensions": int(comp.get("Review Dimensions", 0)) if hasattr(comp, "get") else 0,
                "Open / Blocked Dimensions": int(comp.get("Open / Blocked Dimensions", 0)) if hasattr(comp, "get") else 0,
                "Completion Status": _text(comp.get("Completion Status")) if hasattr(comp, "get") else "",
            }
        )
    return pd.DataFrame(rows, columns=QUESTION_REPORT_COLUMNS)


def build_chapter9_report_frames(
    payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    data = ch9.normalize_payload(payload or {})
    return {
        "questions": build_question_report(data, chapter7_payload),
        "dimension_closure": build_dimension_closure(data, chapter7_payload),
        "evidence": _frame(_rows(data.get("evidence")), list(WORKSPACE_EVIDENCE_COLUMNS)),
        "research_gaps": _frame(
            _rows(data.get("research_gaps")),
            [
                "Question", "Dimension Key", "Manager ID", "Manager", "Research Gap",
                "Materiality", "Next Action", "Status", "Analyst Note",
            ],
        ),
        "behavior_events": _frame(_rows(data.get("behavior_events")), list(ch9.BEHAVIOR_EVENT_COLUMNS)),
        "q48_passion_research": _frame(
            _rows(data.get("q48_passion_research")), list(ch9.Q48_PASSION_COLUMNS)
        ),
    }


def _question_delta(before: dict[str, Any], after: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    fields = [
        ("Research Status", "question_status"),
        ("Analyst Confidence", "confidence"),
        ("Analyst Assessment", "analyst_assessment"),
    ]
    for question in ch9.QUESTION_KEYS:
        for label, key in fields:
            left = _text((before.get(key) or {}).get(question)) or "Unknown"
            right = _text((after.get(key) or {}).get(question)) or "Unknown"
            if left != right:
                rows.append(
                    {
                        "Question": question,
                        "Field": label,
                        "Before": left,
                        "After": right,
                        "Change Type": "Changed",
                    }
                )
    return pd.DataFrame(rows, columns=QUESTION_DELTA_COLUMNS)


def _evidence_delta(before: dict[str, Any], after: dict[str, Any]) -> pd.DataFrame:
    left = _index_unique(_rows(before.get("evidence")), _evidence_identity)
    right = _index_unique(_rows(after.get("evidence")), _evidence_identity)
    rows: list[dict[str, Any]] = []
    for key in sorted(set(left) | set(right)):
        old = left.get(key)
        new = right.get(key)
        if old is None:
            change, row = "Added", new or {}
        elif new is None:
            change, row = "Removed", old
        elif _fingerprint(old) != _fingerprint(new):
            change, row = "Changed", new
        else:
            continue
        rows.append(
            {
                "Change": change,
                "Question": _text(row.get("Question")),
                "Dimension Key": _text(row.get("Dimension Key")),
                "Manager ID": _text(row.get("Manager ID")),
                "Manager": _text(row.get("Manager")),
                "Evidence / Reference": _text(
                    row.get("Evidence Text / Reference") or row.get("Observation / Claim")
                ),
                "Source URL / File": _text(row.get("Source URL / File")),
            }
        )
    return pd.DataFrame(rows, columns=EVIDENCE_DELTA_COLUMNS)


def _gap_delta(before: dict[str, Any], after: dict[str, Any]) -> pd.DataFrame:
    left = _index_unique(_rows(before.get("research_gaps")), _gap_identity)
    right = _index_unique(_rows(after.get("research_gaps")), _gap_identity)
    rows: list[dict[str, Any]] = []
    for key in sorted(set(left) | set(right)):
        old = left.get(key)
        new = right.get(key)
        old_status = _text((old or {}).get("Status"))
        new_status = _text((new or {}).get("Status"))
        if old is None:
            change, row = "Added", new or {}
        elif new is None:
            change, row = "Removed", old
        elif old_status != new_status:
            if not _is_closed_status(old_status) and _is_closed_status(new_status):
                change = "Closed"
            elif _is_closed_status(old_status) and not _is_closed_status(new_status):
                change = "Reopened"
            else:
                change = "Status changed"
            row = new
        elif _fingerprint(old) != _fingerprint(new):
            change, row = "Changed", new
        else:
            continue
        rows.append(
            {
                "Change": change,
                "Question": _text(row.get("Question")),
                "Dimension Key": _text(row.get("Dimension Key")),
                "Manager ID": _text(row.get("Manager ID")),
                "Research Gap": _text(row.get("Research Gap")),
                "Before Status": old_status,
                "After Status": new_status,
            }
        )
    return pd.DataFrame(rows, columns=GAP_DELTA_COLUMNS)


def _event_delta(before: dict[str, Any], after: dict[str, Any]) -> pd.DataFrame:
    left = _index_unique(_rows(before.get("behavior_events")), _event_identity)
    right = _index_unique(_rows(after.get("behavior_events")), _event_identity)
    rows: list[dict[str, Any]] = []
    for key in sorted(set(left) | set(right)):
        old = left.get(key)
        new = right.get(key)
        if old is None:
            change, row = "Added", new or {}
        elif new is None:
            change, row = "Removed", old
        elif _fingerprint(old) != _fingerprint(new):
            change, row = "Changed", new
        else:
            continue
        rows.append(
            {
                "Change": change,
                "Event Date": _text(row.get("Event Date")),
                "Manager ID": _text(row.get("Manager ID")),
                "Manager": _text(row.get("Manager")),
                "Context / Situation": _text(row.get("Context / Situation")),
                "Source": _text(row.get("Source")),
            }
        )
    return pd.DataFrame(rows, columns=EVENT_DELTA_COLUMNS)


def _closure_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    chapter7_payload: dict[str, Any] | None,
) -> pd.DataFrame:
    left = build_dimension_closure(before, chapter7_payload).set_index("Dimension Key")
    right = build_dimension_closure(after, chapter7_payload).set_index("Dimension Key")
    rows: list[dict[str, Any]] = []
    for dimension_key in [dim.key for dim in __import__(
        "modules.deep_company_analysis.chapter9_source_contract_v63", fromlist=["all_dimensions"]
    ).all_dimensions()]:
        if dimension_key not in left.index or dimension_key not in right.index:
            continue
        old = _text(left.loc[dimension_key, "Closure Status"])
        new = _text(right.loc[dimension_key, "Closure Status"])
        if old == new:
            continue
        if not old.startswith("Closed") and new.startswith("Closed"):
            change = "Newly closed"
        elif old.startswith("Closed") and not new.startswith("Closed"):
            change = "Reopened / no longer closed"
        else:
            change = "Closure status changed"
        rows.append(
            {
                "Question": _text(right.loc[dimension_key, "Question"]),
                "Dimension Key": dimension_key,
                "Before Closure": old,
                "After Closure": new,
                "Change": change,
            }
        )
    return pd.DataFrame(rows, columns=CLOSURE_DELTA_COLUMNS)


def compare_chapter9_payloads(
    before_payload: dict[str, Any] | None,
    after_payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare two Chapter 9 payloads without mutating either input or interpreting quality."""
    before_input = deepcopy(before_payload) if isinstance(before_payload, dict) else {}
    after_input = deepcopy(after_payload) if isinstance(after_payload, dict) else {}
    before = ch9.normalize_payload(before_input)
    after = ch9.normalize_payload(after_input)

    question_delta = _question_delta(before, after)
    evidence_delta = _evidence_delta(before, after)
    gap_delta = _gap_delta(before, after)
    event_delta = _event_delta(before, after)
    closure_delta = _closure_delta(before, after, chapter7_payload)

    before_completion = completion_snapshot(before, chapter7_payload)
    after_completion = completion_snapshot(after, chapter7_payload)
    summary = {
        "question_field_changes": len(question_delta),
        "evidence_added": int((evidence_delta["Change"] == "Added").sum()) if not evidence_delta.empty else 0,
        "evidence_removed": int((evidence_delta["Change"] == "Removed").sum()) if not evidence_delta.empty else 0,
        "evidence_changed": int((evidence_delta["Change"] == "Changed").sum()) if not evidence_delta.empty else 0,
        "gaps_added": int((gap_delta["Change"] == "Added").sum()) if not gap_delta.empty else 0,
        "gaps_closed": int((gap_delta["Change"] == "Closed").sum()) if not gap_delta.empty else 0,
        "gaps_reopened": int((gap_delta["Change"] == "Reopened").sum()) if not gap_delta.empty else 0,
        "behavior_event_changes": len(event_delta),
        "closure_status_changes": len(closure_delta),
        "dimensions_newly_closed": int((closure_delta["Change"] == "Newly closed").sum()) if not closure_delta.empty else 0,
        "dimensions_reopened": int((closure_delta["Change"] == "Reopened / no longer closed").sum()) if not closure_delta.empty else 0,
        "before_research_completion_gate": before_completion["research_completion_gate"],
        "after_research_completion_gate": after_completion["research_completion_gate"],
        "manager_scope_basis": ch9.MANAGER_IDENTITY_SSOT,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
    }
    return {
        "summary": summary,
        "question_delta": question_delta,
        "evidence_delta": evidence_delta,
        "gap_delta": gap_delta,
        "behavior_event_delta": event_delta,
        "closure_delta": closure_delta,
    }


__all__ = [
    "CLOSURE_DELTA_COLUMNS",
    "EVIDENCE_DELTA_COLUMNS",
    "EVENT_DELTA_COLUMNS",
    "GAP_DELTA_COLUMNS",
    "HISTORY_BOUNDARY",
    "QUESTION_DELTA_COLUMNS",
    "QUESTION_REPORT_COLUMNS",
    "build_chapter9_report_frames",
    "build_chapter9_summary",
    "build_question_report",
    "compare_chapter9_payloads",
]
