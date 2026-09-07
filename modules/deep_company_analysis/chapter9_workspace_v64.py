from __future__ import annotations

"""Chapter 9 Phase 9C — pure analyst-workspace kernel for Q48-Q52.

This module turns the V63 source contract into editable, source-locked research rows.
It deliberately stays outside Streamlit, persistence, web research, financial-data bridges,
and investment decision logic. Chapter 7 remains the manager identity/background SSOT.
"""

from copy import deepcopy
from typing import Any

import pandas as pd

from modules.deep_company_analysis import chapter9 as ch9
from modules.deep_company_analysis import chapter9_source_contract_v63 as v63


DIMENSION_STATUS_OPTIONS = (
    "Open — analyst research required",
    "Partial — analyst review",
    "Closed — analyst verified",
    "N/A — analyst verified",
)
CLOSED_DIMENSION_STATUSES = {
    "closed — analyst verified",
    "n/a — analyst verified",
}
ANALYST_EDITABLE_DIMENSION_FIELDS = (
    "Manager ID",
    "Manager",
    "Supporting Evidence",
    "Counter-Evidence",
    "Evidence Status",
    "Source",
    "Analyst Note",
)
SOURCE_LOCKED_DIMENSION_FIELDS = (
    "Question",
    "Dimension Key",
    "Dimension",
    "Source Origin",
    "Source Pages",
)


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    return []


def _dimension_contract_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in v63.default_dimension_rows():
        rows.append(
            {
                "Question": row["Question"],
                "Dimension Key": row["Dimension Key"],
                "Dimension": row["Dimension"],
                "Source Origin": row["Source Origin"],
                "Source Pages": row["Source Pages"],
                "Manager ID": "",
                "Manager": "",
                "Supporting Evidence": "",
                "Counter-Evidence": "",
                "Evidence Status": "Open — analyst research required",
                "Source": "",
                "Analyst Note": "",
            }
        )
    return rows


def _contract_by_key() -> dict[str, dict[str, Any]]:
    return {str(row["Dimension Key"]): row for row in _dimension_contract_rows()}


