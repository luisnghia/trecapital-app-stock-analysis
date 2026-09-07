from __future__ import annotations

"""Chapter 10 Phase 10C — canonical read-only data bridge.

This module only maps facts already present in a caller-supplied canonical payload into
Chapter 10 evidence observations. It never fetches data, recalculates financial metrics,
changes analyst-owned fields, forecasts growth, or creates an investment signal.

Important SSOT rule: cash-conversion cycle (CCC) is consumed only when a canonical CCC value
is present. DIO/DSO/DPO may be surfaced individually as provenance, but this bridge never
computes CCC = DIO + DSO - DPO.
"""

from copy import deepcopy
from typing import Any, Iterable

from modules.deep_company_analysis import chapter10

PHASE = "10C"
VERSION = "V76"
BRIDGE_CONTRACT = "canonical-read-only"

# Canonical dependency labels used by Chapter 10. Aliases permit existing SSOT payloads to
# expose equivalent names without moving the calculation into this module.
CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "revenue": ("revenue", "net_revenue", "sales"),
    "segment_revenue": ("segment_revenue", "revenue_by_segment"),
    "cash_flow_operations": ("cash_flow_operations", "cfo", "operating_cash_flow"),
    "acquisition_cash_spend": ("acquisition_cash_spend", "acquisitions_cash_paid", "cash_acquisitions"),
    "debt": ("debt", "total_debt"),
    "gross_margin": ("gross_margin",),
    "operating_margin": ("operating_margin", "ebit_margin"),
    "operating_income": ("operating_income", "ebit"),
    "operating_units": ("operating_units", "unit_count", "store_count", "locations"),
    "eps": ("eps", "earnings_per_share"),
    "industry_operating_metric": ("industry_operating_metric",),
    "commodity_price": ("commodity_price",),
    "rd_expense": ("rd_expense", "research_and_development"),
    "new_product_revenue": ("new_product_revenue",),
    "market_size": ("market_size",),
    "dividends_paid": ("dividends_paid", "cash_dividends"),
    "earnings": ("earnings", "net_income"),
    "pe_ratio": ("pe_ratio", "pe"),
    "debt_issuance": ("debt_issuance", "debt_issued"),
    "equity_issuance": ("equity_issuance", "equity_issued"),
    "dio": ("dio", "days_inventory_outstanding"),
    "dso": ("dso", "days_sales_outstanding"),
    "dpo": ("dpo", "days_payables_outstanding"),
    "ccc": ("ccc", "cash_conversion_cycle"),
    "capex": ("capex", "capital_expenditure", "capital_expenditures"),
    "employee_count": ("employee_count", "employees"),
    "return_on_capital": ("return_on_capital", "roic", "roc"),
}


def _containers(payload: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    """Yield likely canonical containers without assuming one historical schema."""
    if isinstance(payload, dict):
        yield "root", payload
        for key in ("metrics", "financials", "canonical", "canonical_metrics", "derived_metrics", "facts"):
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
    return tuple(part.strip() for part in str(spec or "").split(";") if part.strip() and part.strip() != "none")


def build_dimension_evidence(canonical_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build deterministic, neutral evidence availability rows for all 34 dimensions."""
    payload = canonical_payload if isinstance(canonical_payload, dict) else {}
    as_of = payload.get("as_of_date") or payload.get("as_of") or payload.get("date")
    source_name = payload.get("source") or payload.get("source_name") or "canonical_payload"
    rows: list[dict[str, Any]] = []

    for item in chapter10.dimension_catalog():
        dependencies = _dependency_names(item.get("ssot_dependency", "none"))
        lookups = [canonical_lookup(payload, dep) for dep in dependencies]
        available = [entry for entry in lookups if entry["available"]]
        missing = [entry["dependency"] for entry in lookups if not entry["available"]]

        # Qualitative dimensions have no canonical financial dependency and remain Unknown.
        if not dependencies:
            status = "Unknown"
            observation = "No canonical quantitative dependency; analyst/research evidence required."
        elif available:
            status = "Evidence found"
            observation = "Canonical SSOT evidence available for: " + ", ".join(entry["dependency"] for entry in available)
            if missing:
                observation += "; missing: " + ", ".join(missing)
        else:
            status = "Unknown"
            observation = "Canonical SSOT dependencies unavailable: " + ", ".join(dependencies)

        rows.append({
            "question": item["question"],
            "dimension_id": item["id"],
            "dimension": item["label"],
            "status": status,
            "direction": "Unknown",
            "observation": observation,
            "dependencies": dependencies,
            "available_dependencies": tuple(entry["dependency"] for entry in available),
            "missing_dependencies": tuple(missing),
            "canonical_values": {entry["dependency"]: deepcopy(entry["value"]) for entry in available},
            "provenance": {
                "bridge": BRIDGE_CONTRACT,
                "source": source_name,
                "as_of_date": as_of,
                "locations": {entry["dependency"]: f"{entry['container']}.{entry['canonical_key']}" for entry in available},
            },
        })
    return rows


def ccc_bridge_state(canonical_payload: dict[str, Any] | None) -> dict[str, Any]:
    """Expose CCC read-only; explicitly refuse reconstruction from DIO/DSO/DPO."""
    payload = canonical_payload if isinstance(canonical_payload, dict) else {}
    ccc = canonical_lookup(payload, "ccc")
    components = {name: canonical_lookup(payload, name) for name in ("dio", "dso", "dpo")}
    if ccc["available"]:
        return {
            "status": "Evidence found",
            "ccc": deepcopy(ccc["value"]),
            "canonical_key": ccc["canonical_key"],
            "computed_by_chapter10": False,
            "components_available": {key: value["available"] for key, value in components.items()},
        }
    return {
        "status": "Unknown",
        "ccc": None,
        "canonical_key": None,
        "computed_by_chapter10": False,
        "components_available": {key: value["available"] for key, value in components.items()},
        "reason": "Canonical CCC unavailable; Chapter 10 does not recompute CCC from DIO/DSO/DPO.",
    }


def bridge_payload(canonical_payload: dict[str, Any] | None, analyst_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return bridge output while preserving analyst-owned Chapter 10 state byte-for-byte."""
    analyst_before = deepcopy(analyst_payload) if isinstance(analyst_payload, dict) else None
    rows = build_dimension_evidence(canonical_payload)
    result = {
        "phase": PHASE,
        "version": VERSION,
        "contract": BRIDGE_CONTRACT,
        "source_lock": chapter10.SOURCE_LOCK,
        "question_range": chapter10.SOURCE_QUESTION_RANGE,
        "dimension_count": len(rows),
        "evidence": rows,
        "ccc": ccc_bridge_state(canonical_payload),
        "analyst_payload": deepcopy(analyst_before),
        "automatic_growth_score": False,
        "automatic_growth_forecast": False,
        "automatic_investment_signal": False,
        "mos_or_research_gate_changed": False,
    }
    return result
