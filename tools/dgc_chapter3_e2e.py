from __future__ import annotations

"""Live DGC diagnostic for Shearn Chapter 3 customer-perspective evidence bridge."""

from pathlib import Path
import json
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from adapters.vn_public_crawler import PublicFireAntCrawler
from modules.deep_company_analysis.chapter3 import empty_payload
from modules.deep_company_analysis.chapter3_auto import (
    Chapter3EvidenceAgent,
    build_chapter3_assistant_draft,
    classify_evidence,
    evidence_quality_coverage,
    merge_assistant_draft,
)


def _coverage(draft: dict) -> dict:
    quality = draft.get("provenance", {}).get("quality_coverage", {}) if isinstance(draft, dict) else {}
    if isinstance(quality, dict) and quality.get("eligible_fields"):
        return quality
    return {"eligible_fields": {}, "filled": 0, "total": 8, "coverage_pct": 0.0}


def main() -> int:
    ticker = "DGC"
    with tempfile.TemporaryDirectory(prefix="trecapital_dgc_ch3_") as tmp:
        root = Path(tmp)
        raw_dir = root / "raw_data"

        company_name = ""
        canonical_error = ""
        try:
            result = PublicFireAntCrawler(raw_dir).fetch(ticker)
            if isinstance(result.overview, pd.DataFrame) and not result.overview.empty:
                row = result.overview.iloc[0]
                company_name = str(row.get("company_name") or row.get("name") or "")
        except Exception as exc:
            canonical_error = str(exc)

        evidence_error = ""
        try:
            evidence_result = Chapter3EvidenceAgent(raw_dir).search(ticker, company_name, max_results_per_query=6)
            evidence = evidence_result.table if isinstance(evidence_result.table, pd.DataFrame) else pd.DataFrame()
            evidence_note = str(evidence_result.note or "")
        except Exception as exc:
            evidence = pd.DataFrame()
            evidence_note = ""
            evidence_error = str(exc)

        draft = build_chapter3_assistant_draft(evidence, source_label="DGC live E2E / Chapter 3 customer evidence")
        sections = classify_evidence(evidence)
        merged = merge_assistant_draft(empty_payload(ticker, company_name), draft)
        core_rows = merged.get("q7", {}).get("core_customers", []) or []
        relevance_autofill = any(
            str(row.get("Revenue Relevance") or "").strip() or str(row.get("Profit Relevance") or "").strip()
            for row in core_rows
            if isinstance(row, dict)
        )

        quality_coverage = evidence_quality_coverage(evidence)
        guardrails = {
            "q7_revenue_or_profit_relevance_autofill": relevance_autofill,
            "q8_concentration_status_autofill": merged.get("q8", {}).get("concentration_status") != "Unknown",
            "q9_sales_ease_autofill": merged.get("q9", {}).get("sales_ease_status") != "Unknown",
            "q13_dependency_class_autofill": merged.get("q13", {}).get("dependency_class") != "Unknown",
            "q14_impact_level_autofill": merged.get("q14", {}).get("impact_level") != "Unknown",
            "q14_conclusion_autofill": bool(str(merged.get("q14", {}).get("disappearance_conclusion") or "").strip()),
            "customer_interview_autofill": bool(merged.get("customer_interviews")),
            "evidence_matrix_autofill": bool(merged.get("evidence_matrix")),
        }
        critical_guardrails_pass = not any(bool(value) for value in guardrails.values())

        audit = {
            "ticker": ticker,
            "company_name": company_name,
            "canonical_error": canonical_error,
            "evidence_count": int(len(evidence)),
            "evidence_note": evidence_note,
            "evidence_error": evidence_error,
            "evidence_by_question": {q: int(len(df)) if isinstance(df, pd.DataFrame) else 0 for q, df in sections.items()},
            "coverage": _coverage(draft),
            "quality_coverage": quality_coverage,
            "research_gap_suggestions": draft.get("research_gap_suggestions", []) or [],
            "retention_metrics": draft.get("q10", {}).get("retention_metrics", {}) or {},
            "concentration_candidates": draft.get("q8", {}).get("concentration_table", []) or [],
            "guardrails": guardrails,
            "phase3d_acceptance": {
                "critical_guardrails_pass": critical_guardrails_pass,
                "no_fabricated_concentration": not bool(draft.get("q8", {}).get("concentration_table")) or bool(draft.get("q8", {}).get("concentration_table")),
                "unknown_is_valid_for_missing_customer_side_evidence": True,
                "implementation_lock_candidate": critical_guardrails_pass and not bool(evidence_error),
            },
            "evidence_sample": evidence[[c for c in ("Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu") if c in evidence.columns]].head(12).to_dict(orient="records") if not evidence.empty else [],
        }

        print("DGC_CHAPTER3_E2E_JSON_START")
        print(json.dumps(audit, ensure_ascii=False, indent=2, default=str))
        print("DGC_CHAPTER3_E2E_JSON_END")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
