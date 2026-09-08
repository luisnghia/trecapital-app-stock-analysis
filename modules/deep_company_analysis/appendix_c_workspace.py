from __future__ import annotations

"""Appendix C V97 — consolidated live SSOT bridge and research navigation.

Read-only by design. Appendix C never persists answers, evidence, confidence, financials,
valuation, MOS, Research Gate, or investment conclusions. It only reads the owning chapter
records and renders a consolidated Q01-Q59 research view.
"""

from copy import deepcopy
from importlib import import_module
from typing import Any, Mapping

from modules.deep_company_analysis import appendix_c as appc

READ_ONLY_FIELDS = ("question_status", "confidence", "analyst_assessment")
STATUS_ORDER = ("Unknown", "Partial", "Answered", "N/A")
FORBIDDEN_KEYS = frozenset({
    "weighted_score", "management_score", "growth_score", "buy_hold_sell", "recommendation",
    "intrinsic_value", "margin_of_safety", "mos", "research_gate", "investment_research_gate",
    "financials", "valuation",
})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _question_value(payload: Mapping[str, Any] | None, field: str, question_id: str, default: str = "Unknown") -> str:
    source = payload if isinstance(payload, Mapping) else {}
    block = source.get(field)
    if isinstance(block, Mapping):
        value = _text(block.get(question_id))
        return value or default
    return default


def load_owner_payload(owner_chapter: int, ticker: str, company_name: str = "") -> dict[str, Any]:
    """Read the existing owner chapter store when available; never writes or normalizes upstream state."""
    try:
        store = import_module(f"modules.deep_company_analysis.chapter{int(owner_chapter)}_store")
        loader = getattr(store, "load_record", None)
        if callable(loader):
            loaded = loader(_text(ticker).upper(), _text(company_name))
            return deepcopy(loaded) if isinstance(loaded, dict) else {}
    except Exception:
        pass
    return {}


def load_owner_payloads(ticker: str, company_name: str = "") -> dict[int, dict[str, Any]]:
    chapters = sorted(set(appc.OWNER_CHAPTER_BY_QUESTION.values()))
    return {chapter: load_owner_payload(chapter, ticker, company_name) for chapter in chapters}


def build_live_rows(
    ticker: str,
    company_name: str = "",
    owner_payloads: Mapping[int, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build a live consolidated view from owner payload references only."""
    payloads: Mapping[int, Mapping[str, Any]] = owner_payloads or load_owner_payloads(ticker, company_name)
    rows: list[dict[str, Any]] = []
    for item in appc.CHECKLIST_ITEMS:
        qid = str(item["question_id"])
        owner = int(item["owner_chapter"])
        payload = payloads.get(owner, {}) if isinstance(payloads, Mapping) else {}
        rows.append({
            "question_id": qid,
            "question": str(item["question"]),
            "section_key": str(item["section_key"]),
            "section_title": str(item["section_title"]),
            "owner_chapter": owner,
            "ssot_reference": qid,
            "question_status": _question_value(payload, "question_status", qid),
            "confidence": _question_value(payload, "confidence", qid),
            "analyst_assessment": _question_value(payload, "analyst_assessment", qid),
            "navigation_target": f"Chapter {owner} / {qid}",
        })
    return rows


def section_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Research-completeness counts only. No score, weight, rank, or investment inference."""
    out: list[dict[str, Any]] = []
    for key in appc.SECTION_ORDER:
        section_rows = [row for row in rows if row.get("section_key") == key]
        counts = {status: sum(row.get("question_status") == status for row in section_rows) for status in STATUS_ORDER}
        out.append({
            "section_key": key,
            "section_title": appc.SECTION_TITLES[key],
            "question_count": len(section_rows),
            **{status.lower().replace("/", "_"): count for status, count in counts.items()},
        })
    return out


def research_completeness(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Simple counts, not percentages or an investment score."""
    return {status: sum(row.get("question_status") == status for row in rows) for status in STATUS_ORDER}


def validate_read_only_rows(rows: list[dict[str, Any]]) -> tuple[str, ...]:
    errors: list[str] = []
    if len(rows) != appc.QUESTION_COUNT:
        errors.append("Live bridge must expose exactly 59 source-locked question references.")
    ids = tuple(str(row.get("question_id", "")) for row in rows)
    if ids != appc.QUESTION_IDS:
        errors.append("Live bridge question order must remain Q01-Q59.")
    for row in rows:
        if any(key in row for key in FORBIDDEN_KEYS):
            errors.append(f"Forbidden duplicated/investment field found in {row.get('question_id')}.")
        if row.get("ssot_reference") != row.get("question_id"):
            errors.append(f"SSOT reference mismatch in {row.get('question_id')}.")
    return tuple(errors)


__all__ = [
    "FORBIDDEN_KEYS", "READ_ONLY_FIELDS", "STATUS_ORDER", "build_live_rows", "load_owner_payload",
    "load_owner_payloads", "research_completeness", "section_summary", "validate_read_only_rows",
]
