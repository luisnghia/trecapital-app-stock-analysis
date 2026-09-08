from pathlib import Path

from modules.deep_company_analysis import appendix_c_history as hist
from modules.deep_company_analysis import appendix_c_history_store as store
from modules.deep_company_analysis import appendix_c_workspace as ws


def test_history_store_is_referential_and_immutable(tmp_path: Path):
    db = tmp_path / "appc.sqlite"
    rows = ws.build_live_rows("QA", owner_payloads={})
    payload = hist.build_snapshot_payload(rows)
    sid = store.create_snapshot("QA", "Example", payload, db)
    assert sid == 1
    snapshots = store.list_snapshots("QA", "Example", db)
    assert len(snapshots) == 1
    assert snapshots[0]["payload"] == payload
    assert snapshots[0]["fingerprint"] == hist.snapshot_fingerprint(payload)
    assert "analyst_assessment" not in snapshots[0]["payload_json"]
    assert "financials" not in snapshots[0]["payload_json"].lower()


def test_explicit_re_review_is_separate_metadata(tmp_path: Path):
    db = tmp_path / "appc.sqlite"
    rid = store.add_re_review("QA", "Example", "Reviewed all checklist references", db_path=db)
    assert rid == 1
    records = store.list_re_reviews("QA", "Example", db)
    assert records[0]["scope"] == "Q01-Q59"
    assert records[0]["analyst_note"] == "Reviewed all checklist references"
    assert "research_gate" not in records[0]
