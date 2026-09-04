from __future__ import annotations

import pandas as pd

import modules.deep_company_analysis.chapter4 as ch4
import modules.deep_company_analysis.chapter4_lock as lock
from modules.deep_company_analysis.chapter4_evidence_c3 import Phase4C3Result, SHEARN_Q19_SUBTOPICS


def _candidate(question="Q19", subtopic="How Competitors Compete", quality="B — Independent financial source", title="DGC industry competition", snippet="DGC cạnh tranh về giá, chi phí và công suất trong ngành hóa chất.", url="https://research.vn/a"):
    return {
        "Question": question,
        "Subtopic": subtopic,
        "Direction": "Neutral — Candidate",
        "Evidence Quality": quality,
        "Explicitness": "candidate — analyst verify",
        "Period Candidate": "2025",
        "Title": title,
        "URL": url,
        "Snippet": snippet,
        "Source Group": "Independent",
        "Source Method": "test direct source",
    }


def _pricing(url="https://company.vn/p", quality="A — Company/Official disclosure"):
    row = _candidate(
        question="Q16",
        subtopic="Actual Pricing / Customer Response",
        quality=quality,
        title="DGC pricing and volume 2025",
        snippet="DGC cho biết giá bán tăng trong khi sản lượng và nhu cầu khách hàng vẫn tăng trong năm 2025.",
        url=url,
    )
    row["Explicitness"] = "Explicit price + customer/volume candidate"
    row["Event Type Candidate"] = "Price + reaction with commodity/cost context — analyst verify"
    return row


def _result_for_lock() -> Phase4C3Result:
    q19_rows = []
    for idx, subtopic in enumerate(SHEARN_Q19_SUBTOPICS[:-1]):  # leave competitor-failure gap explicit
        text = {
            "Limited / Direct Competition": "DGC đối thủ cạnh tranh trực tiếp và thị phần ngành hóa chất.",
            "How Competitors Compete": "DGC cạnh tranh bằng giá, chi phí, chất lượng và phân phối.",
            "Fierceness / Price Competition": "Ngành hóa chất có cạnh tranh giá và áp lực biên lợi nhuận.",
            "Substitute Products": "DGC đối mặt sản phẩm thay thế và alternative product trong một số phân khúc.",
            "Low-cost Country Competition": "DGC chịu cạnh tranh nhập khẩu giá rẻ từ Trung Quốc.",
            "Industry Standard / Market Position": "DGC có vị thế thị phần và được so sánh với nhà sản xuất dẫn đầu.",
            "Industry Change / Capacity Competition": "Ngành hóa chất có mở rộng công suất và nhà máy mới.",
        }[subtopic]
        q19_rows.append(_candidate(subtopic=subtopic, snippet=text, url=f"https://research{idx}.vn/q19"))
    q19 = pd.DataFrame(q19_rows)
    pricing = pd.DataFrame([
        _pricing("https://company.vn/p", "A — Company/Official disclosure"),
        _pricing("https://research.vn/p", "B — Independent financial source"),
    ])
    corroboration = pd.DataFrame([{
        "Period": "2025", "Explicit candidates": 2, "Distinct domains": 2,
        "Independent candidates": 1, "Commodity/pass-through candidates": 2,
        "Corroboration status": "Period-level corroboration candidate — analyst verify same event",
    }])
    combined = pd.concat([pricing, q19], ignore_index=True, sort=False)
    coverage = pd.DataFrame()
    return Phase4C3Result(
        pricing_candidates=pricing,
        pricing_corroboration=corroboration,
        q19_evidence=q19,
        q19_coverage=coverage,
        combined_candidates=combined,
        gaps=["Q19 — Why Competitors Failed: chưa có evidence candidate đủ điều kiện."],
        note="test",
        audit={},
    )


def test_obvious_search_noise_is_quarantined():
    rows = pd.DataFrame([
        _candidate(quality="C — Other candidate source", title="Create & manage a shared YouTube TV membership, or family group", snippet="YouTube TV membership family group smart devices", url="https://youtube.com/x"),
        _candidate(quality="B — Independent financial source", snippet="DGC cạnh tranh giá và mở rộng công suất trong ngành hóa chất.", url="https://research.vn/good"),
    ])
    kept, quarantine = lock.sanitize_candidates(rows, "DGC", "Tập đoàn Hóa chất Đức Giang", "Hóa chất")
    assert len(kept) == 1
    assert len(quarantine) == 1
    assert quarantine.iloc[0]["Quarantine Reason"] == "obvious-unrelated-search-noise"


