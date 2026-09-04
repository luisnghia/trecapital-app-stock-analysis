from __future__ import annotations

"""Chapter 4 Phase 4D — final acceptance and lock hardening.

This module does not make an investment judgement.  It hardens the Chapter-4 research system before
we call the implementation LOCKED:
- quarantine low-relevance/noisy Research-Assistant evidence instead of silently deleting it;
- require provenance for retained evidence;
- keep Shearn Q15/Q19 source/question architecture intact;
- verify Q16 corroboration remains evidence, never a Pricing-Power conclusion;
- verify all Research-Assistant guardrails remain off;
- allow stock-specific research gaps to remain *only when they are explicitly visible*.

"LOCKED" therefore means the Chapter-4 implementation, persistence and guardrails passed final
acceptance.  It does not mean every stock has complete evidence or that the analyst reached a
positive investment conclusion.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
import re

import pandas as pd

from modules.deep_company_analysis.chapter4 import Q15_SOURCES, QUESTION_KEYS
from modules.deep_company_analysis.chapter4_evidence import guardrails as c1_guardrails, _norm
from modules.deep_company_analysis.chapter4_evidence_c2 import guardrails as c2_guardrails
from modules.deep_company_analysis.chapter4_evidence_c3 import (
    Phase4C3Result,
    SHEARN_Q19_SUBTOPICS,
    guardrails as c3_guardrails,
    q19_coverage_matrix,
)


LOCK_VERSION = "Phase 4D — Chapter 4 LOCKED"

# Generic search engines occasionally return unrelated consumer pages.  We quarantine obvious noise
# but never delete a user's/analyst's row.  This list is deliberately narrow and testable.
NOISE_TEXT_PATTERNS = (
    "youtube tv membership",
    "manage a shared youtube tv",
    "amazon prime day",
    "smart devices still",
    "family group",
    "sports betting",
    "weather forecast",
    "horoscope",
    "recipe",
)

CHAPTER4_ANCHORS = (
    "competitive", "competition", "competitor", "cạnh tranh", "đối thủ", "market share", "thị phần",
    "price", "pricing", "giá bán", "sản lượng", "volume", "demand", "nhu cầu", "customer", "khách hàng",
    "margin", "roic", "industry", "ngành", "capacity", "công suất", "substitute", "thay thế", "import",
    "nhập khẩu", "supplier", "nhà cung cấp", "raw material", "nguyên liệu", "apatite", "apatit", "phosphorus",
    "phốt pho", "brand", "thương hiệu", "patent", "bằng sáng chế", "license", "giấy phép", "switching",
    "cost advantage", "lợi thế chi phí", "scale", "quy mô", "bankrupt", "phá sản", "shutdown", "đóng cửa",
    "exit market", "rút lui", "loss", "thua lỗ", "hedge", "commodity", "chuỗi cung ứng", "supply chain",
)

FAILURE_TERMS = (
    "failed", "failure", "thất bại", "bankrupt", "bankruptcy", "phá sản", "shutdown", "đóng cửa",
    "exit market", "rút lui", "insolvency", "mất khả năng thanh toán", "liquidat", "giải thể", "lỗ kéo dài",
)
FAILURE_CAUSE_TERMS = (
    "due to", "because", "caused by", "do ", "vì ", "bởi ", "loss", "lỗ", "debt", "nợ", "cost", "chi phí",
    "safety", "an toàn", "environment", "môi trường", "regulation", "quy định", "overcapacity", "dư cung",
    "mismanagement", "quản trị", "strategy", "chiến lược", "operating", "vận hành", "accident", "tai nạn",
)


def _domain(url: str) -> str:
    try:
        host = (urlparse(str(url or "")).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _entity_anchors(ticker: str, company_name: str, industry_name: str) -> tuple[str, ...]:
    out: list[str] = []
    safe = str(ticker or "").upper().strip()
    if safe:
        out.append(_norm(safe))
    company = _norm(company_name)
    if company:
        # Keep both the full phrase and meaningful tokens.  Generic Vietnamese corporate words are excluded.
        out.append(company)
        stop = {"ctcp", "cong", "ty", "tap", "doan", "co", "phan", "group", "corporation", "jsc"}
        out.extend(tok for tok in company.split() if len(tok) >= 4 and tok not in stop)
    industry = _norm(industry_name)
    if industry:
        out.append(industry)
    return tuple(dict.fromkeys(x for x in out if x))


def _has_anchor(text: str, anchors: tuple[str, ...]) -> bool:
    normalized = _norm(text)
    return any(anchor in normalized for anchor in anchors if anchor)


def _has_chapter4_anchor(text: str) -> bool:
    normalized = _norm(text)
    return any(_norm(term) in normalized for term in CHAPTER4_ANCHORS)


def _obvious_noise(text: str) -> bool:
    normalized = _norm(text)
    return any(_norm(term) in normalized for term in NOISE_TEXT_PATTERNS)


def sanitize_candidates(
    candidates: pd.DataFrame,
    ticker: str,
    company_name: str = "",
    industry_name: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (retained, quarantined) candidate evidence.

    A/B evidence is retained when it has a real URL, meaningful excerpt and Chapter-4 semantic anchor.
    Source-C evidence must additionally anchor to the target/company/industry.  Obvious unrelated pages are
    quarantined.  Quarantine is reversible and never changes analyst conclusions.
    """
    if not isinstance(candidates, pd.DataFrame) or candidates.empty:
        return pd.DataFrame(columns=list(candidates.columns) if isinstance(candidates, pd.DataFrame) else []), pd.DataFrame()

    anchors = _entity_anchors(ticker, company_name, industry_name)
    kept: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for _, row in candidates.iterrows():
        data = row.to_dict()
        title = str(data.get("Title") or data.get("Source Title") or "")
        snippet = str(data.get("Snippet") or data.get("Evidence Text") or "")
        url = str(data.get("URL") or data.get("Source URL / File") or "")
        quality = str(data.get("Evidence Quality") or data.get("Evidence Type") or "")
        text = f"{title} {snippet}"
        reason = ""
        if not (url.startswith("http://") or url.startswith("https://")):
            reason = "missing-valid-source-url"
        elif len(_norm(snippet)) < 30:
            reason = "excerpt-too-short"
        elif _obvious_noise(text):
            reason = "obvious-unrelated-search-noise"
        elif not _has_chapter4_anchor(text):
            reason = "no-chapter4-semantic-anchor"
        elif quality.startswith("C —") and not _has_anchor(text, anchors):
            reason = "source-c-not-anchored-to-target-or-industry"

        if reason:
            data["Quarantine Reason"] = reason
            quarantine.append(data)
        else:
            kept.append(data)

    kept_df = pd.DataFrame(kept, columns=list(candidates.columns)) if kept else pd.DataFrame(columns=list(candidates.columns))
    qcols = list(dict.fromkeys([*list(candidates.columns), "Quarantine Reason"]))
    quarantine_df = pd.DataFrame(quarantine, columns=qcols) if quarantine else pd.DataFrame(columns=qcols)
    return kept_df.reset_index(drop=True), quarantine_df.reset_index(drop=True)


