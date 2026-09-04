from __future__ import annotations

"""Chapter 5 Phase 5D — implementation lock and DGC end-to-end acceptance helpers.

The lock is deliberately split into two concepts:

1. **Implementation Lock** — verifies that the Chapter 5 implementation still obeys the
   source-locked Q21–Q26 architecture, Trecapital Single Source of Truth, no-fabrication rules,
   and analyst-ownership guardrails.
2. **Research Readiness** — reports whether the *current ticker* has enough quantitative context
   and candidate source evidence to proceed with analyst work.

Neither concept is an investment-quality score. PASS never means BUY/HOLD/SELL, nor does it mean
that the analyst has answered the six questions.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pandas as pd

from modules.deep_company_analysis.chapter5 import (
    QUESTION_KEYS,
    SHEARN_Q23_RISKS,
    cross_question_checks,
    guardrails as chapter5_guardrails,
)
from modules.deep_company_analysis.chapter5_evidence import (
    QUESTIONS as EVIDENCE_QUESTIONS,
    candidate_coverage,
    evidence_quality_summary,
    guardrails as evidence_guardrails,
    merge_candidates_into_record,
)

LOCK_VERSION = "5D"

SOURCE_LOCK_QUESTIONS: dict[str, str] = {
    "Q21": "What are the fundamentals of the business?",
    "Q22": "What are the operating metrics of the business that you need to monitor?",
    "Q23": "What are the key risks the business faces?",
    "Q24": "How does inflation affect the business?",
    "Q25": "Is the business's balance sheet strong or weak?",
    "Q26": "What is the return on invested capital for the business?",
}

ANALYST_OWNED_KEYS = (
    "q21", "q22", "q23", "q24", "q25", "q26",
    "q21_fundamentals", "q22_metrics", "q22_metric_history", "q23_risks",
    "q24_inflation_exposures", "q25_debt_instruments", "q25_off_balance_obligations",
    "q25_covenants", "q26_roic_variants", "q26_roic_adjustments", "q26_reinvestment",
    "top_operating_strengths", "top_operating_weaknesses", "deterioration_watch",
    "critical_unknowns", "analyst_summary", "question_status", "question_trend",
)


@dataclass(frozen=True)
class Chapter5LockReport:
    implementation_status: str
    implementation_checks: pd.DataFrame
    research_readiness: pd.DataFrame
    cross_question_diagnostics: tuple[str, ...]
    note: str

    @property
    def passed(self) -> bool:
        return self.implementation_status == "PASS"


def _contains_confidence(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if "confidence" in str(key).casefold():
                return True
            if _contains_confidence(item):
                return True
    elif isinstance(value, list):
        return any(_contains_confidence(item) for item in value)
    return False


def _all_false(flags: dict[str, Any] | None) -> bool:
    return bool(flags) and all(value is False for value in flags.values())


def _quant_guardrails(quant_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(quant_context, dict):
        return {}
    flags = quant_context.get("guardrails")
    return flags if isinstance(flags, dict) else {}


def _canonical_provenance_ok(quant_context: dict[str, Any] | None) -> bool:
    if not isinstance(quant_context, dict):
        return True  # absence is a research-readiness issue, not an implementation-lock failure
    provenance = quant_context.get("provenance")
    if not isinstance(provenance, dict):
        return False
    source_module = str(provenance.get("source_module") or "").casefold()
    data_origin = str(provenance.get("data_origin") or "").casefold()
    source_label = str(provenance.get("source_label") or "").strip()
    return bool(source_label) and (
        "trecapital" in source_module
        or "module 1" in source_module
        or "module1" in source_module
        or "canonical" in data_origin
        or "trecapital" in data_origin
    )


def _candidate_status_safe(candidates: pd.DataFrame | None) -> bool:
    if candidates is None or not isinstance(candidates, pd.DataFrame) or candidates.empty:
        return True
    if "Question" not in candidates.columns:
        return False
    questions = set(candidates["Question"].dropna().astype(str))
    return questions.issubset(set(SOURCE_LOCK_QUESTIONS))


def _merge_preserves_analyst(record: dict[str, Any], candidates: pd.DataFrame | None) -> bool:
    if not isinstance(record, dict):
        return False
    if candidates is None or not isinstance(candidates, pd.DataFrame) or candidates.empty:
        return True
    before = deepcopy(record)
    merged = merge_candidates_into_record(deepcopy(record), candidates, gaps=[])
    for key in ANALYST_OWNED_KEYS:
        if merged.get(key) != before.get(key):
            return False
    return True


def implementation_checks(
    record: dict[str, Any],
    quant_context: dict[str, Any] | None = None,
    candidates: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Hard implementation checks. Missing ticker research data does not fail the architecture."""
    question_keys_ok = tuple(QUESTION_KEYS) == tuple(SOURCE_LOCK_QUESTIONS) == tuple(EVIDENCE_QUESTIONS)
    shearn_risks_ok = len(SHEARN_Q23_RISKS) == 17 and len({risk for risk, _ in SHEARN_Q23_RISKS}) == 17
    chapter_flags = chapter5_guardrails()
    evidence_flags = evidence_guardrails()
    quant_flags = _quant_guardrails(quant_context)

    rows = [
        {
            "Check": "Source-locked Q21–Q26",
            "Hard": True,
            "PASS": question_keys_ok,
            "Detail": "Exactly six Chapter-5 questions; no score-derived replacement question.",
        },
        {
            "Check": "Q23 Shearn risk universe",
            "Hard": True,
            "PASS": shearn_risks_ok,
            "Detail": "17 source-listed risk examples remain available as the fresh-record seed; analyst deletion stays persistent.",
        },
        {
            "Check": "No Confidence field",
            "Hard": True,
            "PASS": not _contains_confidence(record),
            "Detail": "Chapter 5 policy: Confidence is intentionally absent from all payload levels.",
        },
        {
            "Check": "Chapter 5 analyst-ownership guardrails",
            "Hard": True,
            "PASS": _all_false(chapter_flags),
            "Detail": "No automatic fundamental/risk/inflation/balance-sheet/ROIC/reinvestment/gate/trade conclusion.",
        },
        {
            "Check": "Phase 5C evidence guardrails",
            "Hard": True,
            "PASS": _all_false(evidence_flags),
            "Detail": "No fabrication, no automatic Severity/Frequency, covenant/off-BS, compounder or trade conclusion.",
        },
        {
            "Check": "Phase 5B quantitative guardrails",
            "Hard": True,
            "PASS": True if quant_context is None else _all_false(quant_flags),
            "Detail": "When canonical context is present, every quantitative auto-conclusion guardrail must remain False.",
        },
        {
            "Check": "Canonical provenance / Single Source of Truth",
            "Hard": True,
            "PASS": _canonical_provenance_ok(quant_context),
            "Detail": "Financial context must identify the Trecapital/canonical pipeline; missing context is handled separately as readiness.",
        },
        {
            "Check": "Candidate evidence maps only to Q21–Q26",
            "Hard": True,
            "PASS": _candidate_status_safe(candidates),
            "Detail": "Navigation/source links are not promoted into unrelated evidence questions.",
        },
        {
            "Check": "Research refresh preserves analyst fields",
            "Hard": True,
            "PASS": _merge_preserves_analyst(record, candidates),
            "Detail": "Saving Research Assistant candidates cannot overwrite analyst-owned Q21–Q26 objects/registers.",
        },
        {
            "Check": "Missing evidence is not a negative judgement",
            "Hard": True,
            "PASS": evidence_flags.get("missing_evidence_is_low_risk") is False,
            "Detail": "A gap remains a Research Gap; it never becomes Low Risk/Strong by default.",
        },
    ]
    return pd.DataFrame(rows)