def test_source_c_requires_target_or_industry_anchor():
    rows = pd.DataFrame([
        _candidate(quality="C — Other candidate source", title="Chemical competition", snippet="Competition and price pressure increased in another unrelated market.", url="https://other.net/x"),
        _candidate(quality="C — Other candidate source", title="DGC chemical competition", snippet="DGC cạnh tranh giá trong ngành hóa chất và đối thủ tăng công suất.", url="https://other.net/y"),
    ])
    kept, quarantine = lock.sanitize_candidates(rows, "DGC", "Tập đoàn Hóa chất Đức Giang", "Hóa chất")
    assert len(kept) == 1
    assert kept.iloc[0]["URL"].endswith("/y")
    assert len(quarantine) == 1


def test_legitimate_failure_requires_event_cause_and_ab_source():
    rows = pd.DataFrame([
        _candidate(subtopic="Why Competitors Failed", quality="B — Independent financial source", snippet="Một đối thủ đóng cửa do thua lỗ kéo dài và chi phí đầu vào tăng.", url="https://research.vn/f1"),
        _candidate(subtopic="Why Competitors Failed", quality="B — Independent financial source", snippet="Báo cáo đề cập competitor failure nhưng không nêu sự kiện hay nguyên nhân cụ thể.", url="https://research.vn/f2"),
        _candidate(subtopic="Why Competitors Failed", quality="C — Other candidate source", snippet="Một nhà máy đóng cửa do thua lỗ kéo dài.", url="https://blog.net/f3"),
    ])
    out = lock.legitimate_failure_candidates(rows)
    assert len(out) == 1
    assert out.iloc[0]["URL"].endswith("/f1")


def test_final_lock_can_pass_with_explicit_stock_specific_failure_gap():
    audit = lock.build_lock_audit(_result_for_lock(), "DGC", "Tập đoàn Hóa chất Đức Giang", "Hóa chất")
    assert audit.lock_ready is True
    assert int(audit.q19_coverage["Candidates"].gt(0).sum()) == 7
    assert any("Why Competitors Failed" in x for x in audit.research_gaps)
    assert bool(audit.checks["Passed"].all())


def test_provenance_audit_rejects_missing_source_method():
    frame = pd.DataFrame([_candidate()])
    frame.loc[0, "Source Method"] = ""
    prov = lock.provenance_audit(frame)
    row = prov[prov["Check"].eq("source_method")].iloc[0]
    assert bool(row["Passed"]) is False


def test_finalize_lock_never_overwrites_analyst_judgement():
    audit = lock.build_lock_audit(_result_for_lock(), "DGC", "Tập đoàn Hóa chất Đức Giang", "Hóa chất")
    record = ch4.empty_payload("DGC", "Tập đoàn Hóa chất Đức Giang")
    record["q15"]["sustainable_advantage"] = "Partial"
    record["q16"]["pricing_power"] = "Unknown"
    record["q19"]["competition_intensity"] = "Analyst-owned"
    record["research_gate"] = "Watch"
    out = lock.finalize_record_for_lock(record, audit)
    assert out["q15"]["sustainable_advantage"] == "Partial"
    assert out["q16"]["pricing_power"] == "Unknown"
    assert out["q19"]["competition_intensity"] == "Analyst-owned"
    assert out["research_gate"] == "Watch"
    assert out["chapter4_lock"]["status"] == "LOCKED"


def test_persistence_restart_snapshot_and_child_rows_roundtrip(tmp_path, monkeypatch):
    db = tmp_path / "chapter4_lock_test.db"
    monkeypatch.setattr(ch4, "DB_PATH", db)
    record = ch4.empty_payload("LOCKT", "Lock Test Company")
    record["q15"]["sustainable_advantage"] = "Yes"
    record["q15"]["conclusion"] = "Analyst conclusion survives restart."
    record["q15_advantages"] = [{col: "" for col in ch4.ADVANTAGE_COLUMNS}]
    record["q15_advantages"][0]["Specific Advantage"] = "Scale"
    record["evidence_matrix"] = [{
        "Question": "Q15", "Claim": "Scale", "Evidence Type": "A — Company/Official disclosure",
        "Source Title": "Annual report", "Source URL / File": "https://company.vn/ar.pdf", "Source Date": "2025",
        "Period": "2025", "Evidence Text": "Company disclosed scale and production capacity evidence.",
        "Direction": "Supporting — Candidate", "Status": "Candidate — Analyst verify", "Data Origin": "test", "Analyst Note": "",
    }]
    ch4.save_record(record, create_snapshot=True)
    loaded = ch4.load_record("LOCKT")
    history = ch4.load_history("LOCKT")
    assert loaded["q15"]["conclusion"] == "Analyst conclusion survives restart."
    assert loaded["q15_advantages"][0]["Specific Advantage"] == "Scale"
    assert loaded["evidence_matrix"][0]["Source Title"] == "Annual report"
    assert len(history) == 1


def test_guardrails_remain_all_false():
    flags = lock.guardrail_audit()
    assert flags
    assert all(value is False for value in flags.values())
