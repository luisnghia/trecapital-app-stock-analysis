from __future__ import annotations

"""Phase 9L — cross-snapshot history/delta review for analyst-owned management synthesis.

This module compares stored Management Synthesis versions and builds version lineage using only
metadata actually persisted in immutable snapshots/current workspace payloads. A delta means the
analyst record changed; it never means management improved/worsened and it never creates a
Management Quality Score, character classification, investment signal, MOS change, investment
Research Gate, portfolio-sizing input, or BUY/HOLD/SELL recommendation.

Historical source freshness is deliberately NOT reconstructed from today's Chapter 7–9 records.
Only the source baseline fingerprint and explicit review/re-review metadata stored in each version
are shown. This keeps version history auditable without fabricating historical context.
"""

from copy import deepcopy
from typing import Any, Iterable
import json

import pandas as pd

from modules.deep_company_analysis.chapter9_synthesis_workspace import normalize_synthesis_workspace


SYNTHESIS_HISTORY_BOUNDARY = (
    "Analyst-synthesis history/delta only — compares stored versions and source-baseline lineage; "
    "not a Management Quality Score, character classification, investment signal, MOS change, "
    "investment Research Gate, portfolio sizing, or BUY/HOLD/SELL."
)

SYNTHESIS_FIELD_SPECS: tuple[tuple[str, str], ...] = (
    ("Synthesis Status", "workspace_status"),
    ("Analyst Confidence", "analyst_confidence"),
    ("Chapter 7 Background Takeaway", "chapter7_background_takeaway"),
    ("Chapter 8 Operating Competence Takeaway", "chapter8_operating_takeaway"),
    ("Chapter 9 Management Traits Takeaway", "chapter9_traits_takeaway"),
    ("Management Strengths", "management_strengths"),
    ("Management Concerns", "management_concerns"),
    ("Material Management Unknowns", "management_unknowns"),
    ("Evidence That Would Change View", "evidence_that_would_change_view"),
    ("Final Analyst Management Synthesis", "final_management_synthesis"),
    ("Analyst Note", "analyst_note"),
    ("Source Baseline Fingerprint", "source_fingerprint"),
    ("Source Counts", "source_counts"),
    ("Source Handoff State", "source_handoff_state"),
    ("Source Captured At", "source_captured_at"),
    ("Analyst Reviewed At", "analyst_reviewed_at"),
    ("Last Re-review At", "last_re_review_at"),
    ("Last Re-review Note", "last_re_review_note"),
    ("Last Re-review Sections", "last_re_review_sections"),
)

SYNTHESIS_DELTA_COLUMNS = [
    "Field",
    "Before Version",
    "Before",
    "After Version",
    "After",
    "Delta",
]

