from types import SimpleNamespace

import pandas as pd

import module2_dashboard as dashboard
from module2_engine import classify_company


def _bank_company():
    return SimpleNamespace(
        ticker="VCB",
        company_name="Ngân hàng TMCP Ngoại thương Việt Nam",
        exchange="HOSE",
        industry="1357",
        sub_industry="1357",
        current_price=59_100,
        market_cap_bil=493_820,
        pe=13.7,
        pb=2.1,
        roe=16.7,
        roic=None,
    )


def _bank_annual():
    return pd.DataFrame(
        {
            "period": ["2021", "2022", "2023", "2024", "2025", "TTM"],
            "net_profit_bil": [27_000, 29_000, 33_000, 36_000, 40_000, 42_000],
            "roe_actual_pct": [20.9, 24.0, 21.6, 18.4, 16.5, 16.7],
            # These industrial fields may be present in a generic feed but must be ignored.
            "roic_standard_pct": [10, 11, 12, 13, 14, 15],
            "gross_margin_pct": [20, 21, 22, 23, 24, 25],
            "net_margin_pct": [20, 21, 22, 23, 24, 25],
            "cfo_to_net_profit": [1.1, 1.2, 1.3, 1.4, 1.5, 1.6],
            "fcf_to_net_profit": [0.8, 0.9, 1.0, 1.1, 1.2, 1.3],
            "net_debt_to_equity": [0.1] * 6,
            "revenue_bil": [100, 110, 120, 130, 140, 150],
        }
    )


def test_financial_classifier_uses_company_name_when_industry_is_numeric():
    result = classify_company(_bank_company(), _bank_annual())
    assert result.company_type == "Financial / Bank / Insurance"


def test_peer_snapshot_never_scores_industrial_metrics_for_bank(monkeypatch):
    company = _bank_company()
    annual = _bank_annual()
    monkeypatch.setattr(dashboard, "_load_data", lambda *args, **kwargs: (company, annual, pd.DataFrame(), "mock", []))
    monkeypatch.setattr(dashboard, "_has_real_financial_data", lambda frame: True)
    monkeypatch.setattr(dashboard, "build_module2_valuation_table", lambda *args, **kwargs: pd.DataFrame([{"x": 1}]))
    monkeypatch.setattr(
        dashboard,
        "build_valuation_range",
        lambda *args, **kwargs: SimpleNamespace(weighted_vnd=50_000, mos_to_weighted_pct=-18.2),
    )
    monkeypatch.setattr(
        dashboard,
        "build_porter_moat_scorecard",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Porter công nghiệp không được chạy cho bank")),
    )

    row, _peer = dashboard._peer_snapshot("VCB", "mock", {}, 30)

    assert row["Loại DN"] == "Financial / Bank / Insurance"
    assert row["ROIC %"] is None
    assert row["Biên gộp %"] is None
    assert row["Biên ròng %"] is None
    assert row["CAGR DT 5Y %"] is None
    assert row["CFO/LNST"] is None
    assert row["FCF/LNST"] is None
    assert row["Nợ ròng/VCSH"] is None
    assert row["Moat score"] is None
    assert row["Moat level"] == "Không chấm Porter công nghiệp"
    assert row["Điểm dòng tiền"] is None
    assert "NIM" in row["Kết luận so sánh"]


def test_financial_peer_summary_and_note_do_not_invent_moat_leaders():
    frame = pd.DataFrame(
        [
            {"Mã": "VCB", "Tên doanh nghiệp": "Ngân hàng VCB", "Loại DN": "Financial / Bank / Insurance", "Điểm tổng hợp": 60, "MOS hiện tại %": -10, "Moat score": None},
            {"Mã": "BID", "Tên doanh nghiệp": "Ngân hàng BID", "Loại DN": "Financial / Bank / Insurance", "Điểm tổng hợp": 55, "MOS hiện tại %": -20, "Moat score": None},
        ]
    )
    summary = dashboard._peer_comparison_summary(frame, 30)
    assert "không chấm Porter công nghiệp" in summary
    assert "VCB, BID" not in summary.split("Các mã có moat score nổi bật:", 1)[1].split(".", 1)[0]

    note = dashboard._build_peer_row_note(frame.iloc[0].to_dict())
    assert "CFO/LNST, FCF/LNST, ROIC" in note
    assert "NIM, CASA, NPL, LLR, CAR, CIR" in note
