from __future__ import annotations

from modules.deep_company_analysis import chapter1 as ch1


def _payload(ticker: str, gate: str, reason: str):
    quality = {
        code: {
            "status": "✓ Có" if idx < 6 else "— Chưa biết",
            "confidence": 3,
            "note": f"note-{idx}",
        }
        for idx, (code, _, _) in enumerate(ch1.QUALITY_CRITERIA)
    }
    return {
        "ticker": ticker,
        "company_name": "Test Company",
        "idea_sources": ["Định giá thấp bất thường"],
        "market_mispricing": "Temporary uncertainty",
        "initial_thesis": "Initial thesis",
        "research_gaps": "Gap 1\nGap 2",
        "opportunity_signals": {
            "drawdown_52w_pct": 30.0,
            "valuation_percentile": 15.0,
            "price_earnings_divergence": "Có",
            "special_event": "Event",
        },
        "valuation": {
            "current_price": 80000.0,
            "target_price": 100000.0,
            "mos_pct": 20.0,
            "stock_price_vs_target_pct": 80.0,
            "fcf_yield_pct": 7.5,
            "dividend_yield_pct": 2.0,
            "tev_ebit": 9.0,
            "tev_ebitda": 7.5,
            "debt_ebitda": 1.2,
            "ebit_interest": 8.0,
        },
        "quality": quality,
        "gate": gate,
        "gate_reason": reason,
        "next_review": "Sau BCTC Q3/2026",
        "triggers": ["Review khi MOS > 25%", "Review sau BCTC Q3/2026"],
    }


def test_offline_chapter1_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(ch1, "DB_PATH", tmp_path / "chapter1.db")
    ch1.init_db()

    ch1.save_record(_payload("FPT", "watch", "Chờ biên an toàn tốt hơn"))
    loaded = ch1.load_record("FPT")

    assert loaded["company_name"] == "Test Company"
    assert loaded["gate"] == "watch"
    assert loaded["triggers"] == ["Review khi MOS > 25%", "Review sau BCTC Q3/2026"]
    score, unknown = ch1._quality_score(loaded["quality"])
    assert score == 6
    assert unknown == 4

    inventory = ch1.load_inventory()
    assert len(inventory) == 1
    assert inventory.iloc[0]["Mã"] == "FPT"
    assert inventory.iloc[0]["gate_key"] == "watch"
    assert inventory.iloc[0]["Quality"] == "6/10"


def test_gate_change_is_append_only(tmp_path, monkeypatch):
    monkeypatch.setattr(ch1, "DB_PATH", tmp_path / "chapter1.db")
    ch1.init_db()

    ch1.save_record(_payload("MWG", "watch", "Chờ dữ liệu"))
    ch1.save_record(_payload("MWG", "continue", "Điều kiện nghiên cứu đã đạt"))

    history = ch1.load_gate_history("MWG")
    assert len(history) == 2
    assert "Continue" in history.iloc[0]["Gate mới"]
    assert "Watch" in history.iloc[1]["Gate mới"]

    with ch1._connect() as conn:
        snapshot_count = conn.execute(
            "SELECT COUNT(*) FROM chapter1_snapshots WHERE ticker = ?", ("MWG",)
        ).fetchone()[0]
    assert snapshot_count == 2


def test_confidence_is_simplified_to_three_levels(tmp_path, monkeypatch):
    monkeypatch.setattr(ch1, "DB_PATH", tmp_path / "chapter1.db")
    ch1.init_db()

    payload = _payload("DGC", "watch", "Test confidence")
    payload["quality"]["recurring_revenue"]["confidence"] = 5  # legacy value
    ch1.save_record(payload)
    loaded = ch1.load_record("DGC")

    assert loaded["quality"]["recurring_revenue"]["confidence"] == 3
    assert ch1._confidence_label(1) == "Thấp"
    assert ch1._confidence_label(2) == "Trung bình"
    assert ch1._confidence_label(3) == "Cao"


def test_dgc_trial_fixture_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(ch1, "DB_PATH", tmp_path / "chapter1.db")
    fixture = ch1.load_dgc_trial_payload()
    ch1.save_record(fixture)
    loaded = ch1.load_record("DGC")

    assert loaded["gate"] == "watch"
    score, unknown = ch1._quality_score(loaded["quality"])
    assert score == 5
    assert unknown == 2
    assert loaded["quality"]["high_roic"]["confidence"] == 3
    inventory = ch1.load_inventory()
    assert inventory.iloc[0]["Mã"] == "DGC"
    assert inventory.iloc[0]["gate_key"] == "watch"
