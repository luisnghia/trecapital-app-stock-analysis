from __future__ import annotations

"""Chapter 10 Phase 10G / V80 — immutable snapshot history, delta and explicit re-review.

This module compares stored analyst-owned Chapter 10 workspace versions. A delta only means the
research record changed. It does not mean growth quality improved/worsened and never creates a
growth score, forecast, valuation conclusion, MOS change, investment Research Gate change, or
BUY/HOLD/SELL signal.

Historical source freshness is never reconstructed from today's data. Version lineage only shows
metadata actually persisted with a snapshot/current workspace.
"""

from copy import deepcopy
from typing import Any, Iterable
import hashlib
import json

import pandas as pd

import modules.deep_company_analysis.chapter10 as ch10

HISTORY_BOUNDARY = (
    "Analyst-owned Chapter 10 history/delta only; no automatic growth conclusion, growth score, "
    "forecast, valuation, MOS, investment Research Gate, portfolio action, or BUY/HOLD/SELL."
)

SYNTHESIS_FIELDS: tuple[tuple[str, str], ...] = (
    ("Growth Route", "growth_route"),
    ("Historical Growth Profitability", "historical_growth_profitability"),
    ("Growth Runway", "growth_runway"),
    ("Growth Pace & Funding", "growth_pace_and_funding"),
    ("Growth Strengths", "growth_strengths"),
    ("Growth Concerns", "growth_concerns"),
    ("Material Growth Unknowns", "growth_unknowns"),
    ("Evidence That Would Change View", "evidence_that_would_change_view"),
    ("Final Analyst Growth Synthesis", "final_growth_synthesis"),
    ("Analyst Note", "analyst_note"),
    ("Analyst Reviewed At", "analyst_reviewed_at"),
    ("Last Re-review At", "last_re_review_at"),
    ("Last Re-review Note", "last_re_review_note"),
    ("Last Re-review Sections", "last_re_review_sections"),
)

