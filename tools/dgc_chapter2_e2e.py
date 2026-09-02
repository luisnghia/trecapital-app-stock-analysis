from __future__ import annotations

"""Live diagnostic for DGC / Shearn Chapter 2.

This script intentionally uses the same Trecapital public financial crawler and Chapter 2 evidence
agent used by the app. It prints a compact audit instead of changing analyst records. Network
failures are reported as gaps rather than replaced with invented data.
"""

from pathlib import Path
from types import SimpleNamespace
import json
import sys
import tempfile

# Running `python tools/dgc_chapter2_e2e.py` makes Python put tools/ rather than repo root on
# sys.path. Add repo root explicitly so this diagnostic executes exactly as the CI command does.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from adapters.vn_public_crawler import PublicFireAntCrawler
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter2_auto import (
    Chapter2EvidenceAgent,
    build_chapter2_assistant_draft,
    classify_evidence,
)


def _company_from_overview(df: pd.DataFrame):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    return SimpleNamespace(**df.iloc[0].fillna("").to_dict())


def _coverage(draft: dict) -> dict:
    q3 = draft.get("q3", {})
    q4 = draft.get("q4", {})
    q5 = draft.get("q5", {})
    q6 = draft.get("q6", {})
    eligible = {
        "Q3 business_flow": bool(str(q3.get("business_flow") or "").strip()),
        "Q4 money_summary": bool(str(q4.get("money_summary") or "").strip()),
        "Q5 evolution table": bool(q5.get("evolution")),
        "Q6 foreign_markets table": bool(q6.get("foreign_markets")),
        "Q6 foreign_strategy_summary": bool(str(q6.get("foreign_strategy_summary") or "").strip()),
        "Q6 currency_evidence": bool(q6.get("currency_evidence")),
    }
    filled = sum(1 for ok in eligible.values() if ok)
    return {
        "eligible_fields": eligible,
        "filled": filled,
        "total": len(eligible),
        "coverage_pct": round(filled / len(eligible) * 100.0, 1),
    }


def main() -> int:
    ticker = "DGC"
    with tempfile.TemporaryDirectory(prefix="trecapital_dgc_ch2_") as tmp:
        root = Path(tmp)
        raw_dir = root / "raw_data"

        financial_error = ""
        try:
            result = PublicFireAntCrawler(raw_dir).fetch(ticker)
        except Exception as exc:
            result = None
            financial_error = str(exc)

        if result is not None:
            company = _company_from_overview(result.overview)
            annual = append_ttm_row(result.annual, result.quarterly)
            company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "") if company else ""
            finance = {
                "overview_rows": int(len(result.overview)),
                "annual_rows": int(len(result.annual)),
                "quarterly_rows": int(len(result.quarterly)),
                "ttm_rows": int(len(annual)),
                "note": str(result.note or ""),
            }
        else:
            company = None
            annual = pd.DataFrame()
            company_name = ""
            finance = {"overview_rows": 0, "annual_rows": 0, "quarterly_rows": 0, "ttm_rows": 0, "note": financial_error}

        evidence_error = ""
        try:
            evidence_result = Chapter2EvidenceAgent(raw_dir).search(ticker, company_name, max_results_per_query=6)
            evidence = evidence_result.table if isinstance(evidence_result.table, pd.DataFrame) else pd.DataFrame()
            evidence_note = str(evidence_result.note or "")
        except Exception as exc:
            evidence = pd.DataFrame()
            evidence_note = ""
            evidence_error = str(exc)

        draft = build_chapter2_assistant_draft(company, annual, evidence, source_label="DGC live E2E / Trecapital")
        sections = classify_evidence(evidence)
        coverage = _coverage(draft)
        q4_metrics = draft.get("q4", {}).get("financial_metrics", {})

        audit = {
            "ticker": ticker,
            "company_name": company_name,
            "financial": finance,
            "financial_error": financial_error,
            "evidence_count": int(len(evidence)),
            "evidence_note": evidence_note,
            "evidence_error": evidence_error,
            "evidence_by_question": {key: int(len(value)) if isinstance(value, pd.DataFrame) else 0 for key, value in sections.items()},
            "coverage": coverage,
            "q4_financial_metrics": q4_metrics,
            "q5_timeline_count": len(draft.get("q5", {}).get("evolution", []) or []),
            "q6_foreign_markets": draft.get("q6", {}).get("foreign_markets", []) or [],
            "q6_currency_evidence": draft.get("q6", {}).get("currency_evidence", []) or [],
            "guardrails": {
                "q1_autofill": False,
                "q2_autofill": False,
                "q3_own_words_autofill": False,
                "q5_skill_vs_luck_autofill": False,
            },
        }

        print("DGC_CHAPTER2_E2E_JSON_START")
        print(json.dumps(audit, ensure_ascii=False, indent=2, default=str))
        print("DGC_CHAPTER2_E2E_JSON_END")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