def sanitize_evidence_matrix(
    rows: list[dict[str, Any]] | None,
    ticker: str,
    company_name: str = "",
    industry_name: str = "",
) -> tuple[list[dict[str, Any]], int]:
    """Mark noisy Research-Assistant rows as quarantined, preserving every stored row for audit."""
    if not isinstance(rows, list):
        return [], 0
    anchors = _entity_anchors(ticker, company_name, industry_name)
    out: list[dict[str, Any]] = []
    quarantined = 0
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        origin = str(row.get("Data Origin") or "")
        if "Chapter 4 Research Assistant Evidence Bridge" not in origin:
            out.append(row)
            continue
        quality = str(row.get("Evidence Type") or "")
        title = str(row.get("Source Title") or "")
        snippet = str(row.get("Evidence Text") or "")
        url = str(row.get("Source URL / File") or "")
        text = f"{title} {snippet}"
        reason = ""
        if not (url.startswith("http://") or url.startswith("https://")):
            reason = "missing-valid-source-url"
        elif len(_norm(snippet)) < 30:
            reason = "excerpt-too-short"
        elif _obvious_noise(text):
            reason = "obvious-unrelated-search-noise"
        elif not _has_chapter4_anchor(text):
            reason = "no-chapter4-semantic-anchor"
        elif quality.startswith("C —") and not _has_anchor(text, anchors):
            reason = "source-c-not-anchored-to-target-or-industry"
        if reason:
            quarantined += 1
            row["Status"] = "Quarantined — low relevance/noise"
            note = str(row.get("Analyst Note") or "").strip()
            row["Analyst Note"] = " | ".join(x for x in [note, f"Phase 4D quarantine: {reason}"] if x)
        out.append(row)
    return out, quarantined


