from __future__ import annotations

import copy
import sqlite3

from modules.deep_company_analysis import chapter1 as ch1
from modules.deep_company_analysis import monitoring


def _bind_db(tmp_path, monkeypatch):
    db = tmp_path / "chapter1_acceptance.db"
    monkeypatch.setattr(ch1, "DB_PATH", db)
    monkeypatch.setattr(monitoring, "DB_PATH", db)
    ch1.init_db()
    monitoring.init_monitoring_db()
    return db


def _auto_data(*, as_of="2026-Q2", quote_fresh=True, mos=26.0, price=43_000.0, events=None):
    return {
        "as_of": as_of,
        "quote_fresh": quote_fresh,
        "valuation": {
            "current_price": price,
            "target_price": 60_000.0,
            "mos_pct": mos,
            "fcf_yield_pct": 7.0,
            "debt_ebitda": 0.8,
            "ebit_interest": 12.0,
        },
        "monitoring_metrics": {
            "current_price": price,
            "mos_pct": mos,
            "roic_pct": 18.0,
            "debt_ebitda": 0.8,
            "ebit_interest": 12.0,
            "fcf_yield_pct": 7.0,
        },
        "opportunity_signals": {
            "valuation_percentile": 20.0,
            "drawdown_52w_pct": 58.3,
            "event_candidates": events or [
                {"category": "Quản trị / pháp lý", "title": "Event A", "url": "https://example.com/a"}
            ],
        },
    }


def test_dgc_end_to_end_chapter1_acceptance(tmp_path, monkeypatch):
    """Final Chapter 1 acceptance: idea -> filter -> gate -> inventory -> monitor -> review."""
    db = _bind_db(tmp_path, monkeypatch)

    # 1) Load the point-in-time DGC case and verify the analyst-controlled research record.
    payload = ch1.load_dgc_trial_payload()
    ch1.save_record(payload)
    loaded = ch1.load_record("DGC")
    quality_score, unknown_count = ch1._quality_score(loaded["quality"])

    assert loaded["ticker"] == "DGC"
    assert loaded["gate"] == "watch"
    assert quality_score == 5
    assert unknown_count == 2
    assert loaded["quality"]["high_roic"]["confidence"] == 3
    assert loaded["quality"]["proven_management"]["confidence"] == 1
    assert loaded["market_mispricing"]
    assert loaded["initial_thesis"]
    assert loaded["research_gaps"]

    inventory = ch1.load_inventory()
    assert len(inventory) == 1
    assert inventory.iloc[0]["Mã"] == "DGC"
    assert inventory.iloc[0]["gate_key"] == "watch"
    assert inventory.iloc[0]["Quality"] == "5/10"
    assert int(inventory.iloc[0]["Unknown"]) == 2

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM chapter1_current WHERE ticker='DGC'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM chapter1_snapshots WHERE ticker='DGC'").fetchone()[0] == 1

    # 2) Replace free-text monitoring examples with structured triggers supported by V6.
    structured = copy.deepcopy(payload)
    structured["triggers"] = [
        "Review khi MOS > 25%",
        "Review khi có BCTC Q3/2026",
        "Review khi có event mới",
    ]
    ch1.save_record(structured)
    record = ch1.load_record("DGC")
    assert record["triggers"] == structured["triggers"]

    # First scan: MOS fires; BCTC-Q3 and event triggers only arm/baseline.
    first = monitoring.evaluate_and_persist("DGC", record, _auto_data(as_of="2026-Q2"))
    assert [row["triggered"] for row in first] == [True, False, False]
    assert first[1]["status"] == "armed"
    assert first[1]["target_period"] == "2026-Q3"
    assert first[2]["status"] == "armed"
    assert len(monitoring.load_review_queue()) == 1

    # Repeat scan with unchanged data: no duplicate queue item.
    monitoring.evaluate_and_persist("DGC", record, _auto_data(as_of="2026-Q2"))
    assert len(monitoring.load_review_queue()) == 1

    # New target statement period: Q3 trigger creates exactly one new review item.
    q3 = monitoring.evaluate_and_persist("DGC", record, _auto_data(as_of="2026-Q3"))
    assert q3[1]["triggered"]
    assert len(monitoring.load_review_queue()) == 2

    # New event candidate: event trigger creates exactly one new review item.
    events = [
        {"category": "Quản trị / pháp lý", "title": "Event A", "url": "https://example.com/a"},
        {"category": "Kiểm toán / BCTC", "title": "Event B", "url": "https://example.com/b"},
    ]
    event_scan = monitoring.evaluate_and_persist("DGC", record, _auto_data(as_of="2026-Q3", events=events))
    assert event_scan[2]["triggered"]
    queue = monitoring.load_review_queue()
    assert len(queue) == 3

    # 3) Resolving review items must never change the analyst's Research Gate.
    for item_id in queue["ID"].astype(int).tolist():
        monitoring.resolve_review_item(item_id)
    assert monitoring.load_review_queue().empty
    assert ch1.load_record("DGC")["gate"] == "watch"

    # 4) Analyst can change Gate; history/snapshots append while current inventory remains unique.
    changed = copy.deepcopy(structured)
    changed["gate"] = "continue"
    changed["gate_reason"] = "Acceptance test: analyst quyết định tiếp tục nghiên cứu sau khi review."
    ch1.save_record(changed)

    final_record = ch1.load_record("DGC")
    final_inventory = ch1.load_inventory()
    history = ch1.load_gate_history("DGC")
    assert final_record["gate"] == "continue"
    assert len(final_inventory) == 1
    assert final_inventory.iloc[0]["gate_key"] == "continue"
    assert "Continue" in history.iloc[0]["Gate mới"]
    with sqlite3.connect(db) as conn:
        # fixture save + structured save + gate-change save
        assert conn.execute("SELECT COUNT(*) FROM chapter1_snapshots WHERE ticker='DGC'").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM chapter1_current WHERE ticker='DGC'").fetchone()[0] == 1


def test_final_acceptance_stale_quote_never_fires_market_trigger(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = ch1.load_dgc_trial_payload()
    payload["triggers"] = ["Review khi giá < 80.000", "Review khi MOS > 25%", "ROIC < 20%"]
    ch1.save_record(payload)
    record = ch1.load_record("DGC")

    results = monitoring.evaluate_and_persist(
        "DGC",
        record,
        _auto_data(quote_fresh=False, price=1.0, mos=99.0),
    )
    # Market-dependent price/MOS triggers are suppressed; statement-derived ROIC can still fire.
    assert results[0]["status"] == "missing_data" and not results[0]["triggered"]
    assert results[1]["status"] == "missing_data" and not results[1]["triggered"]
    assert results[2]["triggered"]


def test_final_acceptance_legacy_manual_triggers_are_preserved(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = ch1.load_dgc_trial_payload()
    ch1.save_record(payload)
    loaded = ch1.load_record("DGC")

    # Qualitative free-text triggers from the original case remain stored even if automatic parser
    # cannot evaluate them. This prevents data loss when moving to Structured Trigger Builder V6.
    assert loaded["triggers"] == payload["triggers"]
    parsed = [monitoring.parse_trigger(text).kind for text in loaded["triggers"]]
    assert "unsupported" in parsed
