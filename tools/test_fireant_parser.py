from adapters.vn_public_crawler import _normalize_from_payloads


def test_fireant_exact_endpoint_parser_merges_statements_and_ratios():
    """Exercise the V14 endpoint contract, not the removed broad recursive mock shape."""
    income_statement = [
        {
            "ID": 3,
            "Name": "Doanh thu thuần",
            "Level": 1,
            "Values": [
                {"Period": "2025", "Year": 2025, "Quarter": 0, "Value": 1_000_000_000_000},
                {"Period": "Q1/2026", "Year": 2026, "Quarter": 1, "Value": 300_000_000_000},
            ],
        },
        {
            "ID": 19,
            "Name": "Lợi nhuận sau thuế",
            "Level": 1,
            "Values": [
                {"Period": "2025", "Year": 2025, "Quarter": 0, "Value": 100_000_000_000},
                {"Period": "Q1/2026", "Year": 2026, "Quarter": 1, "Value": 30_000_000_000},
            ],
        },
    ]
    annual_info = [
        {
            "Symbol": "DGC",
            "Year": 2025,
            "Quarter": 0,
            "BasicEPS": 5_000,
            "ROE": 0.22,
            "ROA": 0.16,
            "ROIC": 0.24,
        }
    ]
    quarterly_info = [
        {
            "Symbol": "DGC",
            "Year": 2026,
            "Quarter": 1,
            "BasicEPS_MRQ": 1_200,
            "NetSales_MRQ": 300_000_000_000,
            "ROE_TTM": 0.05,
            "ROA_TTM": 0.04,
            "ROIC_TTM": 0.06,
        }
    ]

    result = _normalize_from_payloads(
        [income_statement, annual_info, quarterly_info], [], "DGC", "FireAnt"
    )

    assert len(result.annual) == 1, result.annual
    assert len(result.quarterly) == 1, result.quarterly
    row = result.annual.iloc[0]
    assert int(row["year"]) == 2025
    assert round(float(row["revenue_bil"]), 2) == 1_000.00
    assert round(float(row["roe_pct"]), 2) == 22.00


if __name__ == "__main__":
    test_fireant_exact_endpoint_parser_merges_statements_and_ratios()
    print("FIREANT_PARSER_OK")