def _manager_rows(chapter7_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    return _rows((chapter7_payload or {}).get("management_profiles"))


def manager_reference_index(chapter7_payload: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    """Return Chapter 7 manager references keyed by confirmed Manager ID.

    No new manager identity is created here. Rows without a Manager ID are intentionally
    excluded from the ID index, though their names may still be reported by validation.
    """
    out: dict[str, dict[str, str]] = {}
    for row in _manager_rows(chapter7_payload):
        manager_id = str(row.get("Manager ID") or "").strip()
        if not manager_id:
            continue
        out[manager_id] = {
            "Manager ID": manager_id,
            "Manager": str(row.get("Manager") or "").strip(),
            "Current Role": str(row.get("Current Role") or "").strip(),
        }
    return out


def default_dimension_workspace_rows() -> list[dict[str, Any]]:
    """Return all 26 V63 dimensions as neutral analyst-editable rows."""
    return _dimension_contract_rows()


def empty_workspace_payload(ticker: str, company_name: str = "") -> dict[str, Any]:
    payload = ch9.empty_payload(ticker, company_name)
    payload["dimension_evidence"] = default_dimension_workspace_rows()
    payload["workspace_version"] = 64
    payload["workspace_boundary"] = (
        "Analyst-controlled research workspace only; no management score, MOS, Research Gate, or BUY/HOLD/SELL signal."
    )
    return payload


def _normalize_dimension_rows(value: Any) -> list[dict[str, Any]]:
    contract = _contract_by_key()
    incoming = {str(row.get("Dimension Key") or "").strip(): row for row in _rows(value)}
    normalized: list[dict[str, Any]] = []
    for key, source_row in contract.items():
        row = deepcopy(source_row)
        prior = incoming.get(key, {})
        for field in ANALYST_EDITABLE_DIMENSION_FIELDS:
            if field in prior:
                row[field] = deepcopy(prior[field])
        if row["Evidence Status"] not in DIMENSION_STATUS_OPTIONS:
            row["Evidence Status"] = "Open — analyst research required"
        row["Manager ID"] = str(row.get("Manager ID") or "").strip()
        row["Manager"] = str(row.get("Manager") or "").strip()
        normalized.append(row)
    return normalized


def normalize_workspace_payload(
    payload: dict[str, Any] | None,
    *,
    ticker: str = "",
    company_name: str = "",
) -> dict[str, Any]:
    base = ch9.normalize_payload(payload, ticker=ticker, company_name=company_name)
    source = payload if isinstance(payload, dict) else {}
    out = deepcopy(base)
    out["dimension_evidence"] = _normalize_dimension_rows(source.get("dimension_evidence"))
    out["workspace_version"] = 64
    out["workspace_boundary"] = (
        "Analyst-controlled research workspace only; no management score, MOS, Research Gate, or BUY/HOLD/SELL signal."
    )
    return out


def validate_manager_scope(
    payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Return manager-link issues without auto-fixing or inventing an identity."""
    data = normalize_workspace_payload(payload)
    manager_index = manager_reference_index(chapter7_payload)
    chapter7_rows = _manager_rows(chapter7_payload)
    names = {
        str(row.get("Manager") or "").strip(): str(row.get("Manager ID") or "").strip()
        for row in chapter7_rows
        if str(row.get("Manager") or "").strip()
    }
    issues: list[dict[str, str]] = []
    for row in data["dimension_evidence"]:
        manager_id = str(row.get("Manager ID") or "").strip()
        manager = str(row.get("Manager") or "").strip()
        if manager_id and manager_id not in manager_index:
            issues.append(
                {
                    "Question": str(row.get("Question") or ""),
                    "Dimension Key": str(row.get("Dimension Key") or ""),
                    "Issue": f"Manager ID '{manager_id}' is not present in Chapter 7 manager master.",
                }
            )
            continue
        if manager_id and manager:
            expected = manager_index.get(manager_id, {}).get("Manager", "")
            if expected and manager != expected:
                issues.append(
                    {
                        "Question": str(row.get("Question") or ""),
                        "Dimension Key": str(row.get("Dimension Key") or ""),
                        "Issue": f"Manager name '{manager}' does not match Chapter 7 Manager ID '{manager_id}'.",
                    }
                )
        elif manager and manager in names and names[manager] and not manager_id:
            issues.append(
                {
                    "Question": str(row.get("Question") or ""),
                    "Dimension Key": str(row.get("Dimension Key") or ""),
                    "Issue": f"Manager '{manager}' has a Chapter 7 Manager ID but this row is not linked to it.",
                }
            )
    return issues


def apply_dimension_edits(
    payload: dict[str, Any] | None,
    edits: pd.DataFrame | list[dict[str, Any]],
    *,
    chapter7_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int, list[str]]:
    """Apply analyst edits while keeping all V63 source-contract fields immutable."""
    out = normalize_workspace_payload(payload)
    contract = _contract_by_key()
    rows_by_key = {str(row["Dimension Key"]): row for row in out["dimension_evidence"]}
    manager_index = manager_reference_index(chapter7_payload)
    validate_manager_ids = chapter7_payload is not None
    applied = 0
    rejected: list[str] = []

    for edit in _rows(edits):
        key = str(edit.get("Dimension Key") or "").strip()
        if key not in contract:
            rejected.append(f"Unknown Dimension Key: {key or '<blank>'}")
            continue
        candidate = deepcopy(rows_by_key[key])
        for field in ANALYST_EDITABLE_DIMENSION_FIELDS:
            if field in edit:
                candidate[field] = deepcopy(edit[field])
        status = str(candidate.get("Evidence Status") or "").strip()
        if status not in DIMENSION_STATUS_OPTIONS:
            rejected.append(f"{key}: invalid Evidence Status '{status}'")
            continue
        candidate["Manager ID"] = str(candidate.get("Manager ID") or "").strip()
        candidate["Manager"] = str(candidate.get("Manager") or "").strip()
        if validate_manager_ids and candidate["Manager ID"]:
            ref = manager_index.get(candidate["Manager ID"])
            if not ref:
                rejected.append(f"{key}: Manager ID '{candidate['Manager ID']}' is not in Chapter 7 manager master")
                continue
            if candidate["Manager"] and ref.get("Manager") and candidate["Manager"] != ref["Manager"]:
                rejected.append(f"{key}: manager name does not match Chapter 7 Manager ID '{candidate['Manager ID']}'")
                continue
        for field in SOURCE_LOCKED_DIMENSION_FIELDS:
            candidate[field] = deepcopy(contract[key][field])
        rows_by_key[key] = candidate
        applied += 1

    out["dimension_evidence"] = [rows_by_key[str(row["Dimension Key"])] for row in _dimension_contract_rows()]
    return out, applied, rejected


def _gap_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("Question") or "").strip(),
        str(row.get("Manager ID") or "").strip(),
        str(row.get("Research Gap") or "").strip(),
        str(row.get("Status") or "").strip(),
    )


def merge_research_gaps(
    payload: dict[str, Any] | None,
    gaps: pd.DataFrame | list[dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    """Merge machine/analyst gap rows without overwriting existing analyst edits."""
    out = normalize_workspace_payload(payload)
    existing = [dict(row) for row in _rows(out.get("research_gaps"))]
    keys = {_gap_key(row) for row in existing}
    added = 0
    for row in _rows(gaps):
        normalized = {column: row.get(column, "") for column in ch9.RESEARCH_GAP_COLUMNS}
        key = _gap_key(normalized)
        if key in keys:
            continue
        existing.append(normalized)
        keys.add(key)
        added += 1
    out["research_gaps"] = existing
    return out, added


def build_open_dimension_gaps(payload: dict[str, Any] | None) -> pd.DataFrame:
    """Project unresolved dimensions into research gaps without mutating the workspace."""
    data = normalize_workspace_payload(payload)
    rows: list[dict[str, Any]] = []
    for row in data["dimension_evidence"]:
        status = str(row.get("Evidence Status") or "").strip().casefold()
        if status in CLOSED_DIMENSION_STATUSES:
            continue
        rows.append(
            {
                "Question": str(row.get("Question") or ""),
                "Manager ID": str(row.get("Manager ID") or ""),
                "Manager": str(row.get("Manager") or ""),
                "Research Gap": f"Open Chapter 9 dimension: {row.get('Dimension') or row.get('Dimension Key')}",
                "Materiality": "Analyst review required",
                "Next Action": "Collect source evidence and explicitly close or mark N/A after analyst review.",
                "Status": "Open",
                "Analyst Note": "",
            }
        )
    return pd.DataFrame(rows, columns=ch9.RESEARCH_GAP_COLUMNS)


def workspace_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = normalize_workspace_payload(payload)
    counts = {q: 0 for q in ch9.QUESTION_KEYS}
    closed = {q: 0 for q in ch9.QUESTION_KEYS}
    for row in data["dimension_evidence"]:
        q = str(row.get("Question") or "")
        counts[q] += 1
        if str(row.get("Evidence Status") or "").strip().casefold() in CLOSED_DIMENSION_STATUSES:
            closed[q] += 1
    return {
        "workspace_version": 64,
        "question_keys": list(ch9.QUESTION_KEYS),
        "dimension_counts": counts,
        "closed_dimension_counts": closed,
        "total_dimensions": sum(counts.values()),
        "manager_identity_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
    }


__all__ = [
    "ANALYST_EDITABLE_DIMENSION_FIELDS",
    "CLOSED_DIMENSION_STATUSES",
    "DIMENSION_STATUS_OPTIONS",
    "SOURCE_LOCKED_DIMENSION_FIELDS",
    "apply_dimension_edits",
    "build_open_dimension_gaps",
    "default_dimension_workspace_rows",
    "empty_workspace_payload",
    "manager_reference_index",
    "merge_research_gaps",
    "normalize_workspace_payload",
    "validate_manager_scope",
    "workspace_snapshot",
]
