from __future__ import annotations

import sqlite3

from modules.deep_company_analysis import chapter2 as ch2


def _bind_db(tmp_path, monkeypatch):
    db = tmp_path / "chapter2.db"
    monkeypatch.setattr(ch2, "DB_PATH", db)
    ch2.init_db()
    return db


def _complete_payload():
    payload = ch2.empty_payload("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    payload["q1"].update({
        "interest_reason": "Tôi muốn hiểu sâu economics của chuỗi phosphorus.",
        "unknowns": "Chưa hiểu đầy đủ economics của downstream products.",
        "bias_check": "Không dựa vào việc yêu thích sản phẩm.",
    })
    payload["q2"].update({
        "underlying_economics": "Giá bán, sản lượng, feedstock và năng lực vận hành quyết định economics.",
        "industry_context": "Ngành hóa chất phosphorus có tính commodity và yêu cầu tích hợp nguyên liệu.",
        "customers_users": "Khách hàng công nghiệp trong và ngoài nước.",
        "field_reality_check": "Cần thêm evidence từ nhà máy/khách hàng.",
        "ceo_critical_questions": "Nguồn quặng?\nCost curve?\nNghi Sơn?\nKhách hàng?\nCapital allocation?",
    })
    payload["q3"].update({
        "segments": [{"Segment": "Phosphorus", "Product / Service": "P4", "Customer": "Industrial"}],
        "business_flow": "Apatite → processing → phosphorus products → export/domestic customer → cash",
        "own_words": "Doanh nghiệp chuyển nguyên liệu phosphorus thành các hóa chất có mức giá trị gia tăng khác nhau.",
        "analogy": "Chuỗi tích hợp nguyên liệu đến hóa chất downstream.",
        "world_without": "Khách hàng phải tìm nguồn hóa chất thay thế.",
    })
    payload["q4"].update({
        "money_engine": [{"Segment": "Phosphorus", "Who pays?": "Industrial customers", "Pays for what?": "P4"}],
        "money_summary": "Revenue = volume × price; lợi nhuận phụ thuộc spread so với feedstock/energy và utilization.",
        "complexity_status": "Dễ giải thích",
        "what_can_break": "Feedstock shortage, price decline, cost inflation.",
    })
    payload["q5"].update({
        "evolution": [{"Year": "2020", "Event": "Capacity expansion", "Type": "New Capacity"}],
        "history_summary": "Mở rộng từ hóa chất cơ bản sang sản phẩm có giá trị gia tăng cao hơn.",
        "skill_vs_luck": "Kết hợp năng lực vận hành, nguồn nguyên liệu và chu kỳ giá thuận lợi.",
    })
    payload["q6"].update({
        "foreign_markets": [{"Country / Region": "Asia", "Revenue share %": "50"}],
        "foreign_strategy_summary": "Xuất khẩu là phần trọng yếu; cần tách country-level exposure.",
        "country_risks": [{"Country": "China", "Revenue exposure %": "10"}],
        "currency_risks": [{"Currency": "USD", "Revenue exposure": "Export"}],
    })
    payload["research_gaps"] = "Country-level revenue\nRegional profitability"
    payload["analyst_summary"] = "Business understandable ở mức nền tảng, cần tiếp tục đóng research gaps."
    return payload


def test_chapter2_roundtrip_and_snapshots(tmp_path, monkeypatch):
    db = _bind_db(tmp_path, monkeypatch)
    payload = _complete_payload()
    status = ch2.save_record(payload)
    assert status == "understandable"

    loaded = ch2.load_record("DGC")
    assert loaded["ticker"] == "DGC"
    assert loaded["company_name"] == "CTCP Tập đoàn Hóa chất Đức Giang"
    assert loaded["q3"]["segments"][0]["Segment"] == "Phosphorus"
    assert ch2.question_statuses(loaded) == {"Q1": "Answered", "Q2": "Answered", "Q3": "Answered", "Q4": "Answered", "Q5": "Answered", "Q6": "Answered"}

    ch2.save_record(payload)
    history = ch2.load_history("DGC")
    assert len(history) == 2
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM chapter2_current WHERE ticker='DGC'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM chapter2_snapshots WHERE ticker='DGC'").fetchone()[0] == 2


def test_understanding_status_requires_q3_and_q4(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = _complete_payload()
    payload["q3"]["own_words"] = ""
    assert ch2.question_statuses(payload)["Q3"] == "Partial"
    assert ch2.understanding_status(payload) == "partial"


def test_q6_can_be_answered_as_no_material_foreign_operations(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = ch2.empty_payload("ABC", "ABC Corp")
    payload["q6"]["no_material_foreign_operations"] = True
    assert ch2.question_statuses(payload)["Q6"] == "Answered"
    assert ch2.understanding_status(payload) == "partial"


def test_blank_payload_is_not_understood(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = ch2.empty_payload("ABC", "ABC Corp")
    statuses = ch2.question_statuses(payload)
    assert all(value == "Unknown" for value in statuses.values())
    assert ch2.understanding_status(payload) == "not_understood"