def research_readiness(
    quant_context: dict[str, Any] | None = None,
    candidates: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Ticker-specific readiness diagnostics. This table is not part of Implementation PASS/FAIL."""
    candidates = candidates if isinstance(candidates, pd.DataFrame) else pd.DataFrame()
    quality = evidence_quality_summary(candidates)
    quality_map = {str(row["Question"]): row.to_dict() for _, row in quality.iterrows()}

    q22_quant = isinstance((quant_context or {}).get("q22_context"), pd.DataFrame) and not (quant_context or {}).get("q22_context").empty
    q25_quant = isinstance((quant_context or {}).get("q25_context"), pd.DataFrame) and not (quant_context or {}).get("q25_context").empty
    q26_quant = isinstance((quant_context or {}).get("q26_variants"), pd.DataFrame) and not (quant_context or {}).get("q26_variants").empty
    quant_by_question = {"Q21": None, "Q22": q22_quant, "Q23": None, "Q24": None, "Q25": q25_quant, "Q26": q26_quant}

    rows: list[dict[str, Any]] = []
    for question in SOURCE_LOCK_QUESTIONS:
        item = quality_map.get(question, {})
        candidate_count = int(item.get("Candidates", 0) or 0)
        source_a = int(item.get("Nguồn A", 0) or 0)
        counter = int(item.get("Counter", 0) or 0)
        quant_available = quant_by_question[question]
        if candidate_count == 0:
            readiness = "Gap — chưa có candidate evidence"
        elif source_a == 0:
            readiness = "Mỏng — chưa có Source A"
        elif quant_available is False:
            readiness = "Mỏng — thiếu canonical quant context"
        else:
            readiness = "Research-ready — analyst verify"
        rows.append({
            "Question": question,
            "Candidate Evidence": candidate_count,
            "Source A": source_a,
            "Counter-Evidence Candidates": counter,
            "Canonical Quant": "N/A" if quant_available is None else ("Yes" if quant_available else "No"),
            "Readiness": readiness,
            "Reminder": "Không phải quality score; analyst vẫn phải xác minh nguồn và tự kết luận.",
        })
    return pd.DataFrame(rows)


def evaluate_chapter5_lock(
    record: dict[str, Any],
    quant_context: dict[str, Any] | None = None,
    candidates: pd.DataFrame | None = None,
    chapter4_record: dict[str, Any] | None = None,
) -> Chapter5LockReport:
    checks = implementation_checks(record, quant_context, candidates)
    hard = checks[checks["Hard"].eq(True)] if not checks.empty else pd.DataFrame()
    passed = bool(not hard.empty and hard["PASS"].astype(bool).all())
    readiness = research_readiness(quant_context, candidates)
    diagnostics = tuple(cross_question_checks(record, chapter4_record))
    status = "PASS" if passed else "FAIL"
    note = (
        f"Chapter 5 Phase {LOCK_VERSION} Implementation Lock = {status}. "
        "PASS khóa phương pháp/guardrails của module, không xác nhận doanh nghiệp tốt/xấu và không thay analyst judgement."
    )
    return Chapter5LockReport(status, checks, readiness, diagnostics, note)


def dgc_lock_acceptance(
    record: dict[str, Any],
    quant_context: dict[str, Any],
    candidates: pd.DataFrame,
) -> tuple[bool, list[str]]:
    """Stricter DGC E2E acceptance used by CI. Still no investment conclusion."""
    report = evaluate_chapter5_lock(record, quant_context, candidates)
    failures: list[str] = []
    if not report.passed:
        failures.extend(
            report.implementation_checks.loc[~report.implementation_checks["PASS"].astype(bool), "Check"].astype(str).tolist()
        )
    coverage = candidate_coverage(candidates)
    for question in SOURCE_LOCK_QUESTIONS:
        if int(coverage.get(question, 0)) <= 0:
            failures.append(f"{question}: no real candidate evidence")
    if candidates.empty or not candidates["Evidence Quality"].astype(str).str.startswith("A —").any():
        failures.append("DGC: no Source A evidence")
    for key in ("q22_context", "q25_context", "q26_variants"):
        value = quant_context.get(key)
        if not isinstance(value, pd.DataFrame) or value.empty:
            failures.append(f"DGC: canonical {key} unavailable")
    return not failures, failures


def guardrails() -> dict[str, bool]:
    return {
        "implementation_pass_is_investment_score": False,
        "research_ready_is_quality_score": False,
        "lock_overwrites_analyst_judgement": False,
        "lock_changes_research_gate": False,
        "lock_emits_buy_hold_sell": False,
        "counter_evidence_absence_means_safe": False,
        "missing_quant_means_weak_balance_sheet": False,
        "high_roic_means_compounder": False,
    }
