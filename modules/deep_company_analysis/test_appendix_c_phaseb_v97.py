from modules.deep_company_analysis import appendix_c as appc
from modules.deep_company_analysis import appendix_c_workspace as ws


def _payload_for(start, end):
    return {
        "question_status": {f"Q{i:02d}": ("Answered" if i % 2 else "Partial") for i in range(start, end + 1)},
        "confidence": {f"Q{i:02d}": "Medium" for i in range(start, end + 1)},
        "analyst_assessment": {f"Q{i:02d}": f"Analyst text {i}" for i in range(start, end + 1)},
        "financials": {"revenue": 123},
        "intrinsic_value": 999,
        "research_gate": "PASS",
    }


def test_live_bridge_keeps_source_order_and_reference_only():
    payloads = {}
    for qid, owner in appc.OWNER_CHAPTER_BY_QUESTION.items():
        payloads.setdefault(owner, {"question_status": {}, "confidence": {}, "analyst_assessment": {}})
        i = int(qid[1:])
        payloads[owner]["question_status"][qid] = "Answered" if i % 2 else "Partial"
        payloads[owner]["confidence"][qid] = "Medium"
        payloads[owner]["analyst_assessment"][qid] = f"A{i}"
        payloads[owner]["financials"] = {"should_not_copy": True}
        payloads[owner]["intrinsic_value"] = 100
    rows = ws.build_live_rows("ABC", owner_payloads=payloads)
    assert len(rows) == 59
    assert tuple(r["question_id"] for r in rows) == appc.QUESTION_IDS
    assert all(r["ssot_reference"] == r["question_id"] for r in rows)
    assert not ws.validate_read_only_rows(rows)
    assert all(not (set(r) & ws.FORBIDDEN_KEYS) for r in rows)


def test_missing_owner_payload_stays_unknown():
    rows = ws.build_live_rows("ABC", owner_payloads={})
    assert all(row["question_status"] == "Unknown" for row in rows)
    assert all(row["confidence"] == "Unknown" for row in rows)


def test_section_summary_is_counts_not_score():
    rows = ws.build_live_rows("ABC", owner_payloads={})
    summary = ws.section_summary(rows)
    assert len(summary) == 10
    assert sum(row["question_count"] for row in summary) == 59
    assert sum(row["unknown"] for row in summary) == 59
    assert all("score" not in row for row in summary)
    assert all("weight" not in row for row in summary)


def test_research_completeness_is_neutral_counts():
    rows = ws.build_live_rows("ABC", owner_payloads={})
    counts = ws.research_completeness(rows)
    assert counts == {"Unknown": 59, "Partial": 0, "Answered": 0, "N/A": 0}


def test_navigation_target_is_owner_reference_not_state_copy():
    rows = ws.build_live_rows("ABC", owner_payloads={})
    assert rows[0]["navigation_target"] == "Chapter 2 / Q01"
    assert rows[-1]["navigation_target"] == "Chapter 11 / Q59"
