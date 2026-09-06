from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter6_format import (
    financial_table_html,
    format_numeric,
    infer_numeric_kind,
)


def test_chapter6_numeric_format_rules():
    assert infer_numeric_kind("Amount (tỷ)") == "amount_bil"
    assert infer_numeric_kind("Revenue Share (%)") == "percent"
    assert infer_numeric_kind("Debt / EBITDA (x)") == "ratio"
    assert format_numeric(1234.56, "amount_bil") == "1.235"
    assert format_numeric(12.34, "percent") == "12,3%"
    assert format_numeric(1.234, "ratio") == "1,2x"


def test_chapter6_html_table_wrap_and_heatmap():
    frame = pd.DataFrame(
        {
            "Amount (tỷ)": [-100.0, 200.0],
            "Revenue Share (%)": [-5.25, 10.25],
            "Note": ["negative", "positive"],
        }
    )
    html = financial_table_html(frame)
    assert "table-layout:fixed" in html
    assert "white-space:normal" in html
    assert "overflow-wrap:anywhere" in html
    assert "#991B1B" in html
    assert "#047857" in html
    assert "-100" in html
    assert "200" in html
    assert "-5,2%" in html
    assert "10,2%" in html


def test_chapter6_html_escapes_text():
    frame = pd.DataFrame({"Note": ["<script>alert(1)</script>"]})
    html = financial_table_html(frame)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
