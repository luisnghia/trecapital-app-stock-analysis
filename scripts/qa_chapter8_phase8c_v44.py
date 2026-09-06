from __future__ import annotations

"""Live acceptance runner for Chapter 8 Phase 8C V44.

Runs DGC canonical refresh + Phase 8B structured bridge + Phase 8C research assistant,
then writes a compact JSON acceptance report. Research gaps are valid outputs.
"""

import inspect
import json
from pathlib import Path

import pandas as pd

import module1_dashboard as m1
from adapters.module2_web_research import KNOWN_COMPANY_DOMAINS
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
import modules.deep_company_analysis.chapter8_research as r


def main() -> int:
    ticker = "DGC"
    ok, paths, note = refresh_peer_canonical_bundle(ticker)
    assert ok and paths, f"DGC canonical refresh failed: {note}"
    overview_path, annual_path, quarter_path = paths
    company = m1._load_overview_cached(str(overview_path), ticker)
    company_name = str(
        getattr(company, "company_name", "")
        or getattr(company, "name", "")
        or "CTCP Tập đoàn Hóa chất Đức Giang"
    )
    annual_raw = m1._load_timeseries_cached(str(annual_path), ticker, "Y", 11)
    quarterly = m1._load_timeseries_cached(str(quarter_path), ticker, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    assert isinstance(annual, pd.DataFrame) and not annual.empty

    phase8b = build_phase8b_context(ticker, annual, chapter7_payload=None, guidance_rows=None)
    research = r.Chapter8ResearchAgent("data_cache/chapter8_phase8c_v44").search(
        ticker,
        company_name,
        chapter7_payload=None,
        max_results_per_query=1,
        max_official_documents=12,
    )

    assert list(research.quality["Question"]) == list(r.QUESTION_ORDER)
    assert len(research.source_attempts) >= 1, "DGC official/company source was not attempted"
    if not research.candidates.empty:
        assert research.candidates["Status"].eq("Candidate — analyst verify").all()
        assert research.candidates["Manager ID"].fillna("").eq("").all(), (
            "Phase 8C invented manager IDs although Chapter 7 manager master was not supplied"
        )

    source = inspect.getsource(r).casefold()
    assert "chapter 7 remains the manager identity/background single source of truth" in source
    assert "trecapital canonical financial data remains the financial single source of truth" in source
    assert "analyst_assessment" not in source
    assert "no management score" in source
    assert "no buy/hold/sell" in source
    assert any("ducgiangchem.vn" in str(x).lower() for x in KNOWN_COMPANY_DOMAINS.get("DGC", []))

    q46_labels = [label for label, _ in r.SUBTOPICS["Q46"]]
    for action in ch8.CAPITAL_ALLOCATION_ACTIONS:
        assert action in q46_labels
    assert not any("debt" in x.casefold() for x in q46_labels)

    q47_terms = " ".join(r.FOCUS_TERMS["Q47"]).casefold()
    assert "shares outstanding" not in q47_terms
    assert "share-count" not in q47_terms

    by_q = {
        q: int((research.candidates["Question"] == q).sum()) if not research.candidates.empty else 0
        for q in r.QUESTION_ORDER
    }
    grades = research.candidates["Source Grade"].value_counts().to_dict() if not research.candidates.empty else {}
    q46 = phase8b["q46_capital_allocation_context"]
    latest = str(q46.iloc[-1].get("Kỳ") or "") if isinstance(q46, pd.DataFrame) and not q46.empty else ""

    out = {
        "phase": "Chapter 8 Phase 8C Evidence Research Assistant V44",
        "acceptance": "PASS",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(note),
        "latest_period": latest,
        "research_candidates": int(len(research.candidates)),
        "candidate_by_question": by_q,
        "source_grades": {str(k): int(v) for k, v in grades.items()},
        "source_attempts": int(len(research.source_attempts)),
        "research_gaps": int(len(research.gaps)),
        "manager_reference_rows": int(len(research.manager_reference)),
        "manager_ssot": phase8b["manager_ssot"],
        "financial_ssot": phase8b["financial_ssot"],
        "candidate_status": "Candidate — analyst verify",
        "unknown_is_valid": True,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "note": research.note,
    }
    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    reports.joinpath("CH8_PHASE8C_DGC_LIVE_V44.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    reports.joinpath("CHAPTER8_PHASE8C_V44_ACCEPTANCE.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
