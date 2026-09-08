from modules.deep_company_analysis import appendix_c as appc
from modules.deep_company_analysis import appendix_c_history as hist
from modules.deep_company_analysis import appendix_c_workspace as ws


def _rows(status="Unknown", confidence="Unknown"):
    rows = ws.build_live_rows("QA", owner_payloads={})
    for row in rows:
        row["question_status"] = status
        row["confidence"] = confidence
    return rows


def test_snapshot_is_referential_and_source_locked():
    payload = hist.build_snapshot_payload(_rows())
    assert not hist.validate_snapshot_payload(payload)
    assert len(payload["question_refs"]) == 59
    assert tuple(x["question_id"] for x in payload["question_refs"]) == appc.QUESTION_IDS
    assert all("analyst_assessment" not in x for x in payload["question_refs"])
    assert all(not (set(x) & hist.FORBIDDEN_SNAPSHOT_KEYS) for x in payload["question_refs"])


def test_neutral_delta_only():
    before = hist.build_snapshot_payload(_rows("Unknown", "Unknown"))
    after = hist.build_snapshot_payload(_rows("Partial", "Medium"))
    delta = hist.compare_snapshots(before, after)
    assert len(delta) == 118
    assert set(delta["Delta"]).issubset(set(hist.DELTA_VALUES))
    assert set(delta["Delta"]) == {"Changed"}


def test_fingerprint_deterministic():
    payload = hist.build_snapshot_payload(_rows())
    assert hist.snapshot_fingerprint(payload) == hist.snapshot_fingerprint(payload)
    assert len(hist.snapshot_fingerprint(payload)) == 64


def test_re_review_does_not_claim_state_change():
    record = hist.build_re_review_record("Analyst reviewed coverage")
    assert record == {"scope": "Q01-Q59", "analyst_note": "Analyst reviewed coverage"}
    assert "status" not in record and "research_gate" not in record


def test_full_book_closure_boundary_contract():
    contract = hist.closure_contract()
    assert contract["question_coverage"] == "Q01-Q59"
    assert contract["section_coverage"] == 10
    assert contract["ai_role"] == "Research Assistant"
    assert contract["conclusion_owner"] == "Analyst"
    assert all(contract[key] is False for key in (
        "automatic_weighted_score", "automatic_management_or_growth_score", "automatic_buy_hold_sell",
        "automatic_intrinsic_value_or_mos_change", "automatic_research_gate_change",
        "duplicate_financial_or_question_ssot_added",
    ))
