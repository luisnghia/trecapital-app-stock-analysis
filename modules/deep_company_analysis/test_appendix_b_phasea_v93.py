from modules.deep_company_analysis import appendix_b as appb


def test_source_lock_and_sections_exact():
    assert appb.APPENDIX_KEY == "B"
    assert appb.APPENDIX_TITLE == "How to Interview the Management Team"
    assert appb.SOURCE_PRINT_PAGES == (331, 334)
    assert appb.SECTION_KEYS == (
        "ask_open_ended_questions",
        "face_to_face_assessment_danger",
    )


def test_open_ended_protocol_is_source_locked():
    text = " ".join(appb.INTERVIEW_PROTOCOL).lower()
    assert "open-ended" in text
    assert "listen" in text
    assert "clarify" in text or "re-ask" in text
    assert "past behavior" in text
    assert "hypothetical" in text


def test_management_topic_clusters_are_book_grounded():
    assert len(appb.MANAGEMENT_INTERVIEW_TOPICS) == 8
    text = " ".join(appb.MANAGEMENT_INTERVIEW_TOPICS).lower()
    for term in ("management style", "operational changes", "challenges", "career", "mistakes", "succession"):
        assert term in text


def test_face_to_face_caveats_are_not_quality_signals():
    text = " ".join(appb.FACE_TO_FACE_CAVEATS).lower()
    assert "false confidence" in text
    assert "visual" in text or "body-language" in text
    assert "liking" in text or "similarity" in text
    assert "accessibility" in text or "charisma" in text


def test_contextual_checks_preserve_analyst_review():
    text = " ".join(appb.CONTEXTUAL_CHECKS).lower()
    assert "operating record" in text
    assert "accomplishments" in text
    assert "other informed managers" in text
    assert "thinks, operates and measures" in text


def test_unknown_first_payload_and_normalization():
    payload = appb.empty_payload("fpt", "FPT")
    assert payload["ticker"] == "FPT"
    assert all(v == "Unknown" for v in payload["sections"].values())
    dirty = {
        "ticker": " hpg ",
        "sections": {"ask_open_ended_questions": "Covered", "face_to_face_assessment_danger": "BUY"},
        "sessions": "bad",
        "contextual_checks": None,
        "research_gaps": {},
        "source_lock": "override",
    }
    clean = appb.normalize_payload(dirty)
    assert clean["ticker"] == "HPG"
    assert clean["source_lock"] == appb.SOURCE_LOCK
    assert clean["sections"]["ask_open_ended_questions"] == "Covered"
    assert clean["sections"]["face_to_face_assessment_danger"] == "Unknown"
    assert clean["sessions"] == [] and clean["contextual_checks"] == [] and clean["research_gaps"] == []


def test_session_notes_keep_management_response_separate_from_analyst_commentary():
    assert "Management Response / Observation" in appb.SESSION_NOTE_COLUMNS
    assert "Analyst Commentary" in appb.SESSION_NOTE_COLUMNS
    assert "Face-to-Face Caveat Noted" in appb.SESSION_NOTE_COLUMNS


def test_research_warnings_are_completeness_only():
    warnings = appb.research_gap_warnings(appb.empty_payload("MWG"))
    assert len(warnings) == 2
    text = " ".join(warnings).lower()
    for forbidden in ("buy", "sell", "hold", "score", "mos"):
        assert forbidden not in text


def test_module_has_no_automatic_management_or_investment_scoring_api():
    forbidden = {
        "calculate_score", "management_score", "ceo_quality_score", "credibility_score",
        "personality_score", "weighted_score", "buy_signal", "sell_signal",
        "change_mos", "change_research_gate",
    }
    assert forbidden.isdisjoint(set(dir(appb)))
