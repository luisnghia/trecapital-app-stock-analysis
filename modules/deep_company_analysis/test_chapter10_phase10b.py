from __future__ import annotations

from pathlib import Path

import modules.deep_company_analysis.chapter10 as ch10


def test_phase10b_preserves_source_lock_and_exact_question_range() -> None:
    assert ch10.CHAPTER_NUMBER == 10
    assert ch10.CHAPTER_TITLE == "Evaluating Growth Opportunities"
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert ch10.QUESTION_SOURCE_PAGE_RANGES == {
        "Q53": (281, 282),
        "Q54": (282, 283),
        "Q55": (283, 284),
        "Q56": (284, 296),
        "Q57": (296, 303),
    }
    assert all(53 <= int(key[1:]) <= 57 for key in ch10.QUESTION_KEYS)
    assert "Q52" not in ch10.QUESTION_TITLES
    assert "Q58" not in ch10.QUESTION_TITLES


def test_phase10b_dimension_catalog_is_unique_complete_and_ordered() -> None:
    counts = ch10.dimension_count_by_question()
    assert counts == {"Q53": 4, "Q54": 4, "Q55": 4, "Q56": 15, "Q57": 7}
    ids = ch10.dimension_ids()
    assert len(ids) == 34
    assert len(ids) == len(set(ids))
    assert all(dim_id.startswith("q") for dim_id in ids)
    catalog = ch10.dimension_catalog()
    assert len(catalog) == 34
    assert tuple(row["question"] for row in catalog[:4]) == ("Q53",) * 4
    assert catalog[-1]["id"] == "q57_location_discipline"


def test_q53_dimensions_lock_growth_route_and_materiality() -> None:
    joined = " ".join(item["label"] for item in ch10.EVIDENCE_DIMENSIONS["Q53"]).casefold()
    assert "acquisition spend" in joined
    assert "organic" in joined and "serial-acquirer" in joined
    assert "overpayment" in joined and "integration" in joined
    assert "revenue base" in joined


def test_q55_dimensions_lock_profitable_growth_economics() -> None:
    joined = " ".join(item["label"] for item in ch10.EVIDENCE_DIMENSIONS["Q55"]).casefold()
    assert "gross margin" in joined
    assert "operating margin" in joined
    assert "operating profit per unit" in joined
    assert "continue" in joined


def test_q56_dimensions_cover_runway_secular_innovation_market_and_slowdown() -> None:
    joined = " ".join(item["label"] for item in ch10.EVIDENCE_DIMENSIONS["Q56"]).casefold()
    for expected in (
        "md&a", "runway", "replicability", "operating metric", "secular", "commodity-price",
        "r&d", "new products", "transformational", "market size", "shrinking effective market",
        "slowing-growth", "valuation", "management team",
    ):
        assert expected in joined


def test_q57_dimensions_cover_disciplined_growth_capacity_constraints() -> None:
    joined = " ".join(item["label"] for item in ch10.EVIDENCE_DIMENSIONS["Q57"]).casefold()
    for expected in (
        "disciplined", "internally generated cash", "cash-conversion cycle", "profitability",
        "qualified people", "infrastructure", "location",
    ):
        assert expected in joined
    ccc = next(item for item in ch10.EVIDENCE_DIMENSIONS["Q57"] if item["id"] == "q57_cash_conversion_cycle")
    assert "dio" in ccc["ssot_dependency"] and "dso" in ccc["ssot_dependency"] and "dpo" in ccc["ssot_dependency"]


def test_all_dimension_pages_stay_inside_question_source_ranges() -> None:
    for question, dimensions in ch10.EVIDENCE_DIMENSIONS.items():
        q_start, q_end = ch10.QUESTION_SOURCE_PAGE_RANGES[question]
        for item in dimensions:
            start, end = item["pages"]
            assert q_start <= start <= end <= q_end
            assert item["anchor"].strip()
            assert item["ssot_dependency"].strip()


def test_unknown_first_payload_now_tracks_dimension_status_without_auto_assessment() -> None:
    payload = ch10.empty_payload("fpt", "FPT")
    assert payload["ticker"] == "FPT"
    assert set(payload["dimension_status"]) == set(ch10.dimension_ids())
    assert set(payload["dimension_status"].values()) == {"Unknown"}
    assert set(payload["analyst_assessment"].values()) == {"Unknown"}
    assert payload["growth_mode"] == "Unknown"


def test_normalization_drops_unknown_dimension_ids_and_invalid_statuses() -> None:
    payload = ch10.empty_payload("MWG")
    payload["dimension_status"]["q53_acquisition_spend_vs_cfo"] = "Evidence found"
    payload["dimension_status"]["q54_pressure_to_grow"] = "positive"
    payload["dimension_status"]["invented_dimension"] = "Evidence found"
    normalized = ch10.normalize_payload(payload)
    assert normalized["dimension_status"]["q53_acquisition_spend_vs_cfo"] == "Evidence found"
    assert normalized["dimension_status"]["q54_pressure_to_grow"] == "Unknown"
    assert "invented_dimension" not in normalized["dimension_status"]


def test_phase10b_remains_schema_only_and_does_not_create_financial_or_investment_engines() -> None:
    source = Path(ch10.__file__).read_text(encoding="utf-8").casefold()
    for forbidden in (
        "import streamlit", "from streamlit", "import httpx", "import requests", "import sqlite3",
        "import psycopg", "fireant", "simplize", "buy signal", "sell signal", "weighted_growth_score",
    ):
        assert forbidden not in source
    assert "dependency labels only" in source
    assert "duplicate financial ssot" in source
    assert "buy/hold/sell" in source


def test_dimension_labels_are_neutral_research_requirements_not_scores() -> None:
    joined = " ".join(item["label"] for row in ch10.EVIDENCE_DIMENSIONS.values() for item in row).casefold()
    for forbidden in ("score 10", "score 0", "buy", "sell", "hold", "bullish", "bearish"):
        assert forbidden not in joined
