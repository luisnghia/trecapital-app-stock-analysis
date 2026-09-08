from __future__ import annotations

"""Chapter 11 Phase 11D / V85 — source research and Research Assistant bridge.

Source lock: Michael Shearn, The Investment Checklist, Chapter 11, Q58-Q59.
The module creates deterministic research plans and candidate-evidence records for the
15 source-locked M&A evidence dimensions. Research Assistant output is candidate evidence
only. Analyst verification and explicit promotion are required before any candidate enters
the Chapter 11 workspace.

No M&A score, weighted score, automatic acquisition-success conclusion, synergy forecast,
BUY/HOLD/SELL, intrinsic-value/MOS change, Investment Research Gate change, or duplicate
financial SSOT is introduced here.
"""

from copy import deepcopy
from hashlib import sha256
from typing import Any, Iterable
from urllib.parse import urlparse
import re

import pandas as pd

import modules.deep_company_analysis.chapter11 as ch11

QUESTION_ORDER = ch11.QUESTION_KEYS
RESEARCH_BOUNDARY = (
    "Candidate evidence only; analyst verification and explicit promotion required. "
    "No M&A score, acquisition-success conclusion, synergy forecast, valuation/MOS change, "
    "Investment Research Gate change, or BUY/HOLD/SELL."
)

QUERY_TERMS: dict[str, tuple[str, str]] = {
    "Q58": (
        "quyết định M&A động cơ mua lại sáp nhập lý do chi phí rủi ro synergy khách hàng roll-up",
        "M&A acquisition decision rationale motivation merits prospects costs risks synergies customers roll-up",
    ),
    "Q59": (
        "M&A lịch sử thành công năng lực cốt lõi hiểu doanh nghiệp giữ khách hàng nhân sự giá mua tài trợ nợ cổ phiếu",
        "past acquisitions success core competency target understanding customer retention employee retention price discipline consideration financing debt equity",
    ),
}

OFFICIAL_HOST_SUFFIXES = (
    "sec.gov", "investor.gov", "gov.vn", "hsx.vn", "hnx.vn", "upcom.vn",
)

CANDIDATE_COLUMNS = [
    "Select", "Candidate ID", "Question", "Dimension ID", "Dimension", "Direction",
    "Source Grade", "Source Family", "Source Title", "Source URL / File", "Source Date",
    "As-of Date", "Evidence Text / Reference", "Data Origin", "Status",
]

PLAN_COLUMNS = [
    "Question", "Dimension ID", "Dimension", "Printed Pages", "Source Anchor", "SSOT Dependency",
    "Official Query", "Broad Query", "Research Boundary",
]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tokens(value: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9_]+", value.casefold()) if len(tok) >= 3}


def _catalog_index() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in ch11.dimension_catalog()}


def dimension_terms(dimension_id: str) -> tuple[str, ...]:
    row = _catalog_index().get(dimension_id)
    if not row:
        return ()
    raw = f"{row.get('label', '')} {row.get('anchor', '')} {row.get('ssot_dependency', '')}"
    return tuple(sorted(_tokens(raw)))


def research_plan(ticker: str, company_name: str = "", official_domain: str = "") -> pd.DataFrame:
    symbol = _text(ticker).upper()
    company = _text(company_name) or symbol
    domain = _text(official_domain).lower().replace("https://", "").replace("http://", "").strip("/")
    rows: list[dict[str, Any]] = []
    for item in ch11.dimension_catalog():
        q = item["question"]
        vi, en = QUERY_TERMS[q]
        core = f'"{company}" {symbol} {en}'.strip()
        official = f"site:{domain} {core}" if domain else f"{core} annual report investor relations"
        rows.append({
            "Question": q,
            "Dimension ID": item["id"],
            "Dimension": item["label"],
            "Printed Pages": f"{item['pages'][0]}-{item['pages'][1]}",
            "Source Anchor": item["anchor"],
            "SSOT Dependency": item["ssot_dependency"],
            "Official Query": official,
            "Broad Query": f"{core} {vi}",
            "Research Boundary": RESEARCH_BOUNDARY,
        })
    return pd.DataFrame(rows, columns=PLAN_COLUMNS)


def source_grade_from_url(url: str, official_domain: str = "") -> str:
    raw = _text(url)
    if not raw:
        return "C — Context"
    try:
        host = (urlparse(raw if "://" in raw else f"https://{raw}").hostname or "").casefold()
    except Exception:
        host = ""
    company_host = _text(official_domain).casefold().replace("https://", "").replace("http://", "").strip("/")
    if company_host and (host == company_host or host.endswith("." + company_host)):
        return "A — Official"
    if any(host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_HOST_SUFFIXES):
        return "A — Official"
    if host:
        return "B — Independent"
    return "C — Context"


def match_dimensions(text: str, question: str | None = None) -> tuple[str, ...]:
    haystack = _tokens(_text(text))
    if not haystack:
        return ()
    matches: list[tuple[int, str]] = []
    for row in ch11.dimension_catalog():
        if question in QUESTION_ORDER and row["question"] != question:
            continue
        terms = set(dimension_terms(row["id"]))
        score = len(haystack & terms)
        if score:
            matches.append((score, row["id"]))
    matches.sort(key=lambda item: (-item[0], item[1]))
    return tuple(dim for _, dim in matches)


def candidate_id(record: dict[str, Any], dimension_id: str) -> str:
    seed = "|".join([
        dimension_id,
        _text(record.get("url") or record.get("source_url") or record.get("file")),
        _text(record.get("title")),
        _text(record.get("text") or record.get("snippet") or record.get("evidence")),
    ])
    return sha256(seed.encode("utf-8")).hexdigest()[:16]