def provenance_audit(candidates: pd.DataFrame) -> pd.DataFrame:
    columns = ["Check", "Passed", "Detail"]
    if not isinstance(candidates, pd.DataFrame) or candidates.empty:
        return pd.DataFrame([
            {"Check": "Retained evidence has provenance", "Passed": True, "Detail": "No retained candidate rows"}
        ], columns=columns)
    checks = {
        "source_url": candidates.get("URL", pd.Series([""] * len(candidates))).fillna("").astype(str).str.startswith(("http://", "https://")),
        "excerpt": candidates.get("Snippet", pd.Series([""] * len(candidates))).fillna("").astype(str).str.strip().str.len().ge(30),
        "quality": candidates.get("Evidence Quality", pd.Series([""] * len(candidates))).fillna("").astype(str).str.strip().ne(""),
        "source_method": candidates.get("Source Method", pd.Series([""] * len(candidates))).fillna("").astype(str).str.strip().ne(""),
    }
    rows: list[dict[str, Any]] = []
    for key, mask in checks.items():
        passed = bool(mask.all())
        rows.append({"Check": key, "Passed": passed, "Detail": f"{int(mask.sum())}/{len(mask)} row(s) passed"})
    return pd.DataFrame(rows, columns=columns)


def legitimate_failure_candidates(q19: pd.DataFrame) -> pd.DataFrame:
    """Conservative subset for Shearn's 'Why competitors failed'.

    A row must explicitly describe both a failure/exit event and at least one causal clue.  Merely mentioning
    'failure' in a search title/query is not enough.  Source C is excluded from this stronger subset.
    """
    if not isinstance(q19, pd.DataFrame) or q19.empty:
        return pd.DataFrame(columns=list(q19.columns) if isinstance(q19, pd.DataFrame) else [])
    rows: list[dict[str, Any]] = []
    for _, item in q19.iterrows():
        data = item.to_dict()
        if str(data.get("Subtopic") or "") != "Why Competitors Failed":
            continue
        quality = str(data.get("Evidence Quality") or "")
        if quality.startswith("C —"):
            continue
        text = _norm(f"{data.get('Title','')} {data.get('Snippet','')}")
        has_failure = any(_norm(term) in text for term in FAILURE_TERMS)
        has_cause = any(_norm(term) in text for term in FAILURE_CAUSE_TERMS)
        if has_failure and has_cause:
            rows.append(data)
    return pd.DataFrame(rows, columns=list(q19.columns)).reset_index(drop=True) if rows else pd.DataFrame(columns=list(q19.columns))


def q19_lock_coverage(q19: pd.DataFrame) -> pd.DataFrame:
    """Coverage for lock uses retained A/B evidence only; source C never closes a Shearn bucket."""
    if not isinstance(q19, pd.DataFrame) or q19.empty:
        return q19_coverage_matrix(pd.DataFrame())
    quality = q19.get("Evidence Quality", pd.Series([""] * len(q19))).fillna("").astype(str)
    strong = q19[quality.str.startswith(("A —", "B —"))].copy()
    return q19_coverage_matrix(strong)


def guardrail_audit() -> dict[str, bool]:
    merged: dict[str, bool] = {}
    for prefix, fn in (("4C1", c1_guardrails), ("4C2", c2_guardrails), ("4C3", c3_guardrails)):
        for key, value in fn().items():
            merged[f"{prefix}:{key}"] = bool(value)
    # Lock passes only when all these capabilities remain disabled/False.
    return merged


@dataclass
class Chapter4LockAudit:
    retained_candidates: pd.DataFrame
    quarantined_candidates: pd.DataFrame
    q19_coverage: pd.DataFrame
    failure_candidates: pd.DataFrame
    provenance: pd.DataFrame
    checks: pd.DataFrame
    research_gaps: list[str]
    lock_ready: bool
    note: str