DELTA_COLUMNS = ["Field", "Before Version", "Before", "After Version", "After", "Delta"]
LINEAGE_COLUMNS = [
    "Version", "Snapshot ID", "Created At", "Schema Version", "Research Status",
    "Growth Mode", "Source Baseline", "Analyst Reviewed At", "Last Re-review At",
    "Last Re-review Sections", "Final Synthesis Present",
]


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonical(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    if isinstance(value, (list, tuple, set)):
        return json.dumps(list(value), ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return _text(value)


def source_baseline_fingerprint(payload: dict[str, Any] | None) -> str:
    """Fingerprint source-facing workspace state without copying canonical financial SSOT values."""
    p = ch10.normalize_payload(deepcopy(payload or {}))
    source_state = {
        "question_status": p.get("question_status", {}),
        "confidence": p.get("confidence", {}),
        "dimension_status": p.get("dimension_status", {}),
        "evidence": p.get("evidence", []),
        "research_gaps": p.get("research_gaps", []),
        "growth_events": p.get("growth_events", []),
    }
    raw = json.dumps(source_state, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _synthesis(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    syn = source.get("growth_synthesis") if isinstance(source.get("growth_synthesis"), dict) else {}
    return deepcopy(syn)


def _display(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_text(v) for v in value if _text(v))
    return _text(value)


def _change(before: Any, after: Any) -> str:
    left, right = _canonical(before), _canonical(after)
    if left == right:
        return "Unchanged"
    if not left and right:
        return "Added"
    if left and not right:
        return "Removed"
    return "Changed"


def compare_versions(before: dict[str, Any] | None, after: dict[str, Any] | None, *, before_label: str = "Before", after_label: str = "After") -> pd.DataFrame:
    """Compare analyst-owned Chapter 10 state without changing either payload."""
    left_raw, right_raw = deepcopy(before or {}), deepcopy(after or {})
    left, right = ch10.normalize_payload(left_raw), ch10.normalize_payload(right_raw)
    left_syn, right_syn = _synthesis(left_raw), _synthesis(right_raw)
    specs: list[tuple[str, Any, Any]] = [
        ("Growth Mode", left.get("growth_mode"), right.get("growth_mode")),
    ]
    for q in ch10.QUESTION_KEYS:
        specs.extend([
            (f"{q} Research Status", left.get("question_status", {}).get(q), right.get("question_status", {}).get(q)),
            (f"{q} Confidence", left.get("confidence", {}).get(q), right.get("confidence", {}).get(q)),
            (f"{q} Analyst Assessment", left.get("analyst_assessment", {}).get(q), right.get("analyst_assessment", {}).get(q)),
        ])
    for label, key in SYNTHESIS_FIELDS:
        specs.append((label, left_syn.get(key), right_syn.get(key)))
    specs.append(("Source Baseline Fingerprint", source_baseline_fingerprint(left_raw), source_baseline_fingerprint(right_raw)))
    rows = [{
        "Field": label, "Before Version": _text(before_label) or "Before", "Before": _display(a),
        "After Version": _text(after_label) or "After", "After": _display(b), "Delta": _change(a, b),
    } for label, a, b in specs]
    return pd.DataFrame(rows, columns=DELTA_COLUMNS)


def build_version_lineage(records: Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    normalized: list[dict[str, Any]] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        payload = deepcopy(record.get("payload") or {})
        sid = record.get("snapshot_id", record.get("id", ""))
        normalized.append({
            "snapshot_id": sid,
            "created_at": _text(record.get("created_at")),
            "schema_version": record.get("schema_version", ""),
            "research_status": _text(record.get("research_status")),
            "payload": payload,
        })
    normalized.sort(key=lambda r: (r["created_at"], str(r["snapshot_id"])))
    rows: list[dict[str, Any]] = []
    for record in normalized:
        payload = record["payload"]
        p = ch10.normalize_payload(payload)
        syn = _synthesis(payload)
        sid = record["snapshot_id"]
        rows.append({
            "Version": f"Snapshot #{sid}" if _text(sid) else "Snapshot",
            "Snapshot ID": sid,
            "Created At": record["created_at"],
            "Schema Version": record["schema_version"],
            "Research Status": record["research_status"],
            "Growth Mode": p.get("growth_mode") or "Unknown",
            "Source Baseline": source_baseline_fingerprint(payload)[:16],
            "Analyst Reviewed At": _text(syn.get("analyst_reviewed_at")),
            "Last Re-review At": _text(syn.get("last_re_review_at")),
            "Last Re-review Sections": _display(syn.get("last_re_review_sections")),
            "Final Synthesis Present": "Yes" if _text(syn.get("final_growth_synthesis")) else "No",
        })
    return pd.DataFrame(rows, columns=LINEAGE_COLUMNS)


def history_summary(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    delta = compare_versions(before, after)
    counts = delta["Delta"].value_counts().to_dict() if not delta.empty else {}
    return {
        "tracked_fields": int(len(delta)),
        "changed_fields": int(sum(int(counts.get(x, 0)) for x in ("Added", "Removed", "Changed"))),
        "unchanged_fields": int(counts.get("Unchanged", 0)),
        "source_baseline_changed": source_baseline_fingerprint(before) != source_baseline_fingerprint(after),
        "historical_source_freshness_reconstructed": False,
        "automatic_growth_mode_change": False,
        "automatic_question_status_change": False,
        "automatic_confidence_change": False,
        "automatic_analyst_text_change": False,
        "automatic_growth_score": False,
        "automatic_growth_forecast": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
        "boundary": HISTORY_BOUNDARY,
    }


__all__ = ["DELTA_COLUMNS", "HISTORY_BOUNDARY", "LINEAGE_COLUMNS", "build_version_lineage", "compare_versions", "history_summary", "source_baseline_fingerprint"]