def normalize_candidate(
    record: dict[str, Any],
    *,
    dimension_id: str,
    official_domain: str = "",
    data_origin: str = "Research Assistant",
) -> dict[str, Any]:
    index = _catalog_index()
    if dimension_id not in index:
        raise ValueError(f"Unknown Chapter 11 dimension: {dimension_id}")
    dim = index[dimension_id]
    url = _text(record.get("url") or record.get("source_url") or record.get("file"))
    evidence = _text(record.get("text") or record.get("snippet") or record.get("evidence"))
    return {
        "Select": False,
        "Candidate ID": candidate_id(record, dimension_id),
        "Question": dim["question"],
        "Dimension ID": dimension_id,
        "Dimension": dim["label"],
        "Direction": _text(record.get("direction")) or "Unknown",
        "Source Grade": _text(record.get("source_grade")) or source_grade_from_url(url, official_domain),
        "Source Family": _text(record.get("source_family")) or "Web / document research",
        "Source Title": _text(record.get("title")),
        "Source URL / File": url,
        "Source Date": _text(record.get("source_date") or record.get("date")),
        "As-of Date": _text(record.get("as_of_date")),
        "Evidence Text / Reference": evidence,
        "Data Origin": data_origin,
        "Status": "Candidate — analyst review required",
    }


def build_candidates(records: Iterable[dict[str, Any]], *, official_domain: str = "") -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        explicit_dim = _text(record.get("dimension_id"))
        question = _text(record.get("question"))
        text = " ".join([
            _text(record.get("title")),
            _text(record.get("text") or record.get("snippet") or record.get("evidence")),
        ])
        dims = (explicit_dim,) if explicit_dim else match_dimensions(
            text, question if question in QUESTION_ORDER else None
        )
        for dim in dims:
            if dim in _catalog_index():
                rows.append(normalize_candidate(record, dimension_id=dim, official_domain=official_domain))
    dedup = {row["Candidate ID"]: row for row in rows}
    return pd.DataFrame(list(dedup.values()), columns=CANDIDATE_COLUMNS)


def research_gaps(candidates: pd.DataFrame | None = None) -> pd.DataFrame:
    found: set[str] = set()
    if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Dimension ID" in candidates.columns:
        found = {str(x) for x in candidates["Dimension ID"].dropna().tolist()}
    rows = []
    for item in ch11.dimension_catalog():
        if item["id"] not in found:
            rows.append({
                "Question": item["question"],
                "Dimension ID": item["id"],
                "Research Gap": item["label"],
                "Materiality": "Analyst to assess",
                "Next Action": "Research / verify source evidence",
                "Status": "Open",
                "Analyst Note": "",
            })
    return pd.DataFrame(rows, columns=ch11.RESEARCH_GAP_COLUMNS)


def promote_selected_candidates(
    payload: dict[str, Any] | None,
    candidates: pd.DataFrame,
    selected_ids: Iterable[str],
) -> dict[str, Any]:
    """Append only analyst-selected candidates; never alter analyst conclusions/status fields."""
    base = ch11.normalize_payload(deepcopy(payload) if isinstance(payload, dict) else {})
    selected = {str(x) for x in selected_ids}
    if not selected or candidates is None or candidates.empty:
        return base
    existing = list(base.get("evidence", []))
    existing_ids = {str(row.get("Candidate ID", "")) for row in existing if isinstance(row, dict)}
    for _, row in candidates.iterrows():
        cid = str(row.get("Candidate ID", ""))
        if cid not in selected or cid in existing_ids:
            continue
        existing.append({
            "Question": row.get("Question", ""),
            "Dimension ID": row.get("Dimension ID", ""),
            "Dimension": row.get("Dimension", ""),
            "Observation / Claim": row.get("Evidence Text / Reference", ""),
            "Period / Date": row.get("Source Date", ""),
            "M&A Topic": "",
            "Source Grade": row.get("Source Grade", ""),
            "Source Title": row.get("Source Title", ""),
            "Source URL / File": row.get("Source URL / File", ""),
            "Source Date": row.get("Source Date", ""),
            "As-of Date": row.get("As-of Date", ""),
            "Evidence Text / Reference": row.get("Evidence Text / Reference", ""),
            "Direction": row.get("Direction", "Unknown"),
            "Status": "Promoted by analyst",
            "Analyst Note": "",
            "Candidate ID": cid,
        })
        existing_ids.add(cid)
    base["evidence"] = existing
    return base


def phase_summary() -> dict[str, Any]:
    return {
        "phase": "Chapter 11 Phase 11D Research Assistant V85",
        "chapter": ch11.CHAPTER_NUMBER,
        "question_range": ch11.SOURCE_QUESTION_RANGE,
        "dimensions": len(ch11.dimension_ids()),
        "research_plan_rows": len(research_plan("TEST")),
        "analyst_promotion_required": True,
        "automatic_ma_score": False,
        "automatic_acquisition_success_conclusion": False,
        "automatic_synergy_forecast": False,
        "automatic_investment_signal": False,
        "mos_or_research_gate_changed": False,
        "duplicate_financial_ssot_added": False,
        "boundary": RESEARCH_BOUNDARY,
    }


__all__ = [
    "CANDIDATE_COLUMNS", "PLAN_COLUMNS", "QUERY_TERMS", "RESEARCH_BOUNDARY", "build_candidates",
    "candidate_id", "dimension_terms", "match_dimensions", "normalize_candidate",
    "phase_summary", "promote_selected_candidates", "research_gaps", "research_plan",
    "source_grade_from_url",
]
