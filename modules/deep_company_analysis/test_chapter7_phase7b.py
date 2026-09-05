from __future__ import annotations

import json

import pandas as pd

import modules.deep_company_analysis.chapter7 as ch7
import modules.deep_company_analysis.chapter7_data_bridge as b


def _meta(record_type: str, title: str = "Official disclosure") -> b.SourceMeta:
    return b.SourceMeta(
        title=title,
        source_type="Exchange/regulator disclosure",
        source_url_or_file="official.csv",
        source_grade="A — Primary official",
        publication_date="05/09/2026",
        effective_date="01/09/2026",
        as_of_date="01/09/2026",
        record_type=record_type,
    )


def test_role_normalization_keeps_phase7b_deterministic():
    assert b.normalize_role("Tổng Giám đốc") == "CEO"
    assert b.normalize_role("Giám đốc Tài chính") == "CFO"
    assert b.normalize_role("Thành viên HĐQT độc lập") == "Independent Director"
    assert b.normalize_role("Một chức danh lạ") == "Other"


def test_stable_manager_id_and_possible_match_do_not_auto_merge():
    a = b.stable_manager_id("FPT", "Nguyễn Văn A")
    assert a == b.stable_manager_id("FPT", "Nguyen Van A")
    suggestions = b.suggest_identity_matches("Nguyễn Văn Anh", ["Nguyen Van An", "Tran B"], threshold=0.70)
    assert suggestions
    assert all("do not auto-merge" in row["action"] for row in suggestions)


def test_date_precision_never_invents_month_or_day():
    assert b.parse_date_with_precision("2022") == ("2022", "Year only")
    value, precision = b.parse_date_with_precision("01/09/2026")
    assert value == "01/09/2026"
    assert precision == "Exact date"


def test_registered_and_executed_insider_shares_are_separate():
    row = {
        "Manager": "A",
        "Role": "CEO",
        "Transaction": "Mua",
        "Registered Shares": 1_000_000,
        "Executed Shares": 300_000,
        "Ownership Before": 2_000_000,
        "Price": 20_000,
    }
    out = b.normalize_structured_row("ABC", "insider", row, _meta("insider"))
    assert out["Registered Shares"] == 1_000_000
    assert out["Executed Shares"] == 300_000
    assert out["Shares"] == 300_000
    assert out["% of Existing Ownership"] == 15.0
    assert out["Transaction Value (tỷ)"] == 6.0
    assert out["Analyst Interpretation"] == ""


def test_compensation_aggregate_is_not_allocated_to_fake_manager():
    row = {"Compensation Scope": "Board aggregate", "Year": "2025", "Total Compensation": 12.0}
    out = b.normalize_structured_row("ABC", "compensation", row, _meta("compensation"))
    assert out["Manager"] == "Board aggregate"
    assert out["Manager ID"] == ""
    assert "aggregate_only" in out["Data Quality Flags"]
    assert out["Total Compensation (tỷ)"] == 12.0


def test_ownership_keeps_actual_options_rsu_unvested_separate():
    row = {
        "Manager": "A",
        "As-of Date": "31/12/2025",
        "Actual Shares": 1000,
        "Options": 2000,
        "RSU": 3000,
        "Unvested Awards": 4000,
    }
    out = b.normalize_structured_row("ABC", "ownership", row, _meta("ownership"))
    assert out["Actual Shares"] == 1000
    assert out["Options"] == 2000
    assert out["RSU / Restricted"] == 3000
    assert out["Unvested Awards"] == 4000


def test_career_year_only_and_gap_reason_remain_unknown():
    row = {"Manager": "A", "From": "2018", "To": "2021", "Company": "ABC", "Role": "COO"}
    out = b.normalize_structured_row("ABC", "career", row, _meta("career"))
    assert out["From"] == "2018"
    assert out["To"] == "2021"
    assert out["Career Gap?"] == "Unknown"
    assert out["Gap Explanation"] == "Unknown"
    assert "Year only" in out["Date Precision"]


def test_event_mapping_creates_review_questions_without_changing_answers():
    row = {"Manager": "New CEO", "Event Type": "CEO appointed", "Event": "Appointment", "Effective Date": "01/09/2026"}
    out = b.normalize_structured_row("ABC", "event", row, _meta("event"))
    assert out["Questions to Review"] == "Q33,Q34,Q36"
    assert out["Review Status"] == "Open"


