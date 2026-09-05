from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter6_closure import (
    asset_replacement_analysis,
    chapter6_completion_status,
    combined_leverage_evidence,
    default_final_checklist_rows,
    default_scenario_rows,
    tax_footnote_analysis,
    valuation_method_guidance,
)


def test_tax_footnote_analysis_uses_explicit_current_tax_and_provision_only():
    rows = [
        {
            "Kỳ": "2025",
            "Tax Provision (tỷ)": 100.0,
            "Current Tax (tỷ)": 92.0,
            "Source Title": "Annual report tax note",
            "Source URL / File": "filing.pdf",
            "Disclosure Status": "Company disclosed",
            "Analyst Note": "",
            "tax_paid_bil": 40.0,
        }
    ]
    out = tax_footnote_analysis(rows)
    assert out.iloc[0]["Difference (tỷ)"] == -8.0
    assert out.iloc[0]["Difference (%)"] == 8.0
    assert "tax_paid_bil" not in out.columns


def test_tax_footnote_missing_current_tax_stays_na():
    out = tax_footnote_analysis([{"Kỳ": "2025", "Tax Provision (tỷ)": 100.0}])
    assert pd.isna(out.iloc[0]["Difference (tỷ)"])
    assert pd.isna(out.iloc[0]["Difference (%)"])


def test_asset_replacement_ratio_is_diagnostic_only():
    out = asset_replacement_analysis([
        {
            "As-of Period": "TTM",
            "Asset Class": "Plant",
            "Gross PP&E (tỷ)": 1000.0,
            "Net PP&E (tỷ)": 400.0,
        }
    ])
    assert out.iloc[0]["Net / Gross PP&E (%)"] == 40.0
    assert "maintenance capex" not in " ".join(out.columns).lower()


def test_combined_leverage_is_evidence_without_score():
    balance = pd.DataFrame([
        {
            "Kỳ": "TTM",
            "Nợ vay ròng (tỷ)": 500.0,
            "Debt/EBITDA (x)": 2.2,
            "EBIT/Interest (x)": 4.5,
            "CFO/Interest (x)": 3.9,
        }
    ])
    out = combined_leverage_evidence(
        {"median_dol": 2.4, "downside_median_dol": 3.1, "upside_median_dol": 2.0},
        balance,
    )
    assert out.iloc[0]["Kỳ"] == "TTM"
    assert out.iloc[0]["Median DOL (x)"] == 2.4
    assert out.iloc[0]["Debt/EBITDA (x)"] == 2.2
    assert "score" in out.iloc[0]["Boundary"].lower()
    assert not any("risk score" == str(c).lower() for c in out.columns)


def test_valuation_guidance_does_not_create_assumptions_or_signal():
    wide = valuation_method_guidance("Wide")
    narrow = valuation_method_guidance("Narrow")
    assert "Scenario analysis" in wide["guidance"]
    assert "Point-estimate" in narrow["guidance"]
    assert "automatic MOS" in wide["boundary"]
    assert "Buy Signal" in narrow["boundary"]


def _ready_payload(width: str = "Medium") -> dict:
    checklist = default_final_checklist_rows()
    for row in checklist:
        row["Status"] = "Covered"
        row["Evidence / Reason"] = "Verified"
    return {
        "question_status": {q: "Answered" for q in ("Q27", "Q28", "Q29", "Q30", "Q31", "Q32")},
        "earnings_distribution_width": width,
        "analyst_summary": "Analyst conclusion",
        "chapter6_final_checklist": checklist,
        "research_gaps_table": [],
        "critical_unknowns": "",
        "valuation_scenarios": default_scenario_rows(),
        "chapter6_complete_confirmed": False,
    }


def test_completion_gate_requires_final_checklist_and_analyst_confirmation():
    payload = _ready_payload("Medium")
    status = chapter6_completion_status(payload)
    assert status["ready"] is True
    assert status["confirmed"] is False
    payload["chapter6_complete_confirmed"] = True
    status = chapter6_completion_status(payload)
    assert status["confirmed"] is True
    assert status["status"] == "Complete — analyst confirmed"


def test_completion_gate_blocks_open_research_gap():
    payload = _ready_payload("Medium")
    payload["research_gaps_table"] = [{"Question": "Q27", "Research Gap": "Tax footnote missing", "Status": "Open — evidence gap"}]
    status = chapter6_completion_status(payload)
    assert status["ready"] is False
    assert any("research gap" in b.lower() for b in status["blockers"])


def test_wide_distribution_requires_analyst_bear_base_bull_evidence():
    payload = _ready_payload("Wide")
    status = chapter6_completion_status(payload)
    assert status["ready"] is False
    assert any("Bear/Base/Bull" in b for b in status["blockers"])

    for row in payload["valuation_scenarios"]:
        row["Analyst Revenue / Demand Assumption"] = f"{row['Scenario']} demand assumption"
        row["Evidence / Reason"] = "Analyst evidence"
    status = chapter6_completion_status(payload)
    assert status["ready"] is True


def test_critical_unknowns_warn_but_do_not_auto_fail_completion():
    payload = _ready_payload("Medium")
    payload["critical_unknowns"] = "Residual commodity uncertainty"
    status = chapter6_completion_status(payload)
    assert status["ready"] is True
    assert status["warnings"]
