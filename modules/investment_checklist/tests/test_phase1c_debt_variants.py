import json

import pandas as pd

from modules.investment_checklist.trecapital_debt_enricher import augment_debt_from_latest_fireant_raw


def _write_manifest(tmp_path, body):
    payload = {
        "responses": [
            {
                "url": "https://www.fireant.vn/api/Data/Finance/LastestFinancialReports?symbol=DCM&type=1&year=2026&quarter=2&count=20",
                "body": json.dumps(body, ensure_ascii=False),
            }
        ]
    }
    (tmp_path / "fireant_excel_vba_DCM_999.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _frames():
    annual = pd.DataFrame([
        {"ticker": "DCM", "period_type": "Y", "period": "2025", "year": 2025},
    ])
    quarterly = pd.DataFrame([
        {"ticker": "DCM", "period_type": "Q", "period": "Q2/2026", "year": 2026, "quarter": 2},
    ])
    return annual, quarterly


def test_dcm_style_component_lines_are_summed_when_aggregate_absent(tmp_path):
    _write_manifest(
        tmp_path,
        {
            "data": {
                "items": [
                    {"Name": "Vay ngắn hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 3_500_000_000_000}]},
                    {"Name": "Nợ dài hạn đến hạn trả", "Values": [{"Year": 2026, "Quarter": 2, "Value": 50_000_000_000}]},
                    {"Name": "Nợ thuê tài chính ngắn hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 16_000_000_000}]},
                    {"Name": "Vay dài hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 20_000_000_000}]},
                    {"Name": "Nợ thuê tài chính dài hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 4_000_000_000}]},
                ]
            }
        },
    )
    annual, quarterly = _frames()
    _, q, note = augment_debt_from_latest_fireant_raw(annual, quarterly, "DCM", tmp_path)
    row = q.iloc[0]
    assert float(row["short_term_debt_bil"]) == 3566.0
    assert float(row["long_term_debt_bil"]) == 24.0
    assert float(row["interest_bearing_debt_bil"]) == 3590.0
    assert "Debt được phục hồi" in note


def test_aggregate_lines_take_priority_over_detail_to_avoid_double_count(tmp_path):
    _write_manifest(
        tmp_path,
        [
            {"Name": "Vay và nợ thuê tài chính ngắn hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 3_566_000_000_000}]},
            {"Name": "Vay ngắn hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 3_500_000_000_000}]},
            {"Name": "Nợ dài hạn đến hạn trả", "Values": [{"Year": 2026, "Quarter": 2, "Value": 50_000_000_000}]},
            {"Name": "Nợ thuê tài chính ngắn hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 16_000_000_000}]},
            {"Name": "Vay và nợ thuê tài chính dài hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 24_000_000_000}]},
            {"Name": "Trái phiếu phát hành", "Values": [{"Year": 2026, "Quarter": 2, "Value": 500_000_000_000}]},
        ],
    )
    annual, quarterly = _frames()
    _, q, _ = augment_debt_from_latest_fireant_raw(annual, quarterly, "DCM", tmp_path)
    row = q.iloc[0]
    assert float(row["short_term_debt_bil"]) == 3566.0
    assert float(row["long_term_debt_bil"]) == 24.0
    assert float(row["interest_bearing_debt_bil"]) == 3590.0


def test_direct_period_debt_keys_are_supported(tmp_path):
    _write_manifest(
        tmp_path,
        {
            "result": [
                {"Year": 2026, "Quarter": 2, "shortTermDebt": 3_566_000_000_000, "longTermDebt": 24_000_000_000},
            ]
        },
    )
    annual, quarterly = _frames()
    _, q, _ = augment_debt_from_latest_fireant_raw(annual, quarterly, "DCM", tmp_path)
    row = q.iloc[0]
    assert float(row["interest_bearing_debt_bil"]) == 3590.0
