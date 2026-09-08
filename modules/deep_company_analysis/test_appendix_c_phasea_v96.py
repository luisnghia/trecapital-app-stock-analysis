from modules.deep_company_analysis import appendix_c as appc


def test_appendix_c_source_lock_identity():
    assert appc.APPENDIX_KEY == "C"
    assert appc.APPENDIX_TITLE == "Your Investment Checklist"
    assert appc.SOURCE_PRINT_PAGES == (335, 338)
    assert appc.QUESTION_COUNT == 59
    assert appc.QUESTION_RANGE == (1, 59)


def test_exact_continuous_q01_q59_order():
    expected = tuple(f"Q{i:02d}" for i in range(1, 60))
    assert appc.QUESTION_IDS == expected
    assert len(appc.CHECKLIST_ITEMS) == 59
    assert len(set(appc.QUESTION_IDS)) == 59


def test_exact_ten_section_order_and_counts():
    assert len(appc.SECTION_ORDER) == 10
    assert tuple(appc.SECTION_COUNTS) == appc.SECTION_ORDER
    assert tuple(appc.SECTION_COUNTS.values()) == (6, 8, 6, 6, 6, 6, 9, 5, 5, 2)
    assert sum(appc.SECTION_COUNTS.values()) == 59


def test_source_anchor_questions_match_appendix_c():
    assert appc.QUESTION_TITLES["Q01"] == "Do I want to spend a lot of time learning about this business?"
    assert appc.QUESTION_TITLES["Q06"].startswith("In what foreign markets")
    assert appc.QUESTION_TITLES["Q07"] == "Who is the core customer of the business?"
    assert appc.QUESTION_TITLES["Q14"].startswith("If the business disappeared tomorrow")
    assert appc.QUESTION_TITLES["Q15"].startswith("Does the business have a sustainable competitive advantage")
    assert appc.QUESTION_TITLES["Q26"] == "What is the return on invested capital for the business?"
    assert appc.QUESTION_TITLES["Q33"] == "What type of manager is leading the company?"
    assert appc.QUESTION_TITLES["Q38"] == "Have the managers been buying or selling the stock?"
    assert appc.QUESTION_TITLES["Q48"] == "Does the CEO love the money or the business?"
    assert appc.QUESTION_TITLES["Q53"].startswith("Does the business grow through mergers and acquisitions")
    assert appc.QUESTION_TITLES["Q58"] == "How does management make M&A decisions?"
    assert appc.QUESTION_TITLES["Q59"] == "Have past acquisitions been successful?"


def test_owner_chapter_mapping_is_referential_and_book_aligned():
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q01"] == 2
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q07"] == 3
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q15"] == 4
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q21"] == 5
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q27"] == 6
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q33"] == 7
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q39"] == 8
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q48"] == 9
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q53"] == 10
    assert appc.OWNER_CHAPTER_BY_QUESTION["Q58"] == 11


def test_every_item_references_existing_q_ssot_without_answer_state():
    forbidden = {
        "answer", "evidence", "financials", "valuation", "intrinsic_value", "margin_of_safety",
        "mos", "research_gate", "confidence", "score", "weighted_score", "recommendation",
        "buy", "hold", "sell",
    }
    for item in appc.CHECKLIST_ITEMS:
        assert item["ssot_reference"] == item["question_id"]
        assert forbidden.isdisjoint(set(item))


def test_reference_helpers_do_not_create_new_state():
    assert appc.get_item("q59")["question_id"] == "Q59"
    assert appc.get_item("q60") is None
    assert tuple(x["question_id"] for x in appc.items_for_section("mergers_acquisitions")) == ("Q58", "Q59")
    assert appc.ssot_references(["q59", "q01", "bad"]) == ("Q01", "Q59")
    assert appc.ssot_references() == appc.QUESTION_IDS


def test_source_lock_validator_passes():
    assert appc.validate_source_lock() == ()


def test_module_has_no_scoring_valuation_or_recommendation_api():
    forbidden_api = {
        "calculate_score", "weighted_score", "management_score", "growth_score", "buy_signal",
        "sell_signal", "hold_signal", "calculate_intrinsic_value", "change_mos",
        "change_research_gate", "investment_research_gate",
    }
    assert forbidden_api.isdisjoint(set(dir(appc)))