VERSION_LINEAGE_COLUMNS = [
    "Version",
    "Snapshot ID",
    "Created At",
    "Schema Version",
    "Synthesis Status",
    "Analyst Confidence",
    "Source Baseline",
    "Source Captured At",
    "Analyst Reviewed At",
    "Last Re-review At",
    "Last Re-review Sections",
    "Final Synthesis Present",
]


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonical(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return _text(value)


def _display_value(key: str, value: Any) -> str:
    if key == "source_fingerprint":
        return _text(value)[:16]
    if key == "last_re_review_sections":
        if isinstance(value, (list, tuple)):
            return ", ".join(_text(item) for item in value if _text(item))
        return _text(value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(item) for item in value if _text(item))
    return _text(value)


def _change_type(before: Any, after: Any) -> str:
    left = _canonical(before)
    right = _canonical(after)
    if left == right:
        return "Unchanged"
    if not left and right:
        return "Added"
    if left and not right:
        return "Removed"
    return "Changed"


def compare_synthesis_versions(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    *,
    before_label: str = "Before",
    after_label: str = "After",
) -> pd.DataFrame:
    """Compare two stored analyst synthesis payloads without mutating either input."""
    left = normalize_synthesis_workspace(deepcopy(before or {}))
    right = normalize_synthesis_workspace(deepcopy(after or {}))
    rows: list[dict[str, Any]] = []
    for label, key in SYNTHESIS_FIELD_SPECS:
        rows.append(
            {
                "Field": label,
                "Before Version": _text(before_label) or "Before",
                "Before": _display_value(key, left.get(key)),
                "After Version": _text(after_label) or "After",
                "After": _display_value(key, right.get(key)),
                "Delta": _change_type(left.get(key), right.get(key)),
            }
        )
    return pd.DataFrame(rows, columns=SYNTHESIS_DELTA_COLUMNS)


def build_version_lineage(records: Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    """Build deterministic immutable-snapshot lineage from supplied snapshot metadata/payloads.

    Expected record shape: {snapshot_id/id, created_at, schema_version, payload}. Missing metadata is
    left blank rather than inferred. Records are sorted oldest-to-newest by created_at then ID.
    """
    normalized_records: list[dict[str, Any]] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        payload = normalize_synthesis_workspace(deepcopy(record.get("payload") or {}))
        snapshot_id = record.get("snapshot_id", record.get("id", ""))
        try:
            numeric_id = int(snapshot_id)
        except Exception:
            numeric_id = 0
        normalized_records.append(
            {
                "snapshot_id": snapshot_id,
                "numeric_id": numeric_id,
                "created_at": _text(record.get("created_at")),
                "schema_version": record.get("schema_version", payload.get("schema_version", "")),
                "payload": payload,
            }
        )

    normalized_records.sort(key=lambda item: (item["created_at"], item["numeric_id"]))
    rows: list[dict[str, Any]] = []
    for record in normalized_records:
        payload = record["payload"]
        snapshot_id = record["snapshot_id"]
        rows.append(
            {
                "Version": f"Snapshot #{snapshot_id}" if _text(snapshot_id) else "Snapshot",
                "Snapshot ID": snapshot_id,
                "Created At": record["created_at"],
                "Schema Version": record["schema_version"],
                "Synthesis Status": payload.get("workspace_status") or "Draft",
                "Analyst Confidence": payload.get("analyst_confidence") or "Unknown",
                "Source Baseline": _text(payload.get("source_fingerprint"))[:16],
                "Source Captured At": _text(payload.get("source_captured_at")),
                "Analyst Reviewed At": _text(payload.get("analyst_reviewed_at")),
                "Last Re-review At": _text(payload.get("last_re_review_at")),
                "Last Re-review Sections": _display_value(
                    "last_re_review_sections", payload.get("last_re_review_sections")
                ),
                "Final Synthesis Present": "Yes" if _text(payload.get("final_management_synthesis")) else "No",
            }
        )
    return pd.DataFrame(rows, columns=VERSION_LINEAGE_COLUMNS)


def synthesis_history_summary(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return descriptive delta counts only; no management/investment interpretation."""
    left = normalize_synthesis_workspace(deepcopy(before or {}))
    right = normalize_synthesis_workspace(deepcopy(after or {}))
    delta = compare_synthesis_versions(left, right)
    counts = delta["Delta"].value_counts().to_dict() if not delta.empty else {}
    changed_rows = int(sum(int(counts.get(state, 0)) for state in ("Added", "Removed", "Changed")))
    return {
        "tracked_fields": len(SYNTHESIS_FIELD_SPECS),
        "changed_fields": changed_rows,
        "unchanged_fields": int(counts.get("Unchanged", 0)),
        "added_fields": int(counts.get("Added", 0)),
        "removed_fields": int(counts.get("Removed", 0)),
        "modified_fields": int(counts.get("Changed", 0)),
        "status_changed": _canonical(left.get("workspace_status")) != _canonical(right.get("workspace_status")),
        "confidence_changed": _canonical(left.get("analyst_confidence")) != _canonical(right.get("analyst_confidence")),
        "final_synthesis_changed": _canonical(left.get("final_management_synthesis")) != _canonical(right.get("final_management_synthesis")),
        "source_baseline_changed": _canonical(left.get("source_fingerprint")) != _canonical(right.get("source_fingerprint")),
        "historical_source_freshness_reconstructed": False,
        "automatic_workspace_status_change": False,
        "automatic_confidence_change": False,
        "automatic_analyst_text_change": False,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
        "boundary": SYNTHESIS_HISTORY_BOUNDARY,
    }


__all__ = [
    "SYNTHESIS_DELTA_COLUMNS",
    "SYNTHESIS_FIELD_SPECS",
    "SYNTHESIS_HISTORY_BOUNDARY",
    "VERSION_LINEAGE_COLUMNS",
    "build_version_lineage",
    "compare_synthesis_versions",
    "synthesis_history_summary",
]
