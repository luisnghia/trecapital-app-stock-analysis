from __future__ import annotations

import modules.deep_company_analysis.chapter5 as ch5


def test_q23_origin_is_hidden_from_ui_columns_but_kept_in_storage_schema():
    assert "Origin" in ch5.RISK_COLUMNS
    assert "Origin" not in ch5.RISK_UI_COLUMNS


def test_q23_hidden_origin_is_reconstructed_on_save_normalization():
    shearn = ch5.ensure_shearn_risks([{"Risk": "Overcapacity", "Risk (VI)": "", "Origin": ""}])
    custom = ch5.ensure_shearn_risks([{"Risk": "Geopolitical route disruption", "Risk (VI)": "", "Origin": ""}])
    assert shearn[0]["Origin"] == "Shearn"
    assert custom[0]["Origin"] == "Analyst-defined"
