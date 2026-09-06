import warnings

import pandas as pd
from pandas.errors import SettingWithCopyWarning

import modules.deep_company_analysis.chapter5_quant as ch5q
from modules.deep_company_analysis.chapter7_closure import career_coverage_audit


def test_chapter5_annual_filter_does_not_emit_settingwithcopy_warning():
    frame = pd.DataFrame([
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 100.0},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 120.0},
        {"period": "TTM", "period_type": "Y", "year": 2026, "revenue_bil": 130.0},
    ])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rows = ch5q._annual_rows(frame)
    assert [row["period"] for row in rows] == ["2024", "2025"]
    assert not [item for item in caught if issubclass(item.category, SettingWithCopyWarning)]


def test_chapter7_career_audit_value_column_is_homogeneous_for_arrow():
    payload = {
        "career_timeline": [
            {
                "Manager": "Test Manager",
                "From": "01/01/2020",
                "To": "31/12/2025",
                "Functional Area": "Operations",
                "Career Gap?": "No",
                "Gap Explanation": "",
            }
        ]
    }
    frame = career_coverage_audit(payload)
    assert not frame.empty
    assert frame["Value"].map(lambda value: isinstance(value, str)).all()
