from __future__ import annotations

"""Chapter 6 Phase 6D — final source closure and completion gate.

This module closes source-derived gaps after Phase 6C. It is evidence/methodology support only:
- no automatic Conservative/Liberal conclusion,
- no automatic Distribution Width,
- no automatic MOS or BUY/HOLD/SELL,
- no fabricated TTM for annual-only disclosures,
- no automatic valuation assumptions.
"""

from copy import deepcopy
from typing import Any
import math

import pandas as pd


TAX_FOOTNOTE_COLUMNS = [
    "Kỳ",
    "Tax Provision (tỷ)",
    "Current Tax (tỷ)",
    "Difference (tỷ)",
    "Difference (%)",
    "Source Title",
    "Source URL / File",
    "Disclosure Status",
    "Analyst Note",
]

UNSUSTAINABLE_EARNINGS_COLUMNS = [
    "Kỳ",
    "Item / Event",
    "Type",
    "Amount (tỷ)",
    "Recurring / Non-recurring / Unknown",
    "Cash / Non-cash / Mixed",
    "Impact on Reported Earnings",
    "Source Title",
    "Source URL / File",
    "Supporting Evidence",
    "Counter-Evidence",
    "Analyst Assessment",
    "Analyst Note",
]

ASSET_REPLACEMENT_COLUMNS = [
    "As-of Period",
    "Asset Class",
    "Gross PP&E (tỷ)",
    "Net PP&E (tỷ)",
    "Net / Gross PP&E (%)",
    "Depreciable?",
    "Land / Non-depreciable?",
    "Estimated Age / Remaining Life",
    "Replacement Interval / Timing",
    "Accelerated Depreciation / Comparability",
    "Maintenance / Growth / Regulatory",
    "Expected Replacement Burden",
    "Source Title",
    "Source URL / File",
    "Supporting Evidence",
    "Counter-Evidence",
    "Analyst Assessment",
    "Analyst Note",
]

VALUATION_SCENARIO_COLUMNS = [
    "Scenario",
    "Probability (%)",
    "Analyst Revenue / Demand Assumption",
    "Analyst Margin Assumption",
    "Analyst Normalized Earnings / FCF (tỷ)",
    "Valuation Method",
    "Analyst Fair Value (tỷ / share as documented)",
    "Evidence / Reason",
    "Analyst Note",
]

FINAL_CHECKLIST_COLUMNS = [
    "Question",
    "Source-Locked Requirement",
    "Status",
    "Evidence / Reason",
    "Analyst Note",
]

FINAL_CHECKLIST_STATUS_OPTIONS = ("Unknown", "Covered", "Evidence weak", "N/A")


def default_final_checklist_rows() -> list[dict[str, Any]]:
    requirements = [
        (
            "Q27",
            "Compare Current Tax vs Income-Tax Provision over 5–10 years where disclosed; do not substitute tax paid for current-tax expense.",
        ),
        (
            "Q27",
            "Compare CFO vs Net Income and investigate revenue recognition, capitalization/expensing, depreciation estimates, reserves and restructuring/one-offs.",
        ),
        (
            "Q27",
            "Identify unsustainable earnings sources such as debt-retirement gains/losses, asset write-offs and temporary cuts to advertising/R&D/maintenance.",
        ),
        (
            "Q28",
            "Determine whether revenue is recurring/contractual/behavioral/repeat-purchase/one-off using explicit evidence; do not fabricate recurring share.",
        ),
        (
            "Q29",
            "Assess cyclicality, purchase deferrability, customer-cycle exposure, supply/demand and commodity evidence without auto-classifying the company.",
        ),
        (
            "Q30",
            "Assess operating leverage and review the combined evidence of high operating leverage with balance-sheet debt/interest burden.",
        ),
        (
            "Q31",
            "Review 5–10Y DSO/DIO/DPO/CCC and operating-working-capital cash impact; explain whether cash release/absorption is sustainable or temporary.",
        ),
        (
            "Q32",
            "Separate total capex from maintenance/growth/regulatory capex; review asset age/replacement burden and use depreciation only as an explicitly selected rough proxy when appropriate.",
        ),
        (
            "Final",
            "Translate analyst-owned earnings/cash-flow Distribution Width into a valuation-method review: point estimate may be more useful for narrow distributions; scenario analysis is preferred for wide distributions.",
        ),
    ]
    return [
        {
            "Question": q,
            "Source-Locked Requirement": requirement,
            "Status": "Unknown",
            "Evidence / Reason": "",
            "Analyst Note": "",
        }
        for q, requirement in requirements
    ]


