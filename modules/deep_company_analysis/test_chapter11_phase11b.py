from modules.deep_company_analysis import chapter11 as ch11


def test_source_lock_exact():
    assert ch11.CHAPTER_NUMBER == 11
    assert ch11.CHAPTER_TITLE == "Evaluating Mergers & Acquisitions"
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.QUESTION_SOURCE_PAGES == {"Q58": 305, "Q59": 310}
    assert ch11.QUESTION_SOURCE_PAGE_RANGES == {"Q58": (305, 310), "Q59": (310, 322)}


def test_dimension_counts_and_unique_ids():
    assert ch11.dimension_count_by_question() == {"Q58": 8, "Q59": 7}
    ids = ch11.dimension_ids()
    assert len(ids) == 15
    assert len(ids) == len(set(ids))


def test_q59_locks_seven_book_lenses():
    ids = set(ch11.dimension_ids("Q59"))
    assert ids == {
        "q59_core_competency_fit",
        "q59_management_understands_target",
        "q59_customer_retention",
        "q59_employee_retention",
        "q59_price_discipline_and_walkaway",
        "q59_price_paid_and_postdeal_economics",
        "q59_financing_and_risk_tolerance",
    }


def test_unknown_first_payload_covers_all_dimensions():
    payload = ch11.empty_payload("abc", "ABC Corp")
    assert payload["ticker"] == "ABC"
    assert payload["question_status"] == {"Q58": "Unknown", "Q59": "Unknown"}
    assert payload["confidence"] == {"Q58": "Unknown", "Q59": "Unknown"}
    assert payload["analyst_assessment"] == {"Q58": "Unknown", "Q59": "Unknown"}
    assert set(payload["dimension_status"]) == set(ch11.dimension_ids())
    assert all(value == "Unknown" for value in payload["dimension_status"].values())


def test_normalize_restores_source_lock_and_drops_foreign_dimensions():
    payload = ch11.normalize_payload({
        "ticker": " xyz ",
        "source_lock": "runtime override",
        "source_question_range": "Q1-Q99",
        "dimension_status": {"q59_customer_retention": "Evidence found", "foreign": "Evidence found"},
    })
    assert payload["ticker"] == "XYZ"
    assert payload["source_lock"] == ch11.SOURCE_LOCK
    assert payload["source_question_range"] == "Q58-Q59"
    assert "foreign" not in payload["dimension_status"]
    assert payload["dimension_status"]["q59_customer_retention"] == "Evidence found"


def test_catalog_positions_restart_by_question():
    rows = ch11.dimension_catalog()
    assert len(rows) == 15
    assert [r["position"] for r in rows if r["question"] == "Q58"] == list(range(1, 9))
    assert [r["position"] for r in rows if r["question"] == "Q59"] == list(range(1, 8))


def test_ssot_dependencies_are_labels_not_calculations():
    dependencies = " ".join(str(r["ssot_dependency"]) for r in ch11.dimension_catalog())
    assert "ebitda" in dependencies
    assert "free_cash_flow" in dependencies
    assert "debt" in dependencies
    assert "book_value" in dependencies


def test_gap_warnings_are_completion_only():
    warnings = ch11.research_gap_warnings(ch11.empty_payload("ABC"))
    assert warnings
    text = " ".join(warnings).lower()
    assert "buy" not in text
    assert "sell" not in text
    assert "successful acquisition" not in text
    assert "failed acquisition" not in text
