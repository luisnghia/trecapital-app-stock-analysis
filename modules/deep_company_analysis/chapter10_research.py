from __future__ import annotations

"""Chapter 10 Phase 10D — source research and Research Assistant bridge.

The module turns the source-locked Q53-Q57 / 34-dimension contract into deterministic
research plans and candidate-evidence records. It never converts search results into analyst
conclusions automatically. Promotion into the Chapter 10 workspace requires an explicit
selected candidate id supplied by the analyst/UI.
"""

from copy import deepcopy
from hashlib import sha256
from typing import Any, Iterable
from urllib.parse import urlparse
import re

import pandas as pd

import modules.deep_company_analysis.chapter10 as ch10


QUESTION_ORDER = ch10.QUESTION_KEYS
RESEARCH_BOUNDARY = (
    "Candidate evidence only; analyst verification and explicit promotion required. "
    "No growth score, growth forecast, valuation/MOS change, Research Gate change, or BUY/HOLD/SELL."
)

QUERY_TERMS: dict[str, tuple[str, str]] = {
    "Q53": (
        "mua lại sáp nhập tăng trưởng hữu cơ chi tiêu M&A dòng tiền hoạt động tích hợp nợ",
        "acquisitions M&A organic growth acquisition spend operating cash flow integration leverage",
    ),
    "Q54": (
        "động cơ tăng trưởng ban lãnh đạo áp lực doanh thu giá cổ phiếu ngoài ngành cốt lõi",
        "management motivation growth pressure revenue stock price non-core initiatives acquisitions",
    ),
    "Q55": (
        "tăng trưởng đơn vị biên lợi nhuận gộp biên hoạt động lợi nhuận trên đơn vị",
        "unit growth gross margin operating margin operating income per unit profitable growth",
    ),
    "Q56": (
        "triển vọng tăng trưởng runway thị trường xu hướng dài hạn R&D sản phẩm mới bão hòa",
        "future growth prospects runway market size secular trend R&D new products saturation market share",
    ),
    "Q57": (
        "tốc độ tăng trưởng kỷ luật tài trợ nội bộ vòng quay tiền mặt nhân sự hạ tầng địa điểm",
        "disciplined growth pace internal funding cash conversion cycle human capital infrastructure locations",
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
    return {row["id"]: row for row in ch10.dimension_catalog()}


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
    for item in ch10.dimension_catalog():
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
    for row in ch10.dimension_catalog():
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
        raise ValueError(f"Unknown Chapter 10 dimension: {dimension_id}")
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


def build_candidates(
    records: Iterable[dict[str, Any]],
    *,
    official_domain: str = "",
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        explicit_dim = _text(record.get("dimension_id"))
        question = _text(record.get("question"))
        text = " ".join([_text(record.get("title")), _text(record.get("text") or record.get("snippet") or record.get("evidence"))])
        dims = (explicit_dim,) if explicit_dim else match_dimensions(text, question if question in QUESTION_ORDER else None)
        for dim in dims:
            if dim in _catalog_index():
                rows.append(normalize_candidate(record, dimension_id=dim, official_domain=official_domain))
    dedup: dict[str, dict[str, Any]] = {row["Candidate ID"]: row for row in rows}
    return pd.DataFrame(list(dedup.values()), columns=CANDIDATE_COLUMNS)


def research_gaps(candidates: pd.DataFrame | None = None) -> pd.DataFrame:
    found = set()
    if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Dimension ID" in candidates.columns:
        found = {str(x) for x in candidates["Dimension ID"].dropna().tolist()}
    rows = []
    for item in ch10.dimension_catalog():
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
    return pd.DataFrame(rows, columns=ch10.RESEARCH_GAP_COLUMNS)


def promote_selected_candidates(
    payload: dict[str, Any] | None,
    candidates: pd.DataFrame,
    selected_ids: Iterable[str],
) -> dict[str, Any]:
    """Return a copied normalized workspace with explicitly selected candidates appended as evidence.

    This function does not alter question status, confidence, growth mode, dimension status, or
    analyst assessment. Selection is the analyst/UI authorization boundary.
    """
    base = ch10.normalize_payload(deepcopy(payload) if isinstance(payload, dict) else {})
    selected = {str(x) for x in selected_ids}
    if not selected or candidates is None or candidates.empty:
        return base
    existing = list(base.get("evidence", []))
    for _, row in candidates.iterrows():
        cid = str(row.get("Candidate ID", ""))
        if cid not in selected:
            continue
        existing.append({
            "Question": row.get("Question", ""),
            "Dimension ID": row.get("Dimension ID", ""),
            "Dimension": row.get("Dimension", ""),
            "Observation / Claim": row.get("Evidence Text / Reference", ""),
            "Period / Date": row.get("Source Date", ""),
            "Metric / Growth Driver": "",
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
    base["evidence"] = existing
    return base


def phase_summary() -> dict[str, Any]:
    return {
        "phase": "Chapter 10 Phase 10D Research Assistant V77",
        "chapter": ch10.CHAPTER_NUMBER,
        "question_range": ch10.SOURCE_QUESTION_RANGE,
        "dimensions": len(ch10.dimension_ids()),
        "research_plan_rows": len(research_plan("TEST")),
        "analyst_promotion_required": True,
        "automatic_growth_score": False,
        "automatic_growth_forecast": False,
        "automatic_investment_signal": False,
        "mos_or_research_gate_changed": False,
        "duplicate_financial_ssot_added": False,
        "boundary": RESEARCH_BOUNDARY,
    }
