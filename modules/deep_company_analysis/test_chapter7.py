from __future__ import annotations

import pandas as pd

import modules.deep_company_analysis.chapter7 as ch7


def test_q33_to_q38_and_taxonomy_are_source_locked():
    payload = ch7.empty_payload("dgc")
    assert payload["ticker"] == "DGC"
    assert set(payload["question_status"]) == {"Q33", "Q34", "Q35", "Q36", "Q37", "Q38"}
    assert ch7.MANAGER_CLASSIFICATION_OPTIONS == (
        "Unknown", "OO1", "OO2", "OO3", "LT1", "LT2", "HH1", "HH2", "Mixed"
    )
    assert set(ch7.MANAGER_CLASSIFICATION_DEFINITIONS) == {"OO1", "OO2", "OO3", "LT1", "LT2", "HH1", "HH2"}


def test_founder_and_outsider_do_not_auto_classify():
    payload = ch7.empty_payload("FPT")
    payload["management_profiles"] = [
        {
            "Manager ID": "m1",
            "Manager": "Founder A",
            "Founder?": "Yes",
            "Suggested Classification": "Unknown",
            "Analyst Classification": "Unknown",
        },
        {
            "Manager ID": "m2",
            "Manager": "Outside B",
            "Founder?": "No",
            "Same Industry": "No",
            "Suggested Classification": "Unknown",
            "Analyst Classification": "Unknown",
        },
    ]
    assert payload["management_profiles"][0]["Suggested Classification"] == "Unknown"
    assert payload["management_profiles"][1]["Suggested Classification"] == "Unknown"
    assert payload["q33"]["analyst_classification"] == "Unknown"


def test_table_7_1_has_exactly_seven_dimensions_and_no_score():
    rows = ch7.default_lion_hyena_rows()
    assert len(rows) == 7
    assert [row["Dimension"] for row in rows] == [d for d, _, _ in ch7.LION_HYENA_DIMENSIONS]
    assert all(row["Evidence Direction"] == "Unknown" for row in rows)
    joined = " ".join(ch7.LION_HYENA_COLUMNS).lower()
    assert "score" not in joined
    assert "weighted" not in joined


def test_q37_keeps_actual_ownership_separate_from_options_rsu_esop():
    cols = set(ch7.OWNERSHIP_HISTORY_COLUMNS)
    assert "Actual Shares" in cols
    assert "Options" in cols
    assert "RSU / Restricted" in cols
    assert "Unvested Awards" in cols
    assert "Ownership Origin" in cols
    comp_cols = set(ch7.COMPENSATION_HISTORY_COLUMNS)
    assert "Options Granted" in comp_cols
    assert "RSU / Restricted Stock" in comp_cols
    assert "ESOP Benefit" in comp_cols


def test_q38_transaction_types_are_not_buy_sell_signal_fields():
    cols = set(ch7.INSIDER_TRANSACTION_COLUMNS)
    assert "Transaction" in cols
    assert "Transaction Type" in cols
    assert "% of Existing Ownership" in cols
    assert "Analyst Interpretation" in cols
    joined = " ".join(cols).lower()
    assert "buy signal" not in joined
    assert "sell signal" not in joined


def test_event_as_of_workspace_has_no_fake_ttm_rows_or_period_columns():
    payload = ch7.empty_payload("VCB")
    event_tables = [
        payload["management_profiles"],
        payload["outside_transitions"],
        payload["career_timeline"],
        payload["compensation_history"],
        payload["ownership_history"],
        payload["insider_transactions"],
        payload["management_events"],
    ]
    assert all(table == [] for table in event_tables)
    column_text = " ".join(
        ch7.MANAGEMENT_PROFILE_COLUMNS
        + ch7.OUTSIDE_TRANSITION_COLUMNS
        + ch7.CAREER_TIMELINE_COLUMNS
        + ch7.COMPENSATION_HISTORY_COLUMNS
        + ch7.OWNERSHIP_HISTORY_COLUMNS
        + ch7.INSIDER_TRANSACTION_COLUMNS
        + ch7.EVENT_COLUMNS
    ).upper()
    assert "TTM" not in column_text
    assert "T12M" not in column_text
    assert "As-of Date" in ch7.OWNERSHIP_HISTORY_COLUMNS
    assert "Transaction Date" in ch7.INSIDER_TRANSACTION_COLUMNS
    assert "Year" in ch7.COMPENSATION_HISTORY_COLUMNS


def test_management_overview_derives_tenure_without_classifying():
    out = ch7.build_management_overview(
        [
            {
                "Manager ID": "m1",
                "Manager": "A",
                "Current Role": "CEO",
                "Joined Company": "01/01/2020",
                "Started Current Role": "01/01/2022",
                "Actual Ownership (%)": 2.5,
                "Suggested Classification": "Unknown",
                "Analyst Classification": "Unknown",
                "Confidence": "Unknown",
            }
        ],
        as_of_date="01/01/2025",
    )
    assert isinstance(out, pd.DataFrame)
    assert out.iloc[0]["Company Tenure (years)"] == 5.0
    assert out.iloc[0]["Current Role Tenure (years)"] == 3.0
    assert out.iloc[0]["Analyst Classification"] == "Unknown"


def test_save_load_snapshot_round_trip(tmp_path):
    original = ch7.DB_PATH
    ch7.DB_PATH = tmp_path / "chapter7.db"
    try:
        payload = ch7.empty_payload("HPG", "Hoa Phat")
        payload["question_status"]["Q33"] = "Answered"
        payload["management_profiles"] = [
            {
                "Manager ID": "m1",
                "Manager": "CEO A",
                "Current Role": "CEO",
                "Founder?": "No",
                "Suggested Classification": "Unknown",
                "Analyst Classification": "LT1",
                "Confidence": "Medium",
            }
        ]
        payload["lion_hyena_matrix"][0]["Manager"] = "CEO A"
        payload["career_timeline"] = [
            {"Manager ID": "m1", "Manager": "CEO A", "From": "2015", "To": "2020", "Company": "HPG", "Role": "COO"}
        ]
        ch7.save_record("HPG", payload, "Hoa Phat")
        loaded = ch7.load_record("HPG")
        assert loaded["company_name"] == "Hoa Phat"
        assert loaded["management_profiles"][0]["Analyst Classification"] == "LT1"
        assert len(loaded["lion_hyena_matrix"]) == 7
        assert loaded["career_timeline"][0]["Role"] == "COO"
        snap_id = ch7.create_snapshot("HPG", loaded)
        assert snap_id >= 1
        assert ch7.list_snapshots("HPG")[0]["id"] == snap_id
    finally:
        ch7.DB_PATH = original


def test_research_gap_warnings_are_completion_evidence_checks_not_quality_scores():
    payload = ch7.empty_payload("MWG")
    payload["question_status"]["Q37"] = "Answered"
    payload["question_status"]["Q38"] = "Answered"
    warnings = ch7.research_gap_warnings(payload)
    assert any("Q37" in warning for warning in warnings)
    assert any("Q38" in warning for warning in warnings)
    assert not any("score" in warning.lower() for warning in warnings)
