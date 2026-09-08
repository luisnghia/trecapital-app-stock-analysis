from __future__ import annotations

"""Appendix A V92 immutable history, interview lineage and neutral delta.

History exists to preserve what the analyst knew and recorded at a point in time. A delta means
only that the human-intelligence research record changed. It never means a source became more or
less credible, a business improved or worsened, or an investment action should change.
"""

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Iterable

import pandas as pd

from .appendix_a import SECTION_KEYS, SECTION_TITLES
from .appendix_a_workspace import normalize_workspace

HISTORY_BOUNDARY = (
    "Appendix A history is analyst-owned research lineage only; no source/credibility score, "
    "weighted research score, automatic conclusion, valuation/MOS change, Research Gate change, "
    "portfolio action, or BUY/HOLD/SELL signal."
)

DELTA_COLUMNS = ["Field", "Before Version", "Before", "After Version", "After", "Delta"]
LINEAGE_COLUMNS = [
    "Version", "Snapshot ID", "Created At", "Schema Version", "Source Baseline",
    "Sources", "Interviews", "Open Research Gaps", "Analyst Synthesis Present",
]
INTERVIEW_LINEAGE_COLUMNS = [
    "Interview ID", "Source ID", "Interview Date", "Statement Type", "Related DCA Questions",
    "Source Response Present", "Uncertainty Noted", "Analyst Commentary Present",
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


def source_baseline_fingerprint(payload: dict[str, Any] | None) -> str:
    """Fingerprint only Appendix A analyst-owned research state."""
    ws = normalize_workspace(deepcopy(payload or {}))
    state = {
        "sections": ws.get("sections", {}),
        "sources": ws.get("sources", []),
        "interviews": ws.get("interviews", []),
        "research_gaps": ws.get("research_gaps", []),
    }
    raw = json.dumps(state, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def build_interview_lineage(payload: dict[str, Any] | None) -> pd.DataFrame:
    """Describe interview provenance without interpreting truthfulness or credibility."""
    ws = normalize_workspace(payload or {})
    rows = []
    for item in ws.get("interviews", []):
        rows.append({
            "Interview ID": _text(item.get("interview_id")),
            "Source ID": _text(item.get("source_id")),
            "Interview Date": _text(item.get("interview_date")),
            "Statement Type": _text(item.get("statement_type")) or "Unknown",
            "Related DCA Questions": _display(item.get("related_question_refs", [])),
            "Source Response Present": "Yes" if _text(item.get("source_response_observation")) else "No",
            "Uncertainty Noted": "Yes" if _text(item.get("uncertainty_noted")) else "No",
            "Analyst Commentary Present": "Yes" if _text(item.get("analyst_commentary")) else "No",
        })
    return pd.DataFrame(rows, columns=INTERVIEW_LINEAGE_COLUMNS)


def compare_versions(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    *,
    before_label: str = "Before",
    after_label: str = "After",
) -> pd.DataFrame:
    """Neutral comparison of Appendix A records; never evaluates research quality."""
    left, right = normalize_workspace(before or {}), normalize_workspace(after or {})
    specs: list[tuple[str, Any, Any]] = []
    for key in SECTION_KEYS:
        specs.append((f"Section — {SECTION_TITLES[key]}", left.get("sections", {}).get(key), right.get("sections", {}).get(key)))
    specs.extend([
        ("Sources", left.get("sources", []), right.get("sources", [])),
        ("Interviews", left.get("interviews", []), right.get("interviews", [])),
        ("Research Gaps", left.get("research_gaps", []), right.get("research_gaps", [])),
        ("Analyst Synthesis", left.get("analyst_synthesis", ""), right.get("analyst_synthesis", "")),
        ("Source Baseline Fingerprint", source_baseline_fingerprint(left), source_baseline_fingerprint(right)),
    ])
    rows = [{
        "Field": label,
        "Before Version": _text(before_label) or "Before",
        "Before": _display(a),
        "After Version": _text(after_label) or "After",
        "After": _display(b),
        "Delta": _change(a, b),
    } for label, a, b in specs]
    return pd.DataFrame(rows, columns=DELTA_COLUMNS)


def build_version_lineage(records: Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    normalized = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        normalized.append({
            "snapshot_id": record.get("snapshot_id", record.get("id", "")),
            "created_at": _text(record.get("created_at")),
            "schema_version": record.get("schema_version", ""),
            "payload": deepcopy(record.get("payload") or {}),
        })
    normalized.sort(key=lambda r: (r["created_at"], str(r["snapshot_id"])))
    rows = []
    for record in normalized:
        ws = normalize_workspace(record["payload"])
        open_gaps = sum(1 for gap in ws.get("research_gaps", []) if gap.get("status") in {"Open", "In research"})
        sid = record["snapshot_id"]
        rows.append({
            "Version": f"Snapshot #{sid}" if _text(sid) else "Snapshot",
            "Snapshot ID": sid,
            "Created At": record["created_at"],
            "Schema Version": record["schema_version"],
            "Source Baseline": source_baseline_fingerprint(ws)[:16],
            "Sources": len(ws.get("sources", [])),
            "Interviews": len(ws.get("interviews", [])),
            "Open Research Gaps": open_gaps,
            "Analyst Synthesis Present": "Yes" if _text(ws.get("analyst_synthesis")) else "No",
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
        "automatic_human_source_score": False,
        "automatic_credibility_score": False,
        "automatic_weighted_research_score": False,
        "automatic_investment_signal": False,
        "automatic_mos_change": False,
        "automatic_research_gate_change": False,
        "historical_source_freshness_reconstructed": False,
        "boundary": HISTORY_BOUNDARY,
    }


__all__ = [
    "DELTA_COLUMNS", "HISTORY_BOUNDARY", "INTERVIEW_LINEAGE_COLUMNS", "LINEAGE_COLUMNS",
    "build_interview_lineage", "build_version_lineage", "compare_versions", "history_summary",
    "source_baseline_fingerprint",
]
