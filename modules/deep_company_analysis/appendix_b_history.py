from __future__ import annotations

"""Appendix B V95 immutable snapshot/history and neutral interview delta.

History preserves analyst-owned interview evidence at a point in time. A delta only means the
record changed; it never evaluates management quality, truthfulness, personality, credibility,
or investment attractiveness.
"""

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Iterable

import pandas as pd

from modules.deep_company_analysis.appendix_b import MANAGEMENT_INTERVIEW_TOPICS
from modules.deep_company_analysis.appendix_b_workspace import normalize_research_gap, normalize_session

HISTORY_BOUNDARY = (
    "Appendix B history is analyst-owned interview lineage only; no management/CEO/credibility/"
    "personality score, weighted score, automatic conclusion, valuation/MOS change, Research Gate "
    "change, portfolio action, or BUY/HOLD/SELL signal."
)
DELTA_COLUMNS = ["Field", "Before Version", "Before", "After Version", "After", "Delta"]
LINEAGE_COLUMNS = [
    "Version", "Snapshot ID", "Created At", "Schema Version", "Source Baseline",
    "Sessions", "Research Gaps", "Referenced DCA Questions", "Hypothetical Caveats",
    "Face-to-Face Caveats",
]
SESSION_LINEAGE_COLUMNS = [
    "Session ID", "Interview Date", "Participant / Role", "Status", "Topics With Response",
    "Topics With Past-Behavior Evidence", "Referenced DCA Questions", "Hypothetical Caveats",
    "Face-to-Face Caveats", "Analyst Note Present",
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


def normalize_history_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    sessions = [normalize_session(x) for x in src.get("sessions", []) if isinstance(x, dict)]
    gaps = [normalize_research_gap(x) for x in src.get("research_gaps", []) if isinstance(x, dict)]
    ticker = _text(src.get("ticker")).upper()
    if not ticker and sessions:
        ticker = sessions[0].get("ticker", "")
    company = _text(src.get("company_name"))
    if not company and sessions:
        company = sessions[0].get("company_name", "")
    sessions.sort(key=lambda x: (x.get("interview_date", ""), x.get("session_id", "")))
    gaps.sort(key=lambda x: x.get("gap_id", ""))
    return {"ticker": ticker, "company_name": company, "sessions": sessions, "research_gaps": gaps}


def source_baseline_fingerprint(payload: dict[str, Any] | None) -> str:
    clean = normalize_history_payload(deepcopy(payload or {}))
    raw = json.dumps(clean, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def build_session_lineage(payload: dict[str, Any] | None) -> pd.DataFrame:
    clean = normalize_history_payload(payload)
    rows = []
    for session in clean["sessions"]:
        entries = session.get("topic_entries", [])
        refs = []
        for entry in entries:
            for qid in entry.get("dca_question_refs", []):
                if qid not in refs:
                    refs.append(qid)
        rows.append({
            "Session ID": session.get("session_id", ""),
            "Interview Date": session.get("interview_date", ""),
            "Participant / Role": session.get("management_participant_role", ""),
            "Status": session.get("status", ""),
            "Topics With Response": sum(bool(_text(x.get("management_response_observation"))) for x in entries),
            "Topics With Past-Behavior Evidence": sum(bool(_text(x.get("past_behavior_evidence"))) for x in entries),
            "Referenced DCA Questions": ", ".join(refs),
            "Hypothetical Caveats": sum(bool(x.get("hypothetical_flag")) for x in entries),
            "Face-to-Face Caveats": sum(_text(x.get("face_to_face_caveat")) not in {"", "Not noted"} for x in entries),
            "Analyst Note Present": "Yes" if _text(session.get("analyst_session_note")) else "No",
        })
    return pd.DataFrame(rows, columns=SESSION_LINEAGE_COLUMNS)


def compare_versions(before: dict[str, Any] | None, after: dict[str, Any] | None, *, before_label: str = "Before", after_label: str = "After") -> pd.DataFrame:
    left, right = normalize_history_payload(before), normalize_history_payload(after)
    specs: list[tuple[str, Any, Any]] = []
    left_sessions = {x["session_id"]: x for x in left["sessions"]}
    right_sessions = {x["session_id"]: x for x in right["sessions"]}
    for sid in sorted(set(left_sessions) | set(right_sessions)):
        a, b = left_sessions.get(sid, {}), right_sessions.get(sid, {})
        specs.append((f"Session — {sid}", a, b))
        a_entries = {x.get("topic", ""): x for x in a.get("topic_entries", [])}
        b_entries = {x.get("topic", ""): x for x in b.get("topic_entries", [])}
        for topic in MANAGEMENT_INTERVIEW_TOPICS:
            specs.append((f"{sid} — Topic — {topic}", a_entries.get(topic, {}), b_entries.get(topic, {})))
    specs.extend([
        ("Research Gaps", left["research_gaps"], right["research_gaps"]),
        ("Source Baseline Fingerprint", source_baseline_fingerprint(left), source_baseline_fingerprint(right)),
    ])
    rows = [{
        "Field": label, "Before Version": _text(before_label) or "Before", "Before": _display(a),
        "After Version": _text(after_label) or "After", "After": _display(b), "Delta": _change(a, b),
    } for label, a, b in specs]
    return pd.DataFrame(rows, columns=DELTA_COLUMNS)


def build_version_lineage(records: Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    rows = []
    normalized = [x for x in (records or []) if isinstance(x, dict)]
    normalized.sort(key=lambda r: (_text(r.get("created_at")), str(r.get("snapshot_id", ""))))
    for record in normalized:
        payload = normalize_history_payload(record.get("payload") or {})
        refs = set()
        hypothetical = 0
        face = 0
        for session in payload["sessions"]:
            for entry in session.get("topic_entries", []):
                refs.update(entry.get("dca_question_refs", []))
                hypothetical += int(bool(entry.get("hypothetical_flag")))
                face += int(_text(entry.get("face_to_face_caveat")) not in {"", "Not noted"})
        rows.append({
            "Version": f"Snapshot #{record.get('snapshot_id', '')}",
            "Snapshot ID": record.get("snapshot_id", ""),
            "Created At": _text(record.get("created_at")),
            "Schema Version": record.get("schema_version", ""),
            "Source Baseline": source_baseline_fingerprint(payload)[:16],
            "Sessions": len(payload["sessions"]),
            "Research Gaps": len(payload["research_gaps"]),
            "Referenced DCA Questions": len(refs),
            "Hypothetical Caveats": hypothetical,
            "Face-to-Face Caveats": face,
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
        "automatic_management_score": False,
        "automatic_ceo_quality_classifier": False,
        "automatic_credibility_or_personality_score": False,
        "automatic_investment_signal": False,
        "automatic_mos_change": False,
        "automatic_research_gate_change": False,
        "historical_source_freshness_reconstructed": False,
        "boundary": HISTORY_BOUNDARY,
    }


__all__ = [
    "DELTA_COLUMNS", "HISTORY_BOUNDARY", "LINEAGE_COLUMNS", "SESSION_LINEAGE_COLUMNS",
    "build_session_lineage", "build_version_lineage", "compare_versions", "history_summary",
    "normalize_history_payload", "source_baseline_fingerprint",
]
