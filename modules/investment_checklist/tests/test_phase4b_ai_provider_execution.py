from __future__ import annotations

from datetime import date
import json
import sqlite3

import httpx
import pytest

from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.services.ai_provider_execution import (
    OpenAIResponsesProvider,
    ProviderExecutionError,
    ProviderResult,
    execute_provider_run,
)
from modules.investment_checklist.services.ai_research_assistant import (
    decide_ai_suggestion,
    list_ai_runs,
    list_ai_suggestions,
)
from modules.investment_checklist.services.evidence_workspace import create_source
from modules.investment_checklist.services.source_content import (
    create_source_content_version,
    parse_page_selection,
)


CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"
SOURCE_TEXT = """[[PAGE 94]]
Tỷ lệ nợ xấu hợp nhất cuối năm là 0,97%.

[[PAGE 95]]
Tỷ lệ bao phủ nợ xấu được duy trì ở mức thận trọng.
"""


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "phase4b.db", CATALOG)
    repo.initialize()
    return repo


def _seed(repo, suffix="RUN"):
    company_ref_id = repo.upsert_company_ref(
        host_company_key=f"PHASE4B:{suffix}", ticker="VCB", company_name="Vietcombank",
        exchange="HOSE", company_type="bank", actor="test",
    )
    review_id = repo.create_review(
        company_ref_id, date(2026, 8, 22), analyst_user_id="analyst",
        review_reason="Phase 4B provider QA",
    )
    source_id = create_source(
        repo, company_ref_id=company_ref_id, source_type="annual_report",
        title=f"VCB Annual Report 2025 {suffix}", publisher="VCB",
        document_date=date(2025, 12, 31), reliability=5, actor="analyst",
    )
    content_id = create_source_content_version(
        repo, company_ref_id=company_ref_id, source_id=source_id,
        content_text=SOURCE_TEXT, content_type="application/pdf", locator_scheme="page",
        original_filename="vcb-2025.pdf", scope_label="pages 94-95", actor="analyst",
    )
    return company_ref_id, review_id, source_id, content_id


def _suggestion(source_id, content_id, excerpt="Tỷ lệ nợ xấu hợp nhất cuối năm là 0,97%."):
    return {
        "suggestion_type": "evidence_candidate",
        "source_id": source_id,
        "source_content_id": content_id,
        "question_id": "Q22",
        "evidence_type": "metric",
        "relationship": "supporting",
        "direction": "supports",
        "locator_text": "PAGE 94",
        "excerpt": excerpt,
        "rationale": "NPL là operating driver trọng yếu của ngân hàng.",
        "confidence": 4,
        "materiality": 5,
    }


class FakeProvider:
    def __init__(self, suggestions):
        self.suggestions = suggestions
        self.called = 0

    def generate(self, **kwargs):
        self.called += 1
        assert kwargs["response_schema"]["additionalProperties"] is False
        assert "never an investment recommendation" in kwargs["instructions"]
        return ProviderResult(
            suggestions=self.suggestions,
            model_version="gpt-5.6-terra-2026-08-01",
            metadata={
                "provider_request_id": "req_test",
                "provider_response_id": "resp_test",
                "client_request_id": "client_test",
                "input_tokens": 1200,
                "output_tokens": 200,
                "total_tokens": 1400,
                "latency_ms": 850,
                "attempt_count": 1,
                "service_tier": "default",
            },
        )


