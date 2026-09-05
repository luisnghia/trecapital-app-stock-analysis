from __future__ import annotations

import modules.deep_company_analysis.chapter6 as ch6


def test_empty_payload_contains_q27_to_q32_and_shearn_reserves():
    payload = ch6.empty_payload("dcm")
    assert payload["ticker"] == "DCM"
    assert payload["schema_version"] == ch6.SCHEMA_VERSION
    assert set(payload["question_status"]) == {"Q27", "Q28", "Q29", "Q30", "Q31", "Q32"}
    assert all(value == "Unknown" for value in payload["question_status"].values())

    reserves = payload["q27_accounting_quality"]
    assert len(reserves) == 7
    assert {row["Area"] for row in reserves} == {name for name, _ in ch6.SHEARN_Q27_RESERVE_AREAS}
    assert all(row["Origin"] == "Shearn" for row in reserves)
    assert all(row["Analyst Assessment"] == "Unknown" for row in reserves)


def test_phase6a_does_not_fabricate_recurring_share_or_maintenance_capex():
    payload = ch6.empty_payload("FPT")
    assert payload["q28"]["recurring_revenue_share"] == ""
    assert payload["q28"]["recurring_revenue_share_source"] == "Unknown"
    assert payload["q32"]["maintenance_capex_visibility"] == "Unknown"
    assert payload["q32"]["maintenance_vs_growth_split"] == "Unknown"
    assert payload["q32"]["maintenance_capex_method"] == "Unknown"
    assert payload["q32_capex_register"] == []


def test_approved_distribution_matrix_has_six_drivers_and_no_score():
    payload = ch6.empty_payload("DGC")
    matrix = payload["earnings_distribution_matrix"]
    assert payload["earnings_distribution_width"] == "Unknown"
    assert len(matrix) == 6
    assert {row["Question"] for row in matrix} == set(ch6.QUESTION_KEYS)
    assert {row["Driver"] for row in matrix} == {
        "Accounting quality",
        "Revenue recurrence",
        "Cyclicality",
        "Operating leverage",
        "Working capital",
        "Capital intensity",
    }
    assert ch6.DISTRIBUTION_WIDTH_OPTIONS == (
        "Unknown",
        "Narrow",
        "Moderately Narrow",
        "Medium",
        "Moderately Wide",
        "Wide",
    )
    assert "score" not in " ".join(payload.keys()).lower()


def test_q27_rollforward_and_q28_revenue_durability_schema():
    assert "Beginning Reserve (tỷ)" in ch6.RESERVE_ROLLFORWARD_COLUMNS
    assert "Provision (tỷ)" in ch6.RESERVE_ROLLFORWARD_COLUMNS
    assert "Write-offs / Usage (tỷ)" in ch6.RESERVE_ROLLFORWARD_COLUMNS
    assert "Provision / Actual (x)" in ch6.RESERVE_ROLLFORWARD_COLUMNS
    assert "Revenue Share (%)" in ch6.RECURRING_REVENUE_COLUMNS
    assert "Revenue Type" in ch6.RECURRING_REVENUE_COLUMNS
    assert "Revenue at Risk (%)" in ch6.RECURRING_REVENUE_COLUMNS
    assert ch6.empty_payload("DGC")["q27_reserve_rollforward"] == []


def test_q32_depreciation_proxy_is_explicit_and_warns_without_rationale():
    payload = ch6.empty_payload("DGC")
    assert "Depreciation rough proxy — clearly labelled" in ch6.MAINTENANCE_CAPEX_METHOD_OPTIONS
    payload["q32"]["maintenance_capex_method"] = "Depreciation rough proxy — clearly labelled"
    warnings = ch6.research_gap_warnings(payload)
    assert any("depreciation" in warning.lower() for warning in warnings)

    payload["q32"]["depreciation_proxy_note"] = "Low-growth asset base; proxy is only a rough placeholder."
    warnings = ch6.research_gap_warnings(payload)
    assert not any("depreciation rough proxy" in warning.lower() for warning in warnings)


