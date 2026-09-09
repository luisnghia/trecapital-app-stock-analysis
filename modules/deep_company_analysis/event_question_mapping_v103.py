from __future__ import annotations

"""V103 read-only event -> Investment Checklist evidence mapping.

This module maps externally observed events to canonical Appendix C Qxx references. It never
copies source-locked question wording, mutates checklist status/evidence, writes financial state,
calculates valuation/MOS, or changes the Investment Research Gate. Question wording remains owned
by ``appendix_c`` and is resolved only when a presentation layer needs it.
"""

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from modules.deep_company_analysis.appendix_c import QUESTION_IDS, get_item

AI_ROLE = "Research Assistant"
CONCLUSION_OWNER = "Analyst"
REPORT_VERSION = "V103"
PROVENANCE_COLUMNS = ("source_field", "source_module", "source_period", "data_origin")


@dataclass(frozen=True)
class MappingRule:
    question_id: str
    reason: str


EVENT_RULES: dict[str, tuple[MappingRule, ...]] = {
    "raw_material_cost": (
        MappingRule("Q20", "Supplier/raw-material conditions may affect supplier relationships and bargaining dynamics."),
        MappingRule("Q23", "Input-cost volatility may represent a key operating risk requiring analyst review."),
        MappingRule("Q24", "Raw-material and input-cost changes may be evidence relevant to inflation sensitivity."),
        MappingRule("Q45", "Cost pressure or cost actions may be evidence relevant to management's cost discipline."),
    ),
    "audit_governance": (
        MappingRule("Q27", "Audit/accounting developments may be evidence relevant to accounting conservatism or aggressiveness."),
        MappingRule("Q40", "Governance events may be evidence relevant to how management treats stakeholders."),
        MappingRule("Q49", "Audit/governance events may provide evidence relevant to management integrity."),
        MappingRule("Q50", "Disclosure/governance events may be evidence relevant to clarity and consistency of management communications."),
    ),
    "project_delay": (
        MappingRule("Q23", "A project delay may reveal execution, permitting, supply-chain, financing, or other key business risks."),
        MappingRule("Q42", "A material delay may be relevant to prior management guidance and subsequent revisions."),
        MappingRule("Q55", "Delayed capacity/projects may affect the evidence supporting future growth prospects."),
        MappingRule("Q56", "Repeated or material delays may be evidence relevant to whether growth is being pursued too quickly."),
    ),
}

EVENT_TYPE_ALIASES = {
    "raw-material/cost": "raw_material_cost",
    "raw material cost": "raw_material_cost",
    "raw_material_cost": "raw_material_cost",
    "input_cost": "raw_material_cost",
    "cost": "raw_material_cost",
    "audit/governance": "audit_governance",
    "audit governance": "audit_governance",
    "audit_governance": "audit_governance",
    "governance": "audit_governance",
    "audit": "audit_governance",
    "project-delay": "project_delay",
    "project delay": "project_delay",
    "project_delay": "project_delay",
    "delay": "project_delay",
}


class EventMappingError(ValueError):
    pass


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_event_type(value: Any) -> str:
    raw = _clean(value).lower().replace("–", "-").replace("—", "-")
    normalized = EVENT_TYPE_ALIASES.get(raw)
    if not normalized:
        raise EventMappingError(f"Unsupported event_type: {_clean(value) or '<blank>'}")
    return normalized


def validate_mapping_contract() -> tuple[str, ...]:
    errors: list[str] = []
    valid = set(QUESTION_IDS)
    if set(EVENT_RULES) != {"raw_material_cost", "audit_governance", "project_delay"}:
        errors.append("V103 must retain exactly the three approved deterministic event families.")
    for event_type, rules in EVENT_RULES.items():
        if not rules:
            errors.append(f"{event_type} has no mapping rules.")
        ids = [rule.question_id for rule in rules]
        if len(ids) != len(set(ids)):
            errors.append(f"{event_type} contains duplicate question references.")
        unknown = sorted(set(ids) - valid)
        if unknown:
            errors.append(f"{event_type} references unknown questions: {', '.join(unknown)}")
    return tuple(errors)


def map_event_to_questions(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic evidence-routing rows; never return or mutate checklist status."""
    errors = validate_mapping_contract()
    if errors:
        raise EventMappingError("; ".join(errors))
    event_type = normalize_event_type(event.get("event_type") or event.get("type") or event.get("category"))
    event_id = _clean(event.get("event_id") or event.get("id"))
    summary = _clean(event.get("event_summary") or event.get("summary") or event.get("title"))
    event_date = _clean(event.get("event_date") or event.get("date"))
    source_field = _clean(event.get("source_field")) or "event"
    source_module = _clean(event.get("source_module")) or "event_evidence"
    source_period = _clean(event.get("source_period")) or event_date
    data_origin = _clean(event.get("data_origin") or event.get("source") or event.get("url"))
    if not summary:
        raise EventMappingError("event_summary is required")
    rows: list[dict[str, Any]] = []
    for rule in EVENT_RULES[event_type]:
        rows.append({
            "event_type": event_type,
            "event_id": event_id,
            "event_date": event_date,
            "event_summary": summary,
            "question_id": rule.question_id,
            "mapping_reason": rule.reason,
            "source_field": source_field,
            "source_module": source_module,
            "source_period": source_period,
            "data_origin": data_origin,
        })
    return rows


def map_events_to_questions(events: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Map, dedupe and stably sort events without altering any owner state."""
    rows: list[dict[str, Any]] = []
    for event in events or []:
        rows.extend(map_event_to_questions(event))
    deduped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            row["event_type"], row["event_id"], row["event_date"],
            row["event_summary"], row["question_id"],
        )
        deduped.setdefault(key, row)
    return sorted(
        deduped.values(),
        key=lambda row: (row["event_date"], row["event_type"], row["event_id"], row["question_id"], row["event_summary"]),
    )


def resolve_question_reference(question_id: str) -> dict[str, Any]:
    """Resolve canonical wording on demand from Appendix C; V103 owns no question text."""
    item = get_item(question_id)
    if item is None:
        raise EventMappingError(f"Unknown question reference: {question_id}")
    return item


def render_event_mapping_rows(events: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Presentation rows with wording resolved by reference from the source lock."""
    rendered: list[dict[str, Any]] = []
    for row in map_events_to_questions(events):
        item = resolve_question_reference(row["question_id"])
        rendered.append({**row, "question": str(item["question"]), "owner_chapter": int(item["owner_chapter"])})
    return rendered


__all__ = [
    "AI_ROLE", "CONCLUSION_OWNER", "EVENT_RULES", "EventMappingError", "PROVENANCE_COLUMNS",
    "REPORT_VERSION", "map_event_to_questions", "map_events_to_questions", "normalize_event_type",
    "render_event_mapping_rows", "resolve_question_reference", "validate_mapping_contract",
]
