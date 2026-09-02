from modules.deep_company_analysis.chapter2_evidence import _topic_rows
from modules.deep_company_analysis.chapter2_auto import classify_evidence, extract_timeline_candidates, extract_foreign_market_candidates

import pandas as pd


def test_official_source_rows_feed_q3_q5_q6_without_inventing_data():
    text = """
    Sản phẩm chính gồm phốt pho vàng, axit phosphoric và phân bón.
    Công ty được thành lập từ năm 1963.
    Năm 2018 mua 51% một công ty phốt pho.
    Năm 2023 mua 100% Phốt pho 6, mở rộng công suất.
    Phốt pho vàng chủ yếu được xuất khẩu sang Nhật Bản và Hàn Quốc.
    Giá bán xuất khẩu được niêm yết bằng USD; công ty có rủi ro tỷ giá.
    """
    rows = _topic_rows(
        ticker="DGC",
        page_title="Nguồn chính thức",
        url="https://ducgiangchem.vn/example",
        text=text,
        source_kind="official",
    )
    df = pd.DataFrame(rows)
    sections = classify_evidence(df)
    assert not sections["Q3"].empty
    assert not sections["Q5"].empty
    assert not sections["Q6"].empty

    timeline = extract_timeline_candidates(sections["Q5"])
    assert any(row["Year"] in {"1963", "2018", "2023"} for row in timeline)

    markets = extract_foreign_market_candidates(sections["Q6"])
    names = {row["Country / Region"] for row in markets}
    assert "Nhật Bản" in names
    assert "Hàn Quốc" in names
    # Multiple countries in one evidence snippet => never assign a fabricated per-country share.
    assert all(row["Revenue share %"] == "" for row in markets)