def test_provider_run_persists_usage_exact_content_hash_and_never_assessment(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, source_id, content_id = _seed(repo)
    fake = FakeProvider([_suggestion(source_id, content_id)])
    result = execute_provider_run(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        run_type="evidence_extraction",
        source_content_ids=[content_id],
        actor="analyst",
        api_key="server-test-key",
        provider=fake,
    )
    assert fake.called == 1 and result["suggestion_count"] == 1
    run = list_ai_runs(repo, review_id)[0]
    assert run["status"] == "completed"
    assert run["provider_request_id"] == "req_test"
    assert run["total_tokens"] == 1400 and run["latency_ms"] == 850
    item = list_ai_suggestions(repo, review_id)[0]
    assert item["source_content_id"] == content_id
    assert len(item["source_content_hash_at_run"]) == 64
    with repo._conn() as c:
        assert c.execute(
            "SELECT COUNT(*) n FROM analyst_assessments WHERE review_id=?", (review_id,)
        ).fetchone()["n"] == 0
    promoted = decide_ai_suggestion(
        repo, item["id"], decision="accepted",
        reason="Đã đối chiếu PAGE 94 với báo cáo gốc.", actor="analyst",
    )
    assert promoted["created_evidence_id"] and promoted["created_link_id"]


def test_hallucinated_excerpt_is_rejected_and_failed_run_is_audited(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, source_id, content_id = _seed(repo, "HALLUCINATION")
    fake = FakeProvider([_suggestion(source_id, content_id, excerpt="NPL bằng 0,50%.")])
    with pytest.raises(ValidationError, match="citation hallucination.*Failed run"):
        execute_provider_run(
            repo, company_ref_id=company_ref_id, review_id=review_id,
            run_type="evidence_extraction", source_content_ids=[content_id],
            actor="analyst", api_key="server-test-key", provider=fake,
        )
    runs = list_ai_runs(repo, review_id)
    assert len(runs) == 1 and runs[0]["status"] == "failed"
    assert runs[0]["suggestion_count"] == 0
    assert list_ai_suggestions(repo, review_id) == []


def test_pdf_locator_must_match_the_page_containing_the_excerpt(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, source_id, content_id = _seed(repo, "WRONGPAGE")
    wrong_page = _suggestion(source_id, content_id)
    wrong_page["locator_text"] = "PAGE 95"
    with pytest.raises(ValidationError, match="không nằm tại PAGE 95"):
        execute_provider_run(
            repo, company_ref_id=company_ref_id, review_id=review_id,
            run_type="evidence_extraction", source_content_ids=[content_id],
            actor="analyst", api_key="server-test-key", provider=FakeProvider([wrong_page]),
        )


def test_provider_failure_is_recorded_without_retrying_inside_transaction(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, _source_id, content_id = _seed(repo, "FAIL")

    class FailingProvider:
        def generate(self, **kwargs):
            raise ProviderExecutionError(
                "rate limited",
                metadata={"client_request_id": "client_fail", "attempt_count": 3, "latency_ms": 3010},
            )

    with pytest.raises(ProviderExecutionError, match="Failed run"):
        execute_provider_run(
            repo, company_ref_id=company_ref_id, review_id=review_id,
            run_type="contradiction_scan", source_content_ids=[content_id],
            actor="analyst", api_key="server-test-key", provider=FailingProvider(),
        )
    failed = list_ai_runs(repo, review_id)[0]
    assert failed["status"] == "failed" and failed["attempt_count"] == 3
    assert failed["client_request_id"] == "client_fail"


def test_latest_content_and_completed_review_guardrails(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, source_id, content_id = _seed(repo, "DRIFT")
    newer_id = create_source_content_version(
        repo, company_ref_id=company_ref_id, source_id=source_id,
        content_text=SOURCE_TEXT + "\n[[PAGE 96]]\nBổ sung version mới.",
        content_type="application/pdf", locator_scheme="page", actor="analyst",
    )
    fake = FakeProvider([])
    with pytest.raises(ValidationError, match="không phải version mới nhất"):
        execute_provider_run(
            repo, company_ref_id=company_ref_id, review_id=review_id,
            run_type="research_gap", source_content_ids=[content_id],
            actor="analyst", api_key="server-test-key", provider=fake,
        )
    repo.finalize_review(review_id, actor="analyst", finalize_reason="Lock provider QA")
    with pytest.raises(ValidationError, match="provider execution bị khóa"):
        execute_provider_run(
            repo, company_ref_id=company_ref_id, review_id=review_id,
            run_type="research_gap", source_content_ids=[newer_id],
            actor="analyst", api_key="server-test-key", provider=fake,
        )
    assert fake.called == 0


def test_openai_responses_contract_uses_structured_output_no_store_and_audits_request_id():
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        seen["client_request_id"] = request.headers["x-client-request-id"]
        return httpx.Response(
            200,
            headers={"x-request-id": "req_live_contract"},
            json={
                "id": "resp_live_contract",
                "status": "completed",
                "model": "gpt-5.6-terra-2026-08-01",
                "service_tier": "default",
                "output": [{
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps({"suggestions": []})}],
                }],
                "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIResponsesProvider("server-only-key", http_client=client)
    result = provider.generate(
        model="gpt-5.6-terra",
        instructions="Return suggestions only.",
        input_text="Source content",
        response_schema={
            "type": "object", "properties": {"suggestions": {"type": "array", "items": {"type": "object"}}},
            "required": ["suggestions"], "additionalProperties": False,
        },
        max_output_tokens=2_000,
        reasoning_effort="low",
        safety_identifier="hashed-user",
        metadata={"workflow": "qa"},
    )
    assert result.suggestions == []
    assert result.metadata["provider_request_id"] == "req_live_contract"
    assert result.metadata["total_tokens"] == 12
    assert seen["body"]["store"] is False
    assert seen["body"]["text"]["format"]["type"] == "json_schema"
    assert seen["body"]["text"]["format"]["strict"] is True
    assert seen["body"]["safety_identifier"] == "hashed-user"
    assert "server-only-key" not in json.dumps(seen["body"])
    client.close()


def test_provider_refusal_keeps_request_id_for_failed_run_audit():
    def handler(_request: httpx.Request):
        return httpx.Response(
            200,
            headers={"x-request-id": "req_refusal"},
            json={
                "id": "resp_refusal", "status": "completed", "model": "gpt-5.6-terra",
                "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "Cannot comply"}]}],
                "usage": {"input_tokens": 10, "output_tokens": 1, "total_tokens": 11},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIResponsesProvider("server-only-key", http_client=client)
    with pytest.raises(ProviderExecutionError) as captured:
        provider.generate(
            model="gpt-5.6-terra", instructions="Return suggestions only.", input_text="Source content",
            response_schema={
                "type": "object", "properties": {"suggestions": {"type": "array", "items": {"type": "object"}}},
                "required": ["suggestions"], "additionalProperties": False,
            },
            max_output_tokens=2_000, reasoning_effort="low", safety_identifier="hashed-user",
            metadata={"workflow": "qa"},
        )
    assert captured.value.metadata["provider_request_id"] == "req_refusal"
    assert captured.value.metadata["provider_response_id"] == "resp_refusal"
    assert captured.value.metadata["total_tokens"] == 11
    client.close()


def test_page_selection_parser():
    assert parse_page_selection("1-3,5,7-8", 10) == [0, 1, 2, 4, 6, 7]
    assert parse_page_selection("", 3) == [0, 1, 2]
    with pytest.raises(ValidationError, match="khoảng 1–3"):
        parse_page_selection("4", 3)


def test_sqlite_v2384_tables_migrate_before_new_source_content_index(tmp_path):
    path = tmp_path / "legacy-v2384.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE ai_research_runs(
      id INTEGER PRIMARY KEY AUTOINCREMENT, company_ref_id INTEGER, review_id INTEGER,
      run_type TEXT, status TEXT, provider TEXT, model_name TEXT, model_version TEXT,
      prompt_version TEXT, prompt_hash TEXT, source_manifest_json TEXT, source_manifest_hash TEXT,
      input_hash TEXT, output_hash TEXT, requested_by TEXT, created_at TEXT, completed_at TEXT, error_text TEXT
    );
    CREATE TABLE ai_research_suggestions(
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, company_ref_id INTEGER, review_id INTEGER,
      suggestion_no INTEGER, suggestion_type TEXT, source_id INTEGER, source_hash_at_run TEXT,
      question_id TEXT, evidence_type TEXT, relationship TEXT, direction TEXT, locator_text TEXT,
      excerpt TEXT, rationale TEXT, confidence INTEGER, materiality INTEGER, payload_hash TEXT, created_at TEXT
    );
    """)
    conn.close()
    repo = SQLiteChecklistRepository(path, CATALOG)
    repo.initialize()
    with repo._conn() as c:
        run_cols = {row[1] for row in c.execute("PRAGMA table_info(ai_research_runs)")}
        suggestion_cols = {row[1] for row in c.execute("PRAGMA table_info(ai_research_suggestions)")}
        indexes = {row[1] for row in c.execute("PRAGMA index_list(ai_research_suggestions)")}
    assert {"provider_request_id", "total_tokens", "latency_ms"} <= run_cols
    assert {"source_content_id", "source_content_hash_at_run"} <= suggestion_cols
    assert "ix_ai_suggestions_source_content" in indexes
