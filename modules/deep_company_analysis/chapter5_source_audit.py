from __future__ import annotations

"""Source registry and retrieval-audit helpers for Chapter 5 Phase 5C.

This module contains no analyst judgement.  It only classifies where a source came from,
normalizes source-attempt logs, and preserves failed retrievals so missing documents cannot
silently disappear from the Chapter-5 research trail.
"""

from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import json

import pandas as pd

from adapters.module2_web_research import KNOWN_COMPANY_DOMAINS, WebEvidenceAgent


REGULATORY_DOMAINS = (
    "hsx.vn",
    "hose.vn",
    "hnx.vn",
    "ssc.gov.vn",
    "congbothongtin.ssc.gov.vn",
)

SOURCE_ATTEMPT_COLUMNS = [
    "Channel",
    "Focus",
    "Kind",
    "Label",
    "URL / Path",
    "Domain",
    "Success",
    "Status",
    "Rows",
    "Error / Reason",
]


def domain_of(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def company_domains(ticker: str) -> tuple[str, ...]:
    out: list[str] = []
    for url in KNOWN_COMPANY_DOMAINS.get(str(ticker or "").upper().strip(), []):
        domain = domain_of(url)
        if domain and domain not in out:
            out.append(domain)
    return tuple(out)


def is_company_domain(ticker: str, url: str) -> bool:
    domain = domain_of(url)
    return bool(domain) and any(domain == base or domain.endswith("." + base) for base in company_domains(ticker))


def is_regulatory_domain(url: str) -> bool:
    domain = domain_of(url)
    return bool(domain) and any(domain == base or domain.endswith("." + base) for base in REGULATORY_DOMAINS)


def official_search_domain(ticker: str) -> str:
    """Return the best first-party domain for a source-first search, if registered."""
    domains = company_domains(ticker)
    return domains[0] if domains else ""


def registered_source_catalog(
    ticker: str,
    official_pages: dict[str, tuple[tuple[str, str], ...]] | dict[str, Any],
    official_pdfs: dict[str, tuple[tuple[str, str], ...]] | dict[str, Any],
) -> pd.DataFrame:
    """Build a deduplicated source registry visible in the Phase-5C audit trail."""
    safe = str(ticker or "").upper().strip()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(kind: str, label: str, url: str, origin: str) -> None:
        clean_url = str(url or "").strip()
        if not clean_url or clean_url in seen:
            return
        seen.add(clean_url)
        rows.append({
            "Ticker": safe,
            "Kind": kind,
            "Label": str(label or ""),
            "URL": clean_url,
            "Domain": domain_of(clean_url),
            "Source Grade": "A — Company/Official disclosure",
            "Registry Origin": origin,
        })

    for label, url in official_pages.get(safe, ()):
        add("Official HTML", label, url, "Chapter 5/Chapter 2 official registry")
    for label, url in official_pdfs.get(safe, ()):
        add("Official PDF", label, url, "Chapter 5/Chapter 2 official registry")
    for url in KNOWN_COMPANY_DOMAINS.get(safe, []):
        add("Company IR root", f"{safe} — registered company/IR root", url, "Trecapital known-company registry")

    return pd.DataFrame(rows, columns=[
        "Ticker", "Kind", "Label", "URL", "Domain", "Source Grade", "Registry Origin",
    ])


def annotate_search_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Promote only known company/regulatory domains to source grade A metadata.

    A search snippet remains a candidate and still requires analyst verification; this helper only
    fixes source provenance so a first-party company domain is not mislabeled as a generic web source.
    """
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    out = frame.copy()
    if "Nguồn/URL" not in out.columns:
        return out
    if "Nhóm thông tin" not in out.columns:
        out["Nhóm thông tin"] = ""
    if "_SourceMethod" not in out.columns:
        out["_SourceMethod"] = "Search snippet"

    for idx, url in out["Nguồn/URL"].astype(str).items():
        if is_company_domain(ticker, url):
            out.at[idx, "Nhóm thông tin"] = "Nguồn doanh nghiệp/IR"
            out.at[idx, "_SourceMethod"] = "Official-domain search snippet — analyst verify"
        elif is_regulatory_domain(url):
            out.at[idx, "Nhóm thông tin"] = "Nguồn công bố chính thức"
            out.at[idx, "_SourceMethod"] = "Official-regulatory search snippet — analyst verify"
    return out


def _errors_from_query_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for item in payload.get("errors") or []:
        if isinstance(item, dict):
            value = str(item.get("error") or "").strip()
        else:
            value = str(item or "").strip()
        if value:
            errors.append(value)
    fallback = payload.get("fallback_bing")
    if isinstance(fallback, dict):
        for item in fallback.get("errors") or []:
            if isinstance(item, dict):
                value = str(item.get("error") or "").strip()
            else:
                value = str(item or "").strip()
            if value:
                errors.append(value)
    return errors


def summarize_search_raw_log(raw_path: str | Path, focus: str) -> dict[str, Any]:
    """Summarize the underlying web-search JSON and keep search failures visible."""
    path = Path(raw_path) if raw_path else Path()
    base = {
        "channel": "search",
        "focus": str(focus or ""),
        "kind": "Web search",
        "label": f"{focus} focused search",
        "url": "",
        "success": False,
        "status": "No raw search log",
        "rows": 0,
        "error": "",
        "raw_path": str(raw_path or ""),
    }
    if not raw_path or not path.exists():
        base["error"] = "Raw search log is unavailable"
        return base
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        base["status"] = "Raw search log unreadable"
        base["error"] = str(exc)[:300]
        return base

    queries = payload.get("queries") or []
    item_count = 0
    errors: list[str] = []
    statuses: list[str] = []
    for query_payload in queries:
        if not isinstance(query_payload, dict):
            continue
        primary_items = query_payload.get("items") or []
        fallback = query_payload.get("fallback_bing") if isinstance(query_payload.get("fallback_bing"), dict) else {}
        fallback_items = fallback.get("items") or [] if isinstance(fallback, dict) else []
        item_count += len(primary_items) + len(fallback_items)
        errors.extend(_errors_from_query_payload(query_payload))
        for status in query_payload.get("status_codes") or []:
            if isinstance(status, dict) and status.get("status_code") is not None:
                statuses.append(str(status.get("status_code")))
        if isinstance(fallback, dict):
            for status in fallback.get("status_codes") or []:
                if isinstance(status, dict) and status.get("status_code") is not None:
                    statuses.append(str(status.get("status_code")))

    base["rows"] = int(item_count)
    base["success"] = item_count > 0
    base["status"] = "Search returned candidates" if item_count > 0 else "Search returned no candidates"
    if statuses:
        base["status"] += f"; HTTP={','.join(dict.fromkeys(statuses))}"
    if errors:
        base["error"] = " | ".join(dict.fromkeys(errors))[:600]
    elif item_count == 0:
        base["error"] = "No usable search-engine candidate returned; direct official sources may still succeed"
    return base


def source_attempt_table(audit: dict[str, Any] | None) -> pd.DataFrame:
    """Normalize source-attempt audit records, preserving both successes and failures."""
    audit = audit or {}
    attempts = audit.get("attempts") or []
    rows: list[dict[str, Any]] = []
    for item in attempts:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("raw_path") or "")
        rows.append({
            "Channel": str(item.get("channel") or ""),
            "Focus": str(item.get("focus") or ""),
            "Kind": str(item.get("kind") or ""),
            "Label": str(item.get("label") or ""),
            "URL / Path": url,
            "Domain": domain_of(str(item.get("url") or "")),
            "Success": bool(item.get("success")),
            "Status": str(item.get("status") or ""),
            "Rows": int(item.get("rows") or 0),
            "Error / Reason": str(item.get("error") or ""),
        })
    return pd.DataFrame(rows, columns=SOURCE_ATTEMPT_COLUMNS)


def failed_source_attempts(audit: dict[str, Any] | None) -> pd.DataFrame:
    frame = source_attempt_table(audit)
    if frame.empty:
        return frame
    return frame[~frame["Success"].astype(bool)].reset_index(drop=True)


def prioritize_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    """Put A sources first without changing evidence content or analyst judgement."""
    if not isinstance(candidates, pd.DataFrame) or candidates.empty:
        return candidates.copy() if isinstance(candidates, pd.DataFrame) else pd.DataFrame()
    out = candidates.copy()
    grade = out.get("Evidence Quality", pd.Series("", index=out.index)).astype(str)
    out["_source_rank"] = grade.map(lambda x: 0 if x.startswith("A —") else 1 if x.startswith("B —") else 2)
    q_order = {f"Q{n}": n for n in range(21, 27)}
    out["_question_rank"] = out.get("Question", pd.Series("", index=out.index)).map(q_order).fillna(99)
    out = out.sort_values(["_question_rank", "_source_rank"], kind="stable")
    return out.drop(columns=["_source_rank", "_question_rank"]).reset_index(drop=True)
