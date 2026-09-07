from __future__ import annotations

"""Chapter 9 Phase 9C — manager-context bridge for Q48-Q52.

This phase connects the source-locked Chapter 9 evidence dimensions to the existing
Chapter 7 manager master. It deliberately does not research the web, create a second
manager registry, write analyst conclusions, or calculate any management/investment score.

Boundaries
----------
- Chapter 7 remains the manager identity/background single source of truth (SSOT).
- Q48 and Q52 are CEO-specific in the source. They are scoped only to a manager whose
  Chapter 7 current role explicitly identifies that person as CEO / chief executive /
  Tổng Giám đốc. If no such role is available, the scope remains unassigned/Unknown.
- Q49-Q51 may be researched across the Chapter 7 manager set; the analyst decides whose
  behavior is material to the final answer.
- Source dimensions remain the 26 Phase 9B dimensions; no new checklist criterion is added.
- No web research, UI, database persistence, financial-data bridge, MOS, Research Gate,
  BUY/HOLD/SELL logic, or automatic positive/negative management label is introduced.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
import re

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_source_contract_v63 as source_contract
from modules.deep_company_analysis.chapter8_data_bridge import build_manager_reference


MANAGER_SOURCE_LABEL = ch9.MANAGER_IDENTITY_SSOT
RESEARCH_BOUNDARY = (
    "Manager/source context only — analyst research and judgment required; no management score, "
    "no automatic character conclusion, no MOS/Research Gate, and no BUY/HOLD/SELL."
)

CEO_QUESTIONS = ("Q48", "Q52")
MANAGEMENT_QUESTIONS = ("Q49", "Q50", "Q51")

DIMENSION_SCOPE_COLUMNS = [
    "Question",
    "Dimension Key",
    "Dimension",
    "Source Origin",
    "Source Pages",
    "Manager ID",
    "Manager",
    "Current Role",
    "Chapter 7 Confidence",
    "Manager Source",
    "Supporting Evidence",
    "Counter-Evidence",
    "Evidence Status",
    "Source",
    "Analyst Note",
    "Scope Status",
]

SCOPE_GAP_COLUMNS = [
    "Question",
    "Dimension Key",
    "Research Gap",
    "Materiality",
    "Next Action",
    "Status",
    "Analyst Note",
]


@dataclass
class Chapter9ContextResult:
    manager_reference: pd.DataFrame
    dimension_scope: pd.DataFrame
    gaps: pd.DataFrame
    note: str


def _safe_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_ceo_role(role: Any) -> bool:
    """Return True only for an explicit CEO-equivalent role label.

    We intentionally reject deputy/vice roles so the bridge never promotes a deputy CEO to
    the CEO-specific Q48/Q52 scope merely because the text contains the token ``CEO``.
    """
    text = _safe_text(role).casefold()
    if not text:
        return False
    negative = (
        "deputy ceo",
        "vice ceo",
        "deputy chief executive",
        "vice chief executive",
        "phó tổng giám đốc",
        "pho tong giam doc",
        "phó tgđ",
        "pho tgd",
    )
    if any(term in text for term in negative):
        return False
    positive = (
        "chief executive officer",
        "chief executive",
        "ceo",
        "tổng giám đốc",
        "tong giam doc",
        "tgđ",
        "tgd",
    )
    return any(term in text for term in positive)


def chapter7_manager_reference(chapter7_payload: dict[str, Any] | None) -> pd.DataFrame:
    """Read Chapter 7 manager identities through the existing shared bridge helper.

    This function is a reference adapter only. It never invents or repairs manager IDs.
    """
    return build_manager_reference(chapter7_payload).copy()


def _base_dimension_row(dim: source_contract.SourceDimension) -> dict[str, Any]:
    return {
        "Question": dim.question,
        "Dimension Key": dim.key,
        "Dimension": dim.label,
        "Source Origin": dim.origin,
        "Source Pages": ", ".join(str(page) for page in dim.source_pages),
        "Supporting Evidence": "",
        "Counter-Evidence": "",
        "Evidence Status": "Open — analyst research required",
        "Source": "",
        "Analyst Note": "",
    }


def _attach_manager(base: dict[str, Any], manager: dict[str, Any] | None, scope_status: str) -> dict[str, Any]:
    row = dict(base)
    item = manager or {}
    row.update(
        {
            "Manager ID": _safe_text(item.get("Manager ID")),
            "Manager": _safe_text(item.get("Manager")),
            "Current Role": _safe_text(item.get("Current Role")),
            "Chapter 7 Confidence": _safe_text(item.get("Chapter 7 Confidence")) or "Unknown",
            "Manager Source": MANAGER_SOURCE_LABEL,
            "Scope Status": scope_status,
        }
    )
    return row


def build_dimension_scope(chapter7_payload: dict[str, Any] | None) -> pd.DataFrame:
    """Map the 26 source dimensions to Chapter 7 manager references without judging them.

    If Chapter 7 has no manager records, one unassigned row per source dimension is retained.
    This preserves the complete Chapter 9 research contract while keeping identity Unknown.
    """
    managers = chapter7_manager_reference(chapter7_payload)
    manager_rows = managers.to_dict("records") if not managers.empty else []
    ceo_rows = [row for row in manager_rows if _is_ceo_role(row.get("Current Role"))]

    rows: list[dict[str, Any]] = []
    for dim in source_contract.all_dimensions():
        base = _base_dimension_row(dim)
        if dim.question in CEO_QUESTIONS:
            targets = ceo_rows
            if targets:
                for manager in targets:
                    rows.append(_attach_manager(base, manager, "Scoped — explicit Chapter 7 CEO role"))
            else:
                rows.append(_attach_manager(base, None, "Open — CEO identity/role gap"))
            continue

        # Q49-Q51 concern the manager/management team. Reference every known Chapter 7
        # manager, but leave the analyst to decide whose behavior is material.
        if manager_rows:
            for manager in manager_rows:
                rows.append(_attach_manager(base, manager, "Scoped — Chapter 7 manager reference"))
        else:
            rows.append(_attach_manager(base, None, "Open — manager identity gap"))

    return pd.DataFrame(rows, columns=DIMENSION_SCOPE_COLUMNS)


def build_scope_gaps(chapter7_payload: dict[str, Any] | None) -> pd.DataFrame:
    """Return identity/scope gaps only; absence of evidence is never a negative trait."""
    managers = chapter7_manager_reference(chapter7_payload)
    rows: list[dict[str, Any]] = []

    if managers.empty:
        for question in ch9.QUESTION_KEYS:
            rows.append(
                {
                    "Question": question,
                    "Dimension Key": "",
                    "Research Gap": (
                        f"{MANAGER_SOURCE_LABEL} is empty/unavailable; Chapter 9 cannot reliably scope "
                        "manager-specific behavioral evidence."
                    ),
                    "Materiality": "High",
                    "Next Action": (
                        "Confirm manager identities/roles in Chapter 7 first; do not create replacement "
                        "manager IDs in Chapter 9."
                    ),
                    "Status": "Open — manager identity gap",
                    "Analyst Note": "",
                }
            )
        return pd.DataFrame(rows, columns=SCOPE_GAP_COLUMNS)

    ceos = managers[managers["Current Role"].map(_is_ceo_role)]
    if ceos.empty:
        for question in CEO_QUESTIONS:
            rows.append(
                {
                    "Question": question,
                    "Dimension Key": "",
                    "Research Gap": (
                        f"No explicit CEO/Tổng Giám đốc role is available in {MANAGER_SOURCE_LABEL}; "
                        f"{question} remains unassigned rather than being attached to another manager."
                    ),
                    "Materiality": "High",
                    "Next Action": "Confirm the CEO role in Chapter 7, then rebuild the Chapter 9 context.",
                    "Status": "Open — CEO identity/role gap",
                    "Analyst Note": "",
                }
            )

    return pd.DataFrame(rows, columns=SCOPE_GAP_COLUMNS)


def build_context(
    chapter7_payload: dict[str, Any] | None,
) -> Chapter9ContextResult:
    """Build the deterministic Phase 9C manager context bundle."""
    source_copy = deepcopy(chapter7_payload)
    managers = chapter7_manager_reference(chapter7_payload)
    scope = build_dimension_scope(chapter7_payload)
    gaps = build_scope_gaps(chapter7_payload)
    # Defensive guard: the bridge must never mutate the Chapter 7 payload supplied by the app.
    assert source_copy == chapter7_payload
    note = (
        f"Chapter 9 Phase 9C: {len(managers)} Chapter 7 manager reference(s); "
        f"{len(source_contract.all_dimensions())} source dimensions; {len(scope)} manager-scoped research row(s); "
        f"{len(gaps)} open identity/scope gap(s). Analyst judgment remains required."
    )
    return Chapter9ContextResult(
        manager_reference=managers,
        dimension_scope=scope,
        gaps=gaps,
        note=note,
    )


def context_snapshot(chapter7_payload: dict[str, Any] | None) -> dict[str, Any]:
    result = build_context(chapter7_payload)
    scope = result.dimension_scope
    unique_dimension_count = int(scope["Dimension Key"].nunique()) if not scope.empty else 0
    return {
        "question_keys": list(ch9.QUESTION_KEYS),
        "source_dimension_count": len(source_contract.all_dimensions()),
        "scoped_unique_dimension_count": unique_dimension_count,
        "manager_reference_count": len(result.manager_reference),
        "scope_row_count": len(scope),
        "gap_count": len(result.gaps),
        "manager_identity_ssot": MANAGER_SOURCE_LABEL,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "web_research_added": False,
        "financial_bridge_added": False,
    }


__all__ = [
    "CEO_QUESTIONS",
    "DIMENSION_SCOPE_COLUMNS",
    "MANAGEMENT_QUESTIONS",
    "MANAGER_SOURCE_LABEL",
    "RESEARCH_BOUNDARY",
    "SCOPE_GAP_COLUMNS",
    "Chapter9ContextResult",
    "build_context",
    "build_dimension_scope",
    "build_scope_gaps",
    "chapter7_manager_reference",
    "context_snapshot",
]
