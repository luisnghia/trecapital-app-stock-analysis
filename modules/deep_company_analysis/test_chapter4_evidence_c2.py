from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter4_evidence_c2 import (
    _pricing_candidate_rows,
    _q19_candidate_rows,
    build_competitor_universe,
    guardrails,
    merge_c2_candidates_into_evidence_matrix,
)


def _row(title: str, snippet: str, *, group: str = "Nguồn doanh nghiệp/IR", status: str = "Tìm thấy") -> pd.DataFrame:
    return pd.DataFrame([{
        "Tiêu đề": title,
        "Nguồn/URL": "https://example.com/source",
        "Trích yếu": snippet,
        "Nhóm thông tin": group,
        "Trạng thái": status,
        "Truy vấn": "targeted query with irrelevant keywords",
        "_SourceMethod": "test",
    }])


def test_q16_price_only_is_not_explicit_pricing_power_candidate():
    df = _pricing_candidate_rows(_row("Điều chỉnh giá", "Công ty tăng giá bán 8% trong năm 2025."))
    assert len(df) == 1
    assert "insufficient" in df.iloc[0]["Explicitness"].lower()
    assert "price-only" in df.iloc[0]["Event Type Candidate"].lower()


def test_q16_price_plus_volume_is_explicit_candidate_but_not_conclusion():
    df = _pricing_candidate_rows(_row("Giá và sản lượng", "Năm 2025 công ty tăng giá bán 8% trong khi sản lượng tiêu thụ ổn định."))
    assert len(df) == 1
    assert str(df.iloc[0]["Explicitness"]).startswith("Explicit price + customer/volume")
    assert df.iloc[0]["Direction"] == "Neutral — Candidate"
    assert guardrails()["auto_pricing_power_conclusion"] is False


def test_q16_commodity_context_is_not_pricing_power():
    df = _pricing_candidate_rows(_row("Giá thị trường", "Giá bán tăng do giá nguyên liệu và cung cầu phosphorus tăng mạnh."))
    assert len(df) == 1
    assert "commodity" in df.iloc[0]["Event Type Candidate"].lower()
    assert guardrails()["treat_commodity_price_as_pricing_power"] is False


def test_pricing_classifier_ignores_query_only_keywords():
    # The targeted query contains pricing words, but evidence text does not. It must not become evidence.
    raw = _row("Thông báo doanh nghiệp", "Doanh nghiệp tổ chức đại hội cổ đông thường niên.")
    raw.loc[:, "Truy vấn"] = "tăng giá sản lượng khách hàng"
    assert _pricing_candidate_rows(raw).empty


def test_q19_classifies_key_shearn_subtopics():
    cases = [
        ("Sản phẩm thay thế", "Khách hàng chuyển sang substitute có giá thấp hơn.", "Substitute Products"),
        ("Cạnh tranh nhập khẩu", "Sản phẩm nhập khẩu từ Trung Quốc tạo áp lực cạnh tranh.", "Low-cost Country Competition"),
        ("Price war", "Các doanh nghiệp bước vào chiến tranh giá.", "Fierceness / Price Competition"),
        ("Đối thủ rút lui", "Một đối thủ lỗ nặng và rút lui khỏi thị trường.", "Why Competitors Failed"),
    ]
    for title, snippet, expected in cases:
        df = _q19_candidate_rows(_row(title, snippet, group="Dữ liệu/tin tài chính"))
        assert not df.empty
        assert df.iloc[0]["Subtopic"] == expected


def test_q19_classifier_ignores_query_only_competition_terms():
    raw = _row("Báo cáo kết quả", "Doanh thu năm 2025 tăng 10%.")
    raw.loc[:, "Truy vấn"] = "đối thủ cạnh tranh thị phần price war"
    assert _q19_candidate_rows(raw).empty


def test_competitor_universe_excludes_target_and_sorts_market_cap():
    peers = pd.DataFrame([
        {"ticker": "DGC", "company_name": "Target", "market_cap_bil": 1000, "industry": "Hóa chất"},
        {"ticker": "AAA", "company_name": "A", "market_cap_bil": 500, "industry": "Hóa chất"},
        {"ticker": "BBB", "company_name": "B", "market_cap_bil": 900, "industry": "Hóa chất"},
    ])
    out = build_competitor_universe(peers, "DGC", max_peers=10)
    assert out["Ticker"].tolist() == ["BBB", "AAA"]
    assert all("analyst verify" in str(x).lower() for x in out["Status"])


def test_merge_preserves_analyst_judgements():
    record = {
        "q16": {"pricing_power": "Moderate", "conclusion": "Analyst conclusion"},
        "q19": {"competition_intensity": "High", "conclusion": "Keep"},
        "evidence_matrix": [],
    }
    candidates = pd.DataFrame([{
        "Question": "Q16",
        "Subtopic": "Actual Pricing / Customer Response",
        "Direction": "Neutral — Candidate",
        "Evidence Quality": "A — Company/Official disclosure",
        "Explicitness": "Explicit price + customer/volume candidate",
        "Event Type Candidate": "Price + customer/volume response candidate — analyst verify",
        "Period Candidate": "2025",
        "Title": "Pricing evidence",
        "URL": "https://example.com/source",
        "Snippet": "Giá bán tăng trong khi sản lượng ổn định.",
        "Source Method": "test",
    }])
    merged = merge_c2_candidates_into_evidence_matrix(record, candidates)
    assert merged["q16"]["pricing_power"] == "Moderate"
    assert merged["q16"]["conclusion"] == "Analyst conclusion"
    assert merged["q19"]["competition_intensity"] == "High"
    assert merged["q19"]["conclusion"] == "Keep"
    assert merged["evidence_matrix"][0]["Status"] == "Candidate — Analyst verify"
    assert "Phase 4C.2" in merged["evidence_matrix"][0]["Data Origin"]


def test_phase4c2_guardrails_all_locked_false():
    assert all(value is False for value in guardrails().values())
