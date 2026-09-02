from __future__ import annotations

import sqlite3

from modules.deep_company_analysis import monitoring


def _auto(**overrides):
    data = {
        "as_of": "2026-Q2",
        "quote_fresh": True,
        "valuation": {
            "current_price": 79_000.0,
            "mos_pct": 26.0,
            "fcf_yield_pct": 7.0,
            "debt_ebitda": 1.2,
            "ebit_interest": 8.0,
        },
        "monitoring_metrics": {"roic_pct": 14.0},
        "opportunity_signals": {
            "valuation_percentile": 18.0,
            "drawdown_52w_pct": 35.0,
            "event_candidates": [
                {"category": "Quản trị / pháp lý", "title": "Event A", "url": "https://example.com/a"}
            ],
        },
    }
    for key, value in overrides.items():
        data[key] = value
    return data


def _setup_db(tmp_path, monkeypatch):
    db = tmp_path / "monitoring.db"
    monkeypatch.setattr(monitoring, "DB_PATH", db)
    monitoring.init_monitoring_db()
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chapter1_current (ticker TEXT PRIMARY KEY, company_name TEXT, gate TEXT)"
        )
        conn.execute("INSERT OR REPLACE INTO chapter1_current VALUES ('DGC', 'Duc Giang', 'watch')")
    return db


def test_parse_numeric_triggers():
    price = monitoring.parse_trigger("Review khi giá < 80.000")
    assert price.kind == "numeric"
    assert price.metric == "current_price"
    assert price.operator == "<"
    assert price.threshold == 80000.0

    mos = monitoring.parse_trigger("Review khi MOS > 25%")
    assert mos.metric == "mos_pct"
    assert mos.threshold == 25.0

    debt = monitoring.parse_trigger("Debt/EBITDA > 2x")
    assert debt.metric == "debt_ebitda"
    assert debt.threshold == 2.0


def test_numeric_trigger_creates_one_queue_item_per_transition(tmp_path, monkeypatch):
    db = _setup_db(tmp_path, monkeypatch)
    record = {"triggers": ["Review khi giá < 80.000", "Review khi MOS > 25%", "ROIC < 15%"]}

    results = monitoring.evaluate_and_persist("DGC", record, _auto())
    assert sum(bool(row["triggered"]) for row in results) == 3
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM chapter1_review_queue WHERE status='open'").fetchone()[0] == 3

    monitoring.evaluate_and_persist("DGC", record, _auto())
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM chapter1_review_queue").fetchone()[0] == 3

    data_false = _auto()
    data_false["valuation"]["current_price"] = 90_000.0
    data_false["valuation"]["mos_pct"] = 10.0
    data_false["monitoring_metrics"]["roic_pct"] = 20.0
    monitoring.evaluate_and_persist("DGC", record, data_false)
    monitoring.evaluate_and_persist("DGC", record, _auto())
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM chapter1_review_queue").fetchone()[0] == 6


def test_stale_quote_never_fires_price_or_mos_trigger(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    data = _auto(quote_fresh=False)
    data["monitoring_metrics"].update({"current_price": 50_000.0, "mos_pct": 40.0, "fcf_yield_pct": 10.0})
    record = {"triggers": ["giá < 80.000", "MOS > 25%", "FCF Yield > 8%", "ROIC < 15%"]}
    results = monitoring.evaluate_and_persist("DGC", record, data)
    by_text = {row["trigger_text"]: row for row in results}
    assert by_text["giá < 80.000"]["status"] == "missing_data"
    assert by_text["MOS > 25%"]["status"] == "missing_data"
    assert by_text["FCF Yield > 8%"]["status"] == "missing_data"
    assert by_text["ROIC < 15%"]["triggered"] is True


def test_statement_trigger_arms_then_detects_new_period(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    record = {"triggers": ["Review khi có BCTC mới"]}

    first = monitoring.evaluate_and_persist("DGC", record, _auto())[0]
    assert first["status"] == "armed"
    assert not first["triggered"]

    second_data = _auto(as_of="2026-Q3")
    second = monitoring.evaluate_and_persist("DGC", record, second_data)[0]
    assert second["triggered"]
    assert "2026-Q2" in second["evidence"] and "2026-Q3" in second["evidence"]


def test_event_trigger_arms_then_detects_new_candidate(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    record = {"triggers": ["Review khi có event mới"]}

    first = monitoring.evaluate_and_persist("DGC", record, _auto())[0]
    assert first["status"] == "armed"

    changed = _auto()
    changed["opportunity_signals"]["event_candidates"].append(
        {"category": "Kiểm toán / BCTC", "title": "Event B", "url": "https://example.com/b"}
    )
    second = monitoring.evaluate_and_persist("DGC", record, changed)[0]
    assert second["triggered"]
    assert "1 event" in second["evidence"]


def test_review_resolution_does_not_change_gate(tmp_path, monkeypatch):
    db = _setup_db(tmp_path, monkeypatch)
    record = {"triggers": ["MOS > 25%"]}
    monitoring.evaluate_and_persist("DGC", record, _auto())
    queue = monitoring.load_review_queue()
    assert len(queue) == 1
    monitoring.resolve_review_item(int(queue.iloc[0]["ID"]))
    assert monitoring.load_review_queue().empty
    with sqlite3.connect(db) as conn:
        gate = conn.execute("SELECT gate FROM chapter1_current WHERE ticker='DGC'").fetchone()[0]
    assert gate == "watch"