def build_lock_audit(
    result: Phase4C3Result,
    ticker: str,
    company_name: str = "",
    industry_name: str = "",
) -> Chapter4LockAudit:
    retained, quarantined = sanitize_candidates(result.combined_candidates, ticker, company_name, industry_name)
    q19 = retained[retained.get("Question", pd.Series(dtype=str)).eq("Q19")].copy() if not retained.empty and "Question" in retained.columns else pd.DataFrame()
    coverage = q19_lock_coverage(q19)
    failures = legitimate_failure_candidates(q19)
    prov = provenance_audit(retained)

    q15_names = tuple(name for name, _origin in Q15_SOURCES)
    q15_origin_ok = len(Q15_SOURCES) == 7 and sum(1 for _name, origin in Q15_SOURCES if origin == "Shearn") == 6 and q15_names[-1] == "Other Source — Analyst-defined"
    q19_schema_ok = tuple(SHEARN_Q19_SUBTOPICS) == (
        "Limited / Direct Competition",
        "How Competitors Compete",
        "Fierceness / Price Competition",
        "Substitute Products",
        "Low-cost Country Competition",
        "Industry Standard / Market Position",
        "Industry Change / Capacity Competition",
        "Why Competitors Failed",
    )
    question_schema_ok = tuple(QUESTION_KEYS) == ("Q15", "Q16", "Q17", "Q18", "Q19", "Q20")
    guardrails = guardrail_audit()
    guardrails_ok = all(value is False for value in guardrails.values())
    provenance_ok = bool(prov["Passed"].all()) if not prov.empty else True
    c_rows = retained.get("Evidence Quality", pd.Series(dtype=str)).fillna("").astype(str).str.startswith("C —").sum() if not retained.empty else 0
    noise_ok = not any(_obvious_noise(f"{row.get('Title','')} {row.get('Snippet','')}") for _, row in retained.iterrows()) if not retained.empty else True
    q16_has_corroboration = isinstance(result.pricing_corroboration, pd.DataFrame) and not result.pricing_corroboration.empty
    covered_ab = int(coverage["Candidates"].fillna(0).astype(int).gt(0).sum()) if not coverage.empty else 0
    gaps = [
        f"Q19 — {row['Q19 logic']}: chưa có evidence A/B đủ điều kiện; giữ Research Gap."
        for _, row in coverage.iterrows() if int(row.get("Candidates") or 0) == 0
    ]
    # Missing failure evidence is acceptable for module lock only when it stays explicit; fabrication would fail.
    failure_gap_visible = bool(len(failures) > 0 or any("Why Competitors Failed" in gap for gap in gaps))

    checks_data = [
        ("Q15 taxonomy: 6 Shearn + 1 Analyst-defined", q15_origin_ok, f"sources={len(Q15_SOURCES)}"),
        ("Q15–Q20 schema locked", question_schema_ok, ",".join(QUESTION_KEYS)),
        ("Q19 eight-bucket architecture locked", q19_schema_ok, f"buckets={len(SHEARN_Q19_SUBTOPICS)}"),
        ("Research Assistant guardrails all disabled", guardrails_ok, f"flags={len(guardrails)}"),
        ("Retained evidence provenance complete", provenance_ok, f"rows={len(retained)}"),
        ("Obvious search noise quarantined", noise_ok, f"quarantined={len(quarantined)}; retained_C={int(c_rows)}"),
        ("Q16 has multi-source corroboration candidate", q16_has_corroboration, f"rows={len(result.pricing_corroboration)}"),
        ("Q19 substantial A/B coverage", covered_ab >= 6, f"covered={covered_ab}/8"),
        ("Competitor-failure gap is evidence-based or explicitly visible", failure_gap_visible, f"legitimate_failure_rows={len(failures)}"),
    ]
    checks = pd.DataFrame([{"Check": name, "Passed": bool(ok), "Detail": detail} for name, ok, detail in checks_data])
    lock_ready = bool(checks["Passed"].all())
    note = (
        f"{LOCK_VERSION}: {'READY' if lock_ready else 'NOT READY'} | retained={len(retained)}, quarantined={len(quarantined)}, "
        f"Q19 A/B coverage={covered_ab}/8, legitimate failure evidence={len(failures)}, open research gaps={len(gaps)}."
    )
    return Chapter4LockAudit(retained, quarantined, coverage, failures, prov, checks, gaps, lock_ready, note)


def finalize_record_for_lock(record: dict[str, Any], audit: Chapter4LockAudit) -> dict[str, Any]:
    """Persist lock metadata and quarantine status without modifying analyst-owned Q15–Q20 judgements."""
    out = dict(record)
    matrix, quarantined = sanitize_evidence_matrix(
        out.get("evidence_matrix") if isinstance(out.get("evidence_matrix"), list) else [],
        str(out.get("ticker") or ""),
        str(out.get("company_name") or ""),
        "",
    )
    out["evidence_matrix"] = matrix
    out["chapter4_lock"] = {
        "status": "LOCKED" if audit.lock_ready else "NOT_READY",
        "version": LOCK_VERSION,
        "locked_at": datetime.now().isoformat(timespec="seconds") if audit.lock_ready else "",
        "quarantined_existing_rows": quarantined,
        "open_research_gaps": list(audit.research_gaps),
        "note": audit.note,
    }
    return out
