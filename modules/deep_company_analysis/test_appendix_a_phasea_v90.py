from modules.deep_company_analysis import appendix_a as appa


def test_source_lock_and_sections_exact():
    assert appa.APPENDIX_KEY == "A"
    assert appa.APPENDIX_TITLE == "Building a Human Intelligence Network"
    assert appa.SOURCE_PRINT_PAGES == (323, 330)
    assert appa.SECTION_KEYS == (
        "evaluating_information_sources",
        "locating_human_sources",
        "contacting_human_sources",
        "interview_database",
    )
    assert appa.SECTION_SOURCE_PAGES == {
        "evaluating_information_sources": 324,
        "locating_human_sources": 324,
        "contacting_human_sources": 328,
        "interview_database": 329,
    }


def test_primary_secondary_source_lock():
    assert appa.SOURCE_CLASS_OPTIONS == ("Primary", "Secondary", "Unknown")
    assert "First-hand knowledge" in appa.SOURCE_CLASS_DEFINITIONS["Primary"]
    assert "Interprets information" in appa.SOURCE_CLASS_DEFINITIONS["Secondary"]
    assert appa.classify_source("primary") == "Primary"
    assert appa.classify_source("secondary") == "Secondary"
    assert appa.classify_source("score 10") == "Unknown"


def test_source_types_are_appendix_a_grounded():
    expected = {
        "Customer",
        "Journalist",
        "Industry conference participant",
        "Industry insider / associate",
        "Professor / business-school dean",
        "Headhunter / recruiter",
        "Management",
        "Employee",
        "Supplier",
        "Competitor",
    }
    assert expected.issubset(set(appa.HUMAN_SOURCE_TYPES))


def test_interview_statement_types_follow_book():
    expected = {"Assumption", "Theory", "Fact", "Question", "Idea", "Related point", "Unknown"}
    assert set(appa.NOTE_STATEMENT_TYPES) == expected


def test_unknown_first_payload_and_normalization():
    payload = appa.empty_payload("fpt", "FPT")
    assert payload["ticker"] == "FPT"
    assert all(v == "Unknown" for v in payload["sections"].values())
    assert payload["sources"] == []
    assert payload["interviews"] == []
    assert payload["research_gaps"] == []
    dirty = {
        "ticker": " hpg ",
        "sections": {"evaluating_information_sources": "Covered", "locating_human_sources": "BUY"},
        "sources": "not-a-list",
        "interviews": None,
        "research_gaps": {},
        "source_lock": "override",
    }
    clean = appa.normalize_payload(dirty)
    assert clean["ticker"] == "HPG"
    assert clean["source_lock"] == appa.SOURCE_LOCK
    assert clean["sections"]["evaluating_information_sources"] == "Covered"
    assert clean["sections"]["locating_human_sources"] == "Unknown"
    assert clean["sources"] == [] and clean["interviews"] == [] and clean["research_gaps"] == []


def test_notes_keep_source_response_separate_from_analyst_commentary():
    assert "Source Response / Observation" in appa.INTERVIEW_NOTE_COLUMNS
    assert "Analyst Commentary" in appa.INTERVIEW_NOTE_COLUMNS
    assert appa.INTERVIEW_NOTE_COLUMNS.index("Source Response / Observation") != appa.INTERVIEW_NOTE_COLUMNS.index("Analyst Commentary")


def test_research_warnings_are_completeness_only():
    warnings = appa.research_gap_warnings(appa.empty_payload("MWG"))
    assert len(warnings) == 4
    text = " ".join(warnings).lower()
    assert "buy" not in text and "sell" not in text and "hold" not in text
    assert "score" not in text and "mos" not in text


def test_module_has_no_automatic_investment_or_scoring_api():
    forbidden = {
        "calculate_score",
        "credibility_score",
        "weighted_score",
        "buy_signal",
        "sell_signal",
        "change_mos",
        "change_research_gate",
    }
    assert forbidden.isdisjoint(set(dir(appa)))
