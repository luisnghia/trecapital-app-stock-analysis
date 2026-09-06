from __future__ import annotations

import json

import pandas as pd

from modules.deep_company_analysis.chapter5_evidence import (
    CHAPTER5_OFFICIAL_PAGES,
    CHAPTER5_OFFICIAL_PDFS,
    _FocusedChapter5Agent,
    candidate_rows,
)
from modules.deep_company_analysis.chapter5_source_audit import (
    annotate_search_frame,
    failed_source_attempts,
    official_search_domain,
    prioritize_candidates,
    registered_source_catalog,
    source_attempt_table,
    summarize_search_raw_log,
)


def test_dgc_search_puts_registered_first_party_domain_first(tmp_path):
    agent = _FocusedChapter5Agent(tmp_path, "Q25")
    queries = agent._build_queries("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    assert len(queries) == 2
    assert queries[0].startswith("site:ducgiangchem.vn")
    assert "DGC" in queries[0]
    assert "maturity" in queries[0]


def test_registered_source_catalog_keeps_first_party_pages_pdfs_and_ir_root():
    catalog = registered_source_catalog("DGC", CHAPTER5_OFFICIAL_PAGES, CHAPTER5_OFFICIAL_PDFS)
    assert not catalog.empty
    assert set(catalog["Source Grade"]) == {"A — Company/Official disclosure"}
    assert "ducgiangchem.vn" in set(catalog["Domain"])
    assert {"Official HTML", "Official PDF", "Company IR root"}.issubset(set(catalog["Kind"]))
    assert catalog["URL"].is_unique


def test_known_company_search_snippet_is_source_a_but_stays_candidate():
    raw = pd.DataFrame([{
        "_Focus": "Q25",
        "Nhóm thông tin": "Tin tham khảo",
        "Tiêu đề": "DGC công bố nợ vay và thanh khoản",
        "Nguồn/URL": "https://ducgiangchem.vn/quan-he-co-dong/",
        "Tên miền": "ducgiangchem.vn",
        "Trích yếu": "Nợ vay, liquidity và maturity được trình bày trong tài liệu công bố.",
        "Trạng thái": "Tìm thấy",
        "Truy vấn": "site:ducgiangchem.vn DGC debt maturity",
    }])
    annotated = annotate_search_frame(raw, "DGC")
    assert annotated.iloc[0]["Nhóm thông tin"] == "Nguồn doanh nghiệp/IR"
    assert "Official-domain" in annotated.iloc[0]["_SourceMethod"]

    candidates = candidate_rows(annotated)
    assert len(candidates) == 1
    assert candidates.iloc[0]["Evidence Quality"].startswith("A —")
    assert "Candidate" in candidates.iloc[0]["Direction"]


def test_search_raw_log_preserves_failure_reason(tmp_path):
    path = tmp_path / "search.json"
    path.write_text(json.dumps({
        "ticker": "DGC",
        "queries": [{
            "query": "site:ducgiangchem.vn DGC risk",
            "items": [],
            "status_codes": [{"url": "https://duckduckgo.com", "status_code": 202}],
            "errors": [{"url": "https://duckduckgo.com", "error": "blocked by upstream"}],
            "fallback_bing": {
                "items": [],
                "status_codes": [{"url": "https://www.bing.com", "status_code": 403}],
                "errors": [{"url": "https://www.bing.com", "error": "forbidden"}],
            },
        }],
    }), encoding="utf-8")

    attempt = summarize_search_raw_log(path, "Q23")
    assert attempt["success"] is False
    assert attempt["rows"] == 0
    assert "202" in attempt["status"] and "403" in attempt["status"]
    assert "blocked by upstream" in attempt["error"]
    assert "forbidden" in attempt["error"]


def test_failed_official_document_attempt_is_never_silently_dropped():
    audit = {
        "attempts": [
            {
                "channel": "official",
                "focus": "Q21–Q26",
                "kind": "Official PDF",
                "label": "Annual report",
                "url": "https://example.com/ar.pdf",
                "success": False,
                "status": "Retrieval failed",
                "rows": 0,
                "error": "HTTP 403",
            },
            {
                "channel": "official",
                "focus": "Q21–Q26",
                "kind": "Official HTML",
                "label": "IR page",
                "url": "https://example.com/ir",
                "success": True,
                "status": "HTTP 200",
                "rows": 3,
                "error": "",
            },
        ]
    }
    table = source_attempt_table(audit)
    failed = failed_source_attempts(audit)
    assert len(table) == 2
    assert len(failed) == 1
    assert failed.iloc[0]["Kind"] == "Official PDF"
    assert failed.iloc[0]["Error / Reason"] == "HTTP 403"
    assert bool(failed.iloc[0]["Success"]) is False


def test_candidate_priority_is_question_then_source_grade_without_dropping_rows():
    candidates = pd.DataFrame([
        {"Question": "Q25", "Evidence Quality": "C — Secondary/context source", "Title": "C"},
        {"Question": "Q25", "Evidence Quality": "A — Company/Official disclosure", "Title": "A"},
        {"Question": "Q24", "Evidence Quality": "B — Independent financial source", "Title": "B"},
    ])
    ordered = prioritize_candidates(candidates)
    assert len(ordered) == 3
    assert list(ordered["Question"]) == ["Q24", "Q25", "Q25"]
    assert list(ordered[ordered["Question"].eq("Q25")]["Title"]) == ["A", "C"]


def test_unknown_ticker_does_not_fabricate_company_domain():
    assert official_search_domain("ZZZZ") == ""
