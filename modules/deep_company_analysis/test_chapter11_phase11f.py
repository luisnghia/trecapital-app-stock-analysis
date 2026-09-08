from __future__ import annotations

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_completion as completion
import modules.deep_company_analysis.chapter11_store as store


def _ready_payload():
    p = ch11.empty_payload("DGC")
    for q in ch11.QUESTION_KEYS:
        p["question_status"][q] = "Answered"
        p["confidence"][q] = "High"
        p["analyst_assessment"][q] = f"Analyst conclusion for {q}"
    for d in ch11.dimension_ids():
        p["dimension_status"][d] = "Evidence found"
    return p


def test_v87_completion_gate_is_unknown_first():
    gate = completion.completion_gate(ch11.empty_payload("DGC"))
    assert gate["ready"] is False
    assert gate["total_questions"] == 2
    assert gate["total_dimensions"] == 15
    assert gate["resolved_dimensions"] == 0
    assert len(gate["blockers"]) == 2


def test_v87_completion_gate_ready_requires_analyst_completion():
    gate = completion.completion_gate(_ready_payload())
    assert gate["ready"] is True
    assert all(gate["questions"][q]["ready"] for q in ch11.QUESTION_KEYS)
    assert gate["resolved_dimensions"] == 15


def test_v87_gate_does_not_auto_change_analyst_fields():
    p = _ready_payload()
    before = {k: dict(p[k]) for k in ("question_status", "confidence", "analyst_assessment", "dimension_status")}
    completion.completion_gate(p)
    for key, value in before.items():
        assert p[key] == value


def test_v87_synthesis_is_analyst_owned_and_neutral():
    syn = completion.default_synthesis()
    assert syn["status"] == "Unknown"
    assert syn["final_ma_synthesis"] == ""
    text = " ".join(syn).casefold()
    assert "score" not in text
    assert "buy" not in text and "sell" not in text


def test_v87_attach_synthesis_drops_noncontract_financials():
    p = _ready_payload()
    p["canonical_financials"] = {"debt": 1}
    out = completion.attach_synthesis(p, {"status": "Draft", "final_ma_synthesis": "Analyst text"})
    assert "canonical_financials" not in out
    assert out["ma_synthesis"]["final_ma_synthesis"] == "Analyst text"


def test_v87_store_round_trip_preserves_synthesis_only(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "ch11.db")
    p = _ready_payload()
    p["ma_synthesis"] = completion.normalize_synthesis({"status": "Reviewed", "final_ma_synthesis": "Analyst-owned M&A synthesis"})
    p["ev_ebitda"] = 9.9
    store.save_record("DGC", p)
    loaded = store.load_record("DGC")
    assert loaded["ma_synthesis"]["status"] == "Reviewed"
    assert loaded["ma_synthesis"]["final_ma_synthesis"] == "Analyst-owned M&A synthesis"
    assert "ev_ebitda" not in loaded


def test_v87_report_keeps_completion_separate_from_conclusion():
    p = _ready_payload()
    p["ma_synthesis"] = {"status": "Final", "final_ma_synthesis": "Analyst conclusion"}
    report = completion.report_section(p)
    assert report["research_ready"] is True
    assert report["synthesis"]["final_ma_synthesis"] == "Analyst conclusion"
    note = report["boundary_note"].casefold()
    assert "not an m&a score" in note
    assert "buy/hold/sell" in note


def test_v87_source_lock_unchanged():
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.dimension_count_by_question() == {"Q58": 8, "Q59": 7}
    assert len(ch11.dimension_ids()) == 15