def test_apply_candidates_does_not_overwrite_analyst_conclusions(tmp_path):
    original_core = ch7.DB_PATH
    original_bridge = b.DB_PATH
    db = tmp_path / "chapter7.db"
    ch7.DB_PATH = db
    b.DB_PATH = db
    try:
        payload = ch7.empty_payload("ABC", "ABC Co")
        payload["question_status"]["Q33"] = "Answered"
        payload["q33"]["analyst_classification"] = "LT1"
        payload["final_management_classification"] = "LT1"
        payload["analyst_summary"] = "Analyst-owned conclusion"
        result = b.ingest_structured_rows(
            "ABC",
            "roster",
            [{"Manager": "New CEO", "Current Role": "Tổng Giám đốc", "Founder?": "No"}],
            _meta("roster"),
        )
        assert result["candidate_count"] == 1
        candidate_id = result["candidate_ids"][0]
        updated, stats = b.apply_candidate_ids("ABC", payload, [candidate_id])
        assert stats["applied"] == 1
        assert updated["management_profiles"][0]["Current Role"] == "CEO"
        assert updated["management_profiles"][0]["Suggested Classification"] == "Unknown"
        assert updated["q33"]["analyst_classification"] == "LT1"
        assert updated["question_status"]["Q33"] == "Answered"
        assert updated["final_management_classification"] == "LT1"
        assert updated["analyst_summary"] == "Analyst-owned conclusion"
    finally:
        ch7.DB_PATH = original_core
        b.DB_PATH = original_bridge


def test_duplicate_and_changed_same_key_are_not_silently_overwritten(tmp_path):
    original_core = ch7.DB_PATH
    original_bridge = b.DB_PATH
    db = tmp_path / "chapter7.db"
    ch7.DB_PATH = db
    b.DB_PATH = db
    try:
        meta = _meta("ownership")
        first = b.ingest_structured_rows("ABC", "ownership", [{"Manager": "A", "As-of Date": "31/12/2025", "Actual Shares": 1000}], meta)
        duplicate = b.ingest_structured_rows("ABC", "ownership", [{"Manager": "A", "As-of Date": "31/12/2025", "Actual Shares": 1000}], meta)
        changed = b.ingest_structured_rows("ABC", "ownership", [{"Manager": "A", "As-of Date": "31/12/2025", "Actual Shares": 1200}], meta)
        assert first["candidate_count"] == 1
        assert duplicate["duplicate_count"] == 1
        assert changed["candidate_count"] == 1
        assert changed["conflict_count"] >= 1
        conflicts = b.list_conflicts("ABC", "Needs analyst review")
        assert conflicts
    finally:
        ch7.DB_PATH = original_core
        b.DB_PATH = original_bridge


def test_structured_csv_parser_and_pdf_guardrail():
    rows = b.parse_structured_bytes(b"Manager,Role\nA,CEO\n", "roster.csv", "roster")
    assert rows == [{"Manager": "A", "Role": "CEO"}]
    try:
        b.parse_structured_bytes(b"%PDF", "report.pdf", "roster")
    except ValueError as exc:
        assert "unstructured" in str(exc).lower()
    else:
        raise AssertionError("PDF must not be guessed in Phase 7B")


def test_status_frame_is_event_as_of_not_ttm(tmp_path):
    original_core = ch7.DB_PATH
    original_bridge = b.DB_PATH
    db = tmp_path / "chapter7.db"
    ch7.DB_PATH = db
    b.DB_PATH = db
    try:
        b.ingest_structured_rows("ABC", "ownership", [{"Manager": "A", "As-of Date": "31/12/2025", "Actual Shares": 1000}], _meta("ownership"))
        frame = b.bridge_status_frame("ABC")
        assert isinstance(frame, pd.DataFrame)
        assert "TTM" not in frame.to_string().upper()
        assert "Latest As-of / Effective" in frame.columns
    finally:
        ch7.DB_PATH = original_core
        b.DB_PATH = original_bridge


def test_no_management_quality_or_buy_sell_signal_in_bridge_contract():
    contract = " ".join([
        b.__doc__ or "",
        json.dumps(b.EVENT_REVIEW_MAP),
        " ".join(b.RECORD_TYPES),
    ]).lower()
    assert "no automatic" in contract
    assert "buy/sell signal" in contract
    assert "management quality" in contract