def default_scenario_rows() -> list[dict[str, Any]]:
    return [
        {
            "Scenario": scenario,
            "Probability (%)": None,
            "Analyst Revenue / Demand Assumption": "",
            "Analyst Margin Assumption": "",
            "Analyst Normalized Earnings / FCF (tỷ)": None,
            "Valuation Method": "",
            "Analyst Fair Value (tỷ / share as documented)": None,
            "Evidence / Reason": "",
            "Analyst Note": "",
        }
        for scenario in ("Bear", "Base", "Bull")
    ]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def tax_footnote_analysis(rows: Any) -> pd.DataFrame:
    """Compute the Shearn current-tax vs tax-provision comparison from explicit analyst-entered disclosures.

    The function never uses cash taxes paid as a substitute. TTM is not synthesized; if a TTM row is
    entered by the analyst it is treated as a disclosed row and remains visibly sourced.
    """
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
    elif isinstance(rows, list):
        df = pd.DataFrame([dict(r) for r in rows if isinstance(r, dict)])
    else:
        df = pd.DataFrame()
    if df.empty:
        return pd.DataFrame(columns=TAX_FOOTNOTE_COLUMNS)
    for col in TAX_FOOTNOTE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    for idx, row in df.iterrows():
        provision = _safe_float(row.get("Tax Provision (tỷ)"))
        current = _safe_float(row.get("Current Tax (tỷ)"))
        if provision is None or current is None:
            df.at[idx, "Difference (tỷ)"] = None
            df.at[idx, "Difference (%)"] = None
            continue
        provision_abs = abs(provision)
        current_abs = abs(current)
        difference = current_abs - provision_abs
        df.at[idx, "Difference (tỷ)"] = difference
        df.at[idx, "Difference (%)"] = abs(difference) / provision_abs * 100.0 if provision_abs > 1e-12 else None
    return df[TAX_FOOTNOTE_COLUMNS]


def asset_replacement_analysis(rows: Any) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
    elif isinstance(rows, list):
        df = pd.DataFrame([dict(r) for r in rows if isinstance(r, dict)])
    else:
        df = pd.DataFrame()
    if df.empty:
        return pd.DataFrame(columns=ASSET_REPLACEMENT_COLUMNS)
    for col in ASSET_REPLACEMENT_COLUMNS:
        if col not in df.columns:
            df[col] = None
    for idx, row in df.iterrows():
        gross = _safe_float(row.get("Gross PP&E (tỷ)"))
        net = _safe_float(row.get("Net PP&E (tỷ)"))
        df.at[idx, "Net / Gross PP&E (%)"] = (net / gross * 100.0) if gross not in {None, 0.0} and net is not None else None
    return df[ASSET_REPLACEMENT_COLUMNS]


def combined_leverage_evidence(dol_summary: dict[str, Any] | None, balance_sheet: pd.DataFrame | None) -> pd.DataFrame:
    """Combine Q30 DOL evidence with Chapter-5 balance-sheet diagnostics without producing a risk score."""
    if not isinstance(dol_summary, dict):
        dol_summary = {}
    latest: dict[str, Any] = {}
    if isinstance(balance_sheet, pd.DataFrame) and not balance_sheet.empty:
        latest = balance_sheet.iloc[-1].to_dict()
    row = {
        "Kỳ": latest.get("Kỳ") or "Latest",
        "Median DOL (x)": dol_summary.get("median_dol"),
        "Downside Median DOL (x)": dol_summary.get("downside_median_dol"),
        "Upside Median DOL (x)": dol_summary.get("upside_median_dol"),
        "Nợ vay ròng (tỷ)": latest.get("Nợ vay ròng (tỷ)"),
        "Debt/EBITDA (x)": latest.get("Debt/EBITDA (x)"),
        "EBIT/Interest (x)": latest.get("EBIT/Interest (x)"),
        "CFO/Interest (x)": latest.get("CFO/Interest (x)"),
        "Boundary": "Combined evidence only — analyst decides whether leverage materially widens earnings/distress risk; no score or automatic conclusion.",
        "Data Origin": "Q30 Phase 6B DOL + Chapter 5 shared balance-sheet context",
    }
    if all(row.get(k) is None for k in ("Median DOL (x)", "Nợ vay ròng (tỷ)", "Debt/EBITDA (x)", "EBIT/Interest (x)")):
        return pd.DataFrame()
    return pd.DataFrame([row])


