from __future__ import annotations

"""Appendix C V98 — neutral full-book checklist lineage.

Snapshots are deliberately referential: they preserve only Qxx ownership, research-status/confidence
labels and fingerprints required to compare research progress. They never persist analyst answers,
evidence, financials, valuation, MOS, Research Gate state, or an investment recommendation.
"""

from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

import pandas as pd

from modules.deep_company_analysis import appendix_c as appc
from modules.deep_company_analysis import appendix_c_workspace as ws

DELTA_VALUES = ("Unchanged", "Added", "Removed", "Changed")
SNAPSHOT_SCHEMA_VERSION = 1
FORBIDDEN_SNAPSHOT_KEYS = ws.FORBIDDEN_KEYS | frozenset({"answer", "evidence", "sources", "analyst_assessment"})


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _change(before: Any, after: Any) -> str:
    a, b = _text(before), _text(after)
    if a == b:
        return "Unchanged"
    if not a and b:
        return "Added"
    if a and not b:
        return "Removed"
    return "Changed"


def build_snapshot_payload(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a non-authoritative research-lineage payload; no answer/evidence copy is allowed."""
    normalized = []
    for row in rows:
        normalized.append({
            "question_id": _text(row.get("question_id")),
            "owner_chapter": int(row.get("owner_chapter") or 0),
            "question_status": _text(row.get("question_status")) or "Unknown",
            "confidence": _text(row.get("confidence")) or "Unknown",
        })
    normalized.sort(key=lambda x: x["question_id"])
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "source_lock": appc.SOURCE_LOCK,
        "question_refs": normalized,
    }


def snapshot_fingerprint(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def validate_snapshot_payload(payload: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    refs = payload.get("question_refs", []) if isinstance(payload, Mapping) else []
    if len(refs) != appc.QUESTION_COUNT:
        errors.append("Snapshot must contain exactly 59 referential Qxx rows.")
    ids = tuple(_text(x.get("question_id")) for x in refs if isinstance(x, Mapping))
    if ids != appc.QUESTION_IDS:
        errors.append("Snapshot question order must remain Q01-Q59.")
    for item in refs:
        if not isinstance(item, Mapping):
            errors.append("Snapshot question rows must be mappings.")
            continue
        if set(item) & FORBIDDEN_SNAPSHOT_KEYS:
            errors.append(f"Forbidden duplicated/investment field in {item.get('question_id')}.")
        if set(item) != {"question_id", "owner_chapter", "question_status", "confidence"}:
            errors.append(f"Unexpected snapshot fields in {item.get('question_id')}.")
    return tuple(errors)


def compare_snapshots(before: Mapping[str, Any], after: Mapping[str, Any]) -> pd.DataFrame:
    left = {x["question_id"]: x for x in before.get("question_refs", []) if isinstance(x, Mapping)}
    right = {x["question_id"]: x for x in after.get("question_refs", []) if isinstance(x, Mapping)}
    out = []
    for qid in appc.QUESTION_IDS:
        a, b = left.get(qid, {}), right.get(qid, {})
        for field in ("question_status", "confidence"):
            out.append({
                "Question": qid,
                "Field": field,
                "Before": _text(a.get(field)),
                "After": _text(b.get(field)),
                "Delta": _change(a.get(field), b.get(field)),
            })
    return pd.DataFrame(out, columns=["Question", "Field", "Before", "After", "Delta"])


def build_re_review_record(note: str = "", scope: str = "Q01-Q59") -> dict[str, str]:
    """Explicit analyst re-review metadata only; it does not mutate any owner-chapter research state."""
    return {"scope": _text(scope) or "Q01-Q59", "analyst_note": _text(note)}


def closure_contract() -> dict[str, Any]:
    return {
        "question_coverage": "Q01-Q59",
        "section_coverage": len(appc.SECTION_ORDER),
        "appendix_c_source_pages": list(appc.SOURCE_PRINT_PAGES),
        "ai_role": "Research Assistant",
        "conclusion_owner": "Analyst",
        "automatic_weighted_score": False,
        "automatic_management_or_growth_score": False,
        "automatic_buy_hold_sell": False,
        "automatic_intrinsic_value_or_mos_change": False,
        "automatic_research_gate_change": False,
        "duplicate_financial_or_question_ssot_added": False,
    }


__all__ = [
    "DELTA_VALUES", "FORBIDDEN_SNAPSHOT_KEYS", "SNAPSHOT_SCHEMA_VERSION", "build_re_review_record",
    "build_snapshot_payload", "closure_contract", "compare_snapshots", "snapshot_fingerprint",
    "validate_snapshot_payload",
]
