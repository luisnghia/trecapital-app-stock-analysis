from __future__ import annotations

"""Chapter 11 Phase 11C — canonical read-only M&A data bridge.

Maps facts already present in a caller-supplied canonical payload into neutral evidence
availability rows for Chapter 11 (Q58-Q59). This module never fetches data, recomputes
financial ratios, judges acquisition success, forecasts synergies, changes analyst-owned
fields, or creates an investment signal.

SSOT boundary
-------------
- Financial values and deal facts are consumed read-only from the existing canonical payload.
- EV/EBIT, EV/EBITDA, EV/FCF, premiums, leverage, debt coverage and dilution are NOT calculated here.
- Qualitative dimensions remain Unknown until analyst/research evidence exists.
- Partial canonical availability is surfaced as evidence availability, never as a favorable/unfavorable conclusion.
"""

from copy import deepcopy
from typing import Any, Iterable

from modules.deep_company_analysis import chapter11

PHASE = "11C"
VERSION = "V84"
BRIDGE_CONTRACT = "canonical-read-only"

CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "segment_revenue": ("segment_revenue", "revenue_by_segment", "segments"),
    "revenue": ("revenue", "net_revenue", "sales"),
    "operating_expenses": ("operating_expenses", "opex", "operating_costs"),
    "operating_margin": ("operating_margin", "ebit_margin"),
    "debt": ("debt", "total_debt", "gross_debt"),
    "interest_expense": ("interest_expense", "finance_cost", "finance_costs"),
    "customer_retention": ("customer_retention", "customer_retention_rate"),
    "employee_count": ("employee_count", "employees", "headcount"),
    "employee_turnover": ("employee_turnover", "employee_turnover_rate", "staff_turnover"),
    "acquisition_consideration": (
        "acquisition_consideration",
        "purchase_consideration",
        "deal_consideration",
        "purchase_price",
        "acquisition_price",
    ),
    "ebit": ("ebit", "operating_income"),
    "ebitda": ("ebitda",),
    "free_cash_flow": ("free_cash_flow", "fcf"),
    "book_value": ("book_value", "shareholders_equity", "equity_book_value"),
    "cash": ("cash", "cash_and_equivalents", "cash_equivalents"),
    "debt_coverage": ("debt_coverage", "debt_service_coverage", "dscr"),
    "equity_issuance": ("equity_issuance", "equity_issued", "shares_issued_value"),
    "shares_outstanding": ("shares_outstanding", "weighted_average_shares", "shares"),
}


def _containers(payload: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    if not isinstance(payload, dict):
        return
    yield "root", payload
    for key in (
        "metrics",
        "financials",
        "canonical",
        "canonical_metrics",
        "derived_metrics",
        "facts",
        "deal_facts",
        "ma_facts",
        "acquisitions",
    ):
        value = payload.get(key)
        if isinstance(value, dict):
            yield key, value


def _nonempty(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def canonical_lookup(payload: dict[str, Any] | None, dependency: str) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    aliases = CANONICAL_ALIASES.get(dependency, (dependency,))
    for container_name, container in _containers(source):
        for alias in aliases:
            if alias in container and _nonempty(container[alias]):
                return {
                    "available": True,
                    "dependency": dependency,
                    "canonical_key": alias,
                    "container": container_name,
                    "value": deepcopy(container[alias]),
                }
    return {
        "available": False,
        "dependency": dependency,
        "canonical_key": None,
        "container": None,
        "value": None,
    }


def _dependency_names(spec: str) -> tuple[str, ...]:
    return tuple(
        part.strip()
        for part in str(spec or "").split(";")
        if part.strip() and part.strip() != "none"
    )


def build_dimension_evidence(canonical_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build neutral evidence-availability rows for all 15 Chapter 11 dimensions."""
    payload = canonical_payload if isinstance(canonical_payload, dict) else {}
    as_of = payload.get("as_of_date") or payload.get("as_of") or payload.get("date")
    source_name = payload.get("source") or payload.get("source_name") or "canonical_payload"
    rows: list[dict[str, Any]] = []

    for item in chapter11.dimension_catalog():
        dependencies = _dependency_names(item.get("ssot_dependency", "none"))
        lookups = [canonical_lookup(payload, dep) for dep in dependencies]
        available = [entry for entry in lookups if entry["available"]]
        missing = [entry["dependency"] for entry in lookups if not entry["available"]]

        if not dependencies:
            status = "Unknown"
            observation = "No canonical quantitative dependency; analyst/research evidence required."
        elif available:
            status = "Evidence found"
            observation = "Canonical SSOT evidence available for: " + ", ".join(
                entry["dependency"] for entry in available
            )
            if missing:
                observation += "; missing: " + ", ".join(missing)
        else:
            status = "Unknown"
            observation = "Canonical SSOT dependencies unavailable: " + ", ".join(dependencies)

        rows.append(
            {
                "question": item["question"],
                "dimension_id": item["id"],
                "dimension": item["label"],
                "status": status,
                "direction": "Unknown",
                "observation": observation,
                "dependencies": dependencies,
                "available_dependencies": tuple(entry["dependency"] for entry in available),
                "missing_dependencies": tuple(missing),
                "canonical_values": {
                    entry["dependency"]: deepcopy(entry["value"]) for entry in available
                },
                "provenance": {
                    "bridge": BRIDGE_CONTRACT,
                    "source": source_name,
                    "as_of_date": as_of,
                    "locations": {
                        entry["dependency"]: f"{entry['container']}.{entry['canonical_key']}"
                        for entry in available
                    },
                },
            }
        )
    return rows


def valuation_ratio_policy() -> dict[str, Any]:
    """Explicitly declare ratios mentioned by Shearn as upstream SSOT responsibilities."""
    return {
        "computed_by_chapter11": False,
        "ratios": ("EV/EBIT", "EV/EBITDA", "EV/FCF", "book-value premium"),
        "reason": "Chapter 11 consumes canonical components/facts but does not calculate acquisition valuation ratios or premiums.",
    }


def financing_policy() -> dict[str, Any]:
    """No leverage, coverage or dilution calculation is performed by Chapter 11."""
    return {
        "computed_by_chapter11": False,
        "metrics": ("leverage", "debt coverage", "equity dilution"),
        "reason": "Financing metrics must come from canonical SSOT; Chapter 11 only surfaces available facts.",
    }


def bridge_payload(
    canonical_payload: dict[str, Any] | None,
    analyst_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return bridge output while preserving analyst-owned Chapter 11 state byte-for-byte."""
    analyst_before = deepcopy(analyst_payload) if isinstance(analyst_payload, dict) else None
    rows = build_dimension_evidence(canonical_payload)
    return {
        "phase": PHASE,
        "version": VERSION,
        "contract": BRIDGE_CONTRACT,
        "source_lock": chapter11.SOURCE_LOCK,
        "question_range": chapter11.SOURCE_QUESTION_RANGE,
        "dimension_count": len(rows),
        "evidence": rows,
        "valuation_ratio_policy": valuation_ratio_policy(),
        "financing_policy": financing_policy(),
        "analyst_payload": deepcopy(analyst_before),
        "automatic_ma_score": False,
        "automatic_acquisition_success_conclusion": False,
        "automatic_synergy_forecast": False,
        "automatic_investment_signal": False,
        "mos_or_research_gate_changed": False,
    }


__all__ = [
    "BRIDGE_CONTRACT",
    "CANONICAL_ALIASES",
    "PHASE",
    "VERSION",
    "bridge_payload",
    "build_dimension_evidence",
    "canonical_lookup",
    "financing_policy",
    "valuation_ratio_policy",
]