def test_save_load_preserves_deleted_default_reserve_rows(tmp_path):
    original = ch6.DB_PATH
    ch6.DB_PATH = tmp_path / "chapter6.db"
    try:
        payload = ch6.empty_payload("DGC")
        payload["q27_accounting_quality"] = []
        payload["question_status"]["Q27"] = "Partial"
        ch6.save_record("DGC", payload, "Duc Giang Chemicals")

        loaded = ch6.load_record("DGC")
        assert loaded["q27_accounting_quality"] == []
        assert loaded["question_status"]["Q27"] == "Partial"
        assert loaded["company_name"] == "Duc Giang Chemicals"
    finally:
        ch6.DB_PATH = original


def test_save_load_and_snapshot_round_trip(tmp_path):
    original = ch6.DB_PATH
    ch6.DB_PATH = tmp_path / "chapter6.db"
    try:
        payload = ch6.empty_payload("HPG", "Hoa Phat")
        payload["question_status"]["Q31"] = "Answered"
        payload["q31"]["ccc_change_quality"] = "Temporary"
        payload["q31_working_capital"] = [
            {
                "Component / Mechanism": "Accounts payable",
                "Cash Absorbed / Released": "Released",
                "Business Driver": "Longer supplier terms",
                "Sustainable / Temporary / Unknown": "Temporary",
                "Customer / Supplier Consequence": "Supplier terms may normalize",
                "Normalization Needed?": "Yes",
                "Supporting Evidence": "Annual report",
                "Counter-Evidence": "",
                "Analyst Assessment": "Do not extrapolate",
            }
        ]
        payload["earnings_distribution_width"] = "Medium"
        payload["earnings_distribution_matrix"][4]["Effect on Distribution"] = "Wider"

        saved = ch6.save_record("HPG", payload, "Hoa Phat")
        loaded = ch6.load_record("HPG")
        assert loaded["q31"]["ccc_change_quality"] == "Temporary"
        assert loaded["q31_working_capital"][0]["Normalization Needed?"] == "Yes"
        assert loaded["earnings_distribution_width"] == "Medium"
        assert loaded["earnings_distribution_matrix"][4]["Effect on Distribution"] == "Wider"

        snapshot_id = ch6.create_snapshot("HPG", saved)
        assert snapshot_id >= 1
        snapshots = ch6.list_snapshots("HPG")
        assert snapshots[0]["id"] == snapshot_id
    finally:
        ch6.DB_PATH = original


def test_research_gap_warnings_do_not_treat_missing_evidence_as_quality():
    payload = ch6.empty_payload("MWG")
    payload["q28"]["overall_assessment"] = "Predominantly recurring"
    payload["q28_revenue_streams"] = []
    payload["q32"]["maintenance_vs_growth_split"] = "Supportable"
    payload["q32_capex_register"] = []

    warnings = ch6.research_gap_warnings(payload)
    assert any("Q28" in warning for warning in warnings)
    assert any("Q32" in warning for warning in warnings)


def test_distribution_width_requires_matrix_effects():
    payload = ch6.empty_payload("MWG")
    payload["earnings_distribution_width"] = "Wide"
    warnings = ch6.research_gap_warnings(payload)
    assert any("Effect on Distribution" in warning for warning in warnings)


def test_completion_status_is_research_completion_not_investment_signal(tmp_path):
    original = ch6.DB_PATH
    ch6.DB_PATH = tmp_path / "chapter6.db"
    try:
        payload = ch6.empty_payload("VCB")
        for q in ch6.QUESTION_KEYS:
            payload["question_status"][q] = "Answered"
        ch6.save_record("VCB", payload)
        assert ch6.list_snapshots("VCB") == []
        assert "research_gate" not in payload
        assert "recommendation" not in payload
        assert "buy_sell" not in payload
    finally:
        ch6.DB_PATH = original
