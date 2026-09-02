from __future__ import annotations

import sqlite3

from modules.deep_company_analysis import chapter3 as ch3


def _bind_db(tmp_path, monkeypatch):
    db = tmp_path / "chapter3.db"
    monkeypatch.setattr(ch3, "DB_PATH", db)
    ch3.init_db()
    return db


def _complete_payload():
    payload = ch3.empty_payload("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    payload["q7"].update({
        "core_customers": [{
            "Customer Segment": "Khách hàng công nghiệp",
            "Customer type": "B2B",
            "Who pays?": "Nhà sản xuất công nghiệp",
            "Who uses?": "Nhà máy / bộ phận sản xuất",
            "Main need / job-to-be-done": "Nguyên liệu đầu vào hóa chất",
            "Evidence": "IR/BCTN",
        }],
        "core_customer_summary": "Khách hàng cốt lõi là doanh nghiệp công nghiệp mua hóa chất làm đầu vào sản xuất.",
        "why_core": "Đây là nhóm gắn trực tiếp với nhu cầu sản phẩm công nghiệp.",
    })
    payload["q8"].update({
        "concentration_status": "Diversified",
        "concentration_table": [{"Customer / Group": "Nhóm khách hàng công nghiệp", "Evidence": "BCTN"}],
        "concentration_trend": "Chưa có chuỗi Top customers đầy đủ.",
        "concentration_summary": "Chưa thấy evidence cho phụ thuộc một khách hàng riêng lẻ; cần tiếp tục xác minh định lượng.",
    })
    payload["q9"].update({
        "sales_ease_status": "Moderate",
        "sales_motion": "B2B relationship / commercial negotiation",
        "sales_cycle": "Theo hợp đồng/đơn hàng",
        "sales_friction_summary": "Cần qualification và đàm phán nhưng nhu cầu mang tính đầu vào sản xuất.",
        "evidence": "IR/BCTN",
    })
    payload["q10"].update({
        "retention_assessability": "Not disclosed",
        "business_model": "Transactional / repeat B2B",
        "retention_summary": "Doanh nghiệp không công bố retention rate trực tiếp; không suy retention từ doanh thu.",
        "evidence": "BCTN không có metric retention trực tiếp trong evidence đã rà soát.",
    })
    payload["q11"].update({
        "feedback_mechanisms": "Theo dõi yêu cầu kỹ thuật và chất lượng khách hàng.",
        "customer_orientation_summary": "Có dấu hiệu đáp ứng yêu cầu khách hàng công nghiệp nhưng cần thêm customer-side evidence.",
        "evidence": "IR/BCTN",
    })
    payload["q12"].update({
        "pain_map": [{
            "Customer Segment": "Industrial",
            "Pain / Need": "Nguồn hóa chất đạt chuẩn",
            "Consequence if unsolved": "Gián đoạn/chất lượng sản xuất",
            "Solution / Value delivered": "Cung cấp hóa chất theo tiêu chuẩn",
            "Evidence": "IR/BCTN",
        }],
        "pain_summary": "Giải quyết nhu cầu nguồn nguyên liệu hóa chất đạt chuẩn và ổn định cho sản xuất.",
    })
    payload["q13"].update({
        "dependency_class": "Need to have, but not immediately",
        "dependency_reason": "Khách hàng cần nguyên liệu hóa chất để tiếp tục quy trình sản xuất nhưng có thể có nhà cung cấp thay thế.",
        "substitutes": "Nhà cung cấp hóa chất khác nếu đáp ứng tiêu chuẩn.",
        "evidence": "Customer/product requirements cần tiếp tục xác minh.",
    })
    payload["q14"].update({
        "impact_level": "Moderate",
        "immediate_substitute": "Tìm nhà cung cấp thay thế đủ specification.",
        "switching_time": "Phụ thuộc qualification và logistics.",
        "operational_disruption": "Có thể gián đoạn nếu thay nguồn không kịp.",
        "disappearance_conclusion": "Khách hàng có lựa chọn thay thế nhưng chuyển đổi không hoàn toàn tức thời.",
        "evidence": "Cần customer interview / supply-chain evidence để nâng confidence.",
    })
    payload["research_gaps"] = "Customer concentration định lượng\nRetention/churn trực tiếp\nCustomer interview"
    payload["analyst_summary"] = "Đã có khung customer perspective; cần thêm evidence trực tiếp từ khách hàng."
    return payload


def test_chapter3_roundtrip_and_snapshots(tmp_path, monkeypatch):
    db = _bind_db(tmp_path, monkeypatch)
    payload = _complete_payload()
    status = ch3.save_record(payload)
    assert status == "understood"

    loaded = ch3.load_record("DGC")
    assert loaded["ticker"] == "DGC"
    assert loaded["q7"]["core_customers"][0]["Customer type"] == "B2B"
    assert ch3.question_statuses(loaded) == {
        "Q7": "Answered",
        "Q8": "Answered",
        "Q9": "Answered",
        "Q10": "Answered",
        "Q11": "Answered",
        "Q12": "Answered",
        "Q13": "Answered",
        "Q14": "Answered",
    }

    ch3.save_record(payload)
    history = ch3.load_history("DGC")
    assert len(history) == 2
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM chapter3_current WHERE ticker='DGC'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM chapter3_snapshots WHERE ticker='DGC'").fetchone()[0] == 2


def test_blank_payload_is_not_understood(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = ch3.empty_payload("ABC", "ABC Corp")
    statuses = ch3.question_statuses(payload)
    assert all(value == "Unknown" for value in statuses.values())
    assert ch3.customer_perspective_status(payload) == "not_understood"


def test_retention_does_not_become_answered_from_proxy_without_assessment(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = ch3.empty_payload("ABC", "ABC Corp")
    payload["q10"]["loyalty_proxy"] = "Có chương trình khách hàng thân thiết."
    assert ch3.question_statuses(payload)["Q10"] == "Partial"
    payload["q10"]["retention_summary"] = "Proxy này không phải retention rate."
    assert ch3.question_statuses(payload)["Q10"] == "Partial"


def test_customer_concentration_requires_explicit_assessment_and_summary(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = ch3.empty_payload("ABC", "ABC Corp")
    payload["q8"]["concentration_table"] = [{"Customer / Group": "Top customer", "Revenue share %": ""}]
    assert ch3.question_statuses(payload)["Q8"] == "Partial"
    payload["q8"]["concentration_summary"] = "Chưa đủ disclosure định lượng."
    assert ch3.question_statuses(payload)["Q8"] == "Partial"
    payload["q8"]["concentration_status"] = "Concentrated"
    assert ch3.question_statuses(payload)["Q8"] == "Answered"


def test_customer_perspective_understood_requires_q7_and_q12(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = _complete_payload()
    payload["q12"]["pain_summary"] = ""
    assert ch3.question_statuses(payload)["Q12"] == "Partial"
    assert ch3.customer_perspective_status(payload) == "partial"