def valuation_method_guidance(distribution_width: str) -> dict[str, str]:
    width = str(distribution_width or "Unknown")
    if width in {"Narrow", "Moderately Narrow"}:
        return {
            "guidance": "Point-estimate valuation may be more useful; scenario analysis remains optional and analyst-owned.",
            "preferred_workspace": "Point estimate / normalized earnings or FCF review",
            "boundary": "Not a Buy Signal; no automatic MOS or valuation assumption change.",
        }
    if width in {"Moderately Wide", "Wide"}:
        return {
            "guidance": "Scenario analysis is preferred because the earnings/cash-flow distribution is wide.",
            "preferred_workspace": "Bear / Base / Bull scenario analysis",
            "boundary": "All scenario assumptions, probabilities, fair values and MOS remain analyst-owned.",
        }
    if width == "Medium":
        return {
            "guidance": "Use a hybrid review: normalized point estimate plus explicit downside/upside scenarios where material.",
            "preferred_workspace": "Hybrid point estimate + scenarios",
            "boundary": "No automatic valuation assumption or MOS change.",
        }
    return {
        "guidance": "Distribution Width is Unknown; valuation-method selection should remain open until evidence is sufficient.",
        "preferred_workspace": "Unknown / analyst decide",
        "boundary": "No automatic valuation assumption or MOS change.",
    }


def _scenario_rows_complete(rows: Any) -> bool:
    if not isinstance(rows, list):
        return False
    found: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Scenario") or "").strip().casefold()
        if name in {"bear", "base", "bull"}:
            evidence = str(row.get("Evidence / Reason") or "").strip()
            assumption = str(row.get("Analyst Revenue / Demand Assumption") or "").strip() or str(row.get("Analyst Margin Assumption") or "").strip()
            normalized = _safe_float(row.get("Analyst Normalized Earnings / FCF (tỷ)"))
            if evidence and (assumption or normalized is not None):
                found.add(name)
    return found == {"bear", "base", "bull"}


def chapter6_completion_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Return blocking gaps for the analyst-controlled Chapter-6 completion gate."""
    data = deepcopy(payload or {})
    blockers: list[str] = []
    warnings: list[str] = []

    statuses = data.get("question_status") or {}
    for q in ("Q27", "Q28", "Q29", "Q30", "Q31", "Q32"):
        if str(statuses.get(q) or "Unknown") not in {"Answered", "N/A"}:
            blockers.append(f"{q}: Research status chưa là Answered/N/A.")

    width = str(data.get("earnings_distribution_width") or "Unknown")
    if width == "Unknown":
        blockers.append("Final Distribution Width vẫn Unknown.")

    if not str(data.get("analyst_summary") or "").strip():
        blockers.append("Chưa có kết luận Chapter 6 của analyst.")

    checklist = data.get("chapter6_final_checklist") or []
    if not checklist:
        blockers.append("Final Source Checklist chưa có dữ liệu.")
    else:
        for row in checklist:
            if not isinstance(row, dict):
                continue
            status = str(row.get("Status") or "Unknown")
            if status not in {"Covered", "N/A"}:
                requirement = str(row.get("Source-Locked Requirement") or row.get("Question") or "Checklist item")
                blockers.append(f"Final checklist chưa đóng: {requirement[:110]}")

    open_gaps = []
    for row in data.get("research_gaps_table") or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("Status") or "").strip().casefold()
        if status and not any(status.startswith(prefix) for prefix in ("closed", "resolved", "accepted", "n/a")):
            open_gaps.append(str(row.get("Research Gap") or row.get("Question") or "Open research gap"))
    if open_gaps:
        blockers.append(f"Còn {len(open_gaps)} research gap chưa Closed/Resolved/Accepted/N/A.")

    if width in {"Moderately Wide", "Wide"} and not _scenario_rows_complete(data.get("valuation_scenarios")):
        blockers.append("Distribution rộng: Bear/Base/Bull scenario workspace chưa đủ assumption + evidence cho cả 3 kịch bản.")

    if str(data.get("critical_unknowns") or "").strip():
        warnings.append("Critical unknowns vẫn còn nội dung; analyst cần xác nhận đây là residual uncertainty đã chấp nhận trước khi khóa chương.")

    confirmed = bool(data.get("chapter6_complete_confirmed"))
    return {
        "ready": not blockers,
        "confirmed": confirmed and not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "status": "Complete — analyst confirmed" if confirmed and not blockers else ("Ready for analyst confirmation" if not blockers else "Not ready"),
    }


__all__ = [
    "TAX_FOOTNOTE_COLUMNS",
    "UNSUSTAINABLE_EARNINGS_COLUMNS",
    "ASSET_REPLACEMENT_COLUMNS",
    "VALUATION_SCENARIO_COLUMNS",
    "FINAL_CHECKLIST_COLUMNS",
    "FINAL_CHECKLIST_STATUS_OPTIONS",
    "default_final_checklist_rows",
    "default_scenario_rows",
    "tax_footnote_analysis",
    "asset_replacement_analysis",
    "combined_leverage_evidence",
    "valuation_method_guidance",
    "chapter6_completion_status",
]
