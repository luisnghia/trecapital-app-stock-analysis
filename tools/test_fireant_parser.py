from adapters.vn_public_crawler import _normalize_from_payloads

mock = [
    {"ID": 1, "Name": "Doanh thu thuần", "Level": 1, "Values": [
        {"Period": "2025", "Year": 2025, "Quarter": 0, "Value": 1000000000000},
        {"Period": "Q1/2026", "Year": 2026, "Quarter": 1, "Value": 300000000000},
    ]},
    {"ID": 2, "Name": "Lợi nhuận sau thuế", "Level": 1, "Values": [
        {"Period": "2025", "Year": 2025, "Quarter": 0, "Value": 100000000000},
        {"Period": "Q1/2026", "Year": 2026, "Quarter": 1, "Value": 30000000000},
    ]},
    {"Year": 2025, "Quarter": 0, "ROE": 0.22, "ROA": 0.16, "ROIC": 0.24},
    {"Year": 2026, "Quarter": 1, "ROE": 0.05, "ROA": 0.04, "ROIC": 0.06},
]

res = _normalize_from_payloads(mock, [], "DGC", "FireAnt")
assert len(res.annual) == 1, res.annual
assert len(res.quarterly) == 1, res.quarterly
row = res.annual.iloc[0]
assert int(row["year"]) == 2025
assert round(float(row["revenue_bil"]), 2) == 1000.00
assert round(float(row["roe_pct"]), 2) == 22.00
print("FIREANT_PARSER_OK")
