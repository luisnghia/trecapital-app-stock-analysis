from __future__ import annotations

"""Chapter 8 Phase 8I — bounded deep retrieval from official company documents.

Phase 8H can leave source-locked dimensions open when search snippets do not expose the
relevant text. This module follows the company's registered official/IR domains more deeply,
opens bounded report/disclosure pages and PDFs, and extracts dimension-specific text windows.

Research boundary:
- Chapter 7 remains the manager identity/background SSOT.
- Trecapital canonical data remains the financial SSOT.
- only source-locked open Chapter 8 dimensions are targeted;
- candidates remain ``Candidate — analyst verify`` and are never auto-promoted;
- no analyst assessment/status/confidence is written;
- no management score, MOS/Research Gate, or BUY/HOLD/SELL is produced;
- Q46 keeps exactly five Shearn capital-allocation actions; context rows are not targets;
- Q47 requires explicit buyback/repurchase language; share-count decline alone is not proof.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urldefrag, urljoin, urlparse
import re

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS
import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter7_research import fetch_document_text
from modules.deep_company_analysis.chapter8_gap_engine import (
    BOUNDARY,
    QUESTION_DIMENSIONS,
    build_dimension_coverage,
    enhanced_research_gaps,
)
from modules.deep_company_analysis.chapter8_research import (
    ATTEMPT_COLUMNS,
    CANDIDATE_COLUMNS,
    direction_cue,
    evidence_quality_summary,
    source_grade_from_url,
)


TARGET_COLUMNS = [
    "Question",
    "Dimension Key",
    "Dimension",
    "Query Terms",
    "Next Action",
    "Source Locked",
    "Boundary",
]

DEEP_LINK_TERMS = (
    "annual report", "bao cao thuong nien", "báo cáo thường niên", "bctn",
    "investor", "investor relations", "quan he co dong", "quan hệ cổ đông", "co dong", "cổ đông",
    "disclosure", "cong bo thong tin", "công bố thông tin", "cbtt",
    "governance", "quan tri", "quản trị", "bao cao quan tri", "báo cáo quản trị",
    "sustainability", "phat trien ben vung", "phát triển bền vững", "esg",
    "human resource", "human capital", "nhan su", "nhân sự", "nguoi lao dong", "người lao động",
    "strategy", "chien luoc", "chiến lược", "business plan", "ke hoach", "kế hoạch",
    "agm", "dhdcd", "dai hoi", "đại hội", "nghi quyet", "nghị quyết", "resolution",
    "dividend", "co tuc", "cổ tức", "buyback", "repurchase", "treasury share", "co phieu quy", "cổ phiếu quỹ",
    "appointment", "bo nhiem", "bổ nhiệm", "remuneration", "thu lao", "thù lao", "esop",
    "cost", "chi phi", "chi phí", "restructuring", "tai cau truc", "tái cấu trúc",
)

Q47_EXPLICIT_TERMS = (
    "buyback", "share repurchase", "stock repurchase", "repurchase program", "repurchase authorization",
    "treasury shares", "mua lại cổ phiếu", "mua cổ phiếu quỹ", "cổ phiếu quỹ",
    "phương án mua lại", "giá mua lại", "hủy cổ phiếu quỹ", "huỷ cổ phiếu quỹ",
)

SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".css", ".js",
    ".mp4", ".mp3", ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx",
)


@dataclass
class OfficialDeepRetrievalResult:
    targets: pd.DataFrame
    source_attempts: pd.DataFrame
    documents: pd.DataFrame
    new_candidates: pd.DataFrame
    merged_candidates: pd.DataFrame
    before_coverage: pd.DataFrame
    after_coverage: pd.DataFrame
    remaining_gaps: pd.DataFrame
    quality: pd.DataFrame
    note: str


def _safe(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _same_domain(url: str, root_domain: str) -> bool:
    domain = _domain(url)
    return bool(
        domain
        and root_domain
        and (domain == root_domain or domain.endswith("." + root_domain) or root_domain.endswith("." + domain))
    )


def _candidate_id(*parts: Any) -> str:
    payload = "\x1f".join(_safe(x) for x in parts)
    return sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _year_candidate(text: str) -> str:
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", str(text or ""))
    return years[-1] if years else ""


def _manager_rows(manager_reference: pd.DataFrame | None) -> list[tuple[str, str]]:
    if not isinstance(manager_reference, pd.DataFrame) or manager_reference.empty:
        return []
    out: list[tuple[str, str]] = []
    for _, row in manager_reference.iterrows():
        manager = _safe(row.get("Manager"))
        if manager:
            out.append((_safe(row.get("Manager ID")), manager))
    return out


def _manager_match(text: str, manager_reference: pd.DataFrame | None) -> tuple[str, str]:
    low = _safe(text).casefold()
    for manager_id, manager in sorted(_manager_rows(manager_reference), key=lambda x: len(x[1]), reverse=True):
        if manager.casefold() in low:
            return manager_id, manager
    return "", ""


def _dimension(question: str, key: str):
    for item in QUESTION_DIMENSIONS.get(str(question), ()):
        if item.key == key:
            return item
    return None


def build_official_deep_targets(candidates: pd.DataFrame, *, max_targets: int = 48) -> pd.DataFrame:
    """Return open source-locked dimensions, round-robin across Q39-Q47."""
    max_targets = max(0, min(int(max_targets), 64))
    coverage = build_dimension_coverage(candidates)
    if coverage.empty or max_targets <= 0:
        return pd.DataFrame(columns=TARGET_COLUMNS)
    open_rows = coverage[
        coverage["Source Locked"].eq("Yes")
        & ~coverage["Coverage Status"].eq("Candidate coverage — analyst verify")
    ].copy()
    if open_rows.empty:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    buckets: dict[str, list[dict[str, Any]]] = {}
    for question in ch8.QUESTION_KEYS:
        qrows = open_rows[open_rows["Question"].astype(str).eq(question)].copy()
        qrows = qrows.sort_values(["Candidates", "Dimension Key"], ascending=[True, True])
        buckets[question] = qrows.to_dict("records")

    planned: list[dict[str, Any]] = []
    while len(planned) < max_targets and any(buckets.values()):
        for question in ch8.QUESTION_KEYS:
            if len(planned) >= max_targets:
                break
            if buckets.get(question):
                planned.append(buckets[question].pop(0))

    rows: list[dict[str, Any]] = []
    for row in planned:
        question = _safe(row.get("Question"))
        key = _safe(row.get("Dimension Key"))
        dim = _dimension(question, key)
        if dim is None or not dim.source_locked:
            continue
        rows.append({
            "Question": question,
            "Dimension Key": key,
            "Dimension": dim.label,
            "Query Terms": " | ".join(dim.terms[:8]),
            "Next Action": dim.next_action,
            "Source Locked": "Yes",
            "Boundary": BOUNDARY,
        })
    return pd.DataFrame(rows, columns=TARGET_COLUMNS)


def _target_terms(targets: pd.DataFrame) -> tuple[str, ...]:
    terms: list[str] = []
    for _, row in targets.iterrows():
        dim = _dimension(_safe(row.get("Question")), _safe(row.get("Dimension Key")))
        if dim is None:
            continue
        for term in dim.terms:
            clean = _safe(term)
            if clean and clean.casefold() not in {x.casefold() for x in terms}:
                terms.append(clean)
    return tuple(terms)


def _link_score(label: str, url: str, target_terms: Iterable[str]) -> int:
    text = _safe(f"{label} {url}").casefold()
    score = 0
    score += sum(4 for term in DEEP_LINK_TERMS if term.casefold() in text)
    score += sum(1 for term in target_terms if term.casefold() in text)
    path = url.lower().split("?")[0]
    if path.endswith(".pdf"):
        score += 8
    if any(year in text for year in ("2026", "2025", "2024", "2023")):
        score += 2
    return score


def _looks_document_or_index(label: str, url: str, target_terms: Iterable[str]) -> bool:
    path = url.lower().split("?")[0]
    if path.endswith(SKIP_EXTENSIONS):
        return False
    return _link_score(label, url, target_terms) > 0


def discover_official_document_pool(
    ticker: str,
    targets: pd.DataFrame,
    *,
    max_index_pages: int = 12,
    max_documents: int = 24,
    max_depth: int = 2,
    timeout_seconds: float = 4.5,
) -> tuple[list[dict[str, Any]], pd.DataFrame, str]:
    """Follow official/IR report indexes up to ``max_depth`` and retain relevant text/PDFs."""
    symbol = _safe(ticker).upper()
    roots = list(KNOWN_COMPANY_DOMAINS.get(symbol, []))
    if not roots:
        return [], pd.DataFrame(columns=ATTEMPT_COLUMNS), f"{symbol}: no registered company/IR root."

    max_index_pages = max(1, min(int(max_index_pages), 30))
    max_documents = max(1, min(int(max_documents), 50))
    max_depth = max(0, min(int(max_depth), 3))
    target_terms = _target_terms(targets)
    attempts: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    seen: set[str] = set()
    queued: set[str] = set()
    queue: list[tuple[int, int, str, str, str]] = []  # score, depth, url, label, root-domain

    for root in roots:
        root_url = urldefrag(str(root))[0]
        root_domain = _domain(root_url)
        if root_url and root_domain:
            queue.append((10_000, 0, root_url, root_url, root_domain))
            queued.add(root_url)

    index_pages = 0
    timeout = httpx.Timeout(timeout_seconds, connect=min(2.5, timeout_seconds))
    with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        while queue and index_pages < max_index_pages and len(documents) < max_documents:
            queue.sort(key=lambda row: (-row[0], row[1], row[2]))
            _, depth, url, label, root_domain = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            path = url.lower().split("?")[0]
            try:
                if path.endswith(".pdf"):
                    text, method = fetch_document_text(
                        url, timeout_seconds=timeout_seconds, max_pages=60, max_chars=220_000
                    )
                    attempts.append({
                        "URL": url,
                        "Domain": _domain(url),
                        "Status": "Fetched" if text else "Empty/failed",
                        "Method": f"Phase 8I deep PDF — {method}",
                        "Source Grade": source_grade_from_url(url, symbol),
                    })
                    if text:
                        documents.append({"url": url, "title": label or url, "text": text, "method": method, "depth": depth})
                    continue

                response = client.get(url)
                response.raise_for_status()
                content_type = _safe(response.headers.get("content-type")).lower()
                if "pdf" in content_type:
                    text, method = fetch_document_text(
                        url, timeout_seconds=timeout_seconds, max_pages=60, max_chars=220_000
                    )
                    attempts.append({
                        "URL": url,
                        "Domain": _domain(url),
                        "Status": "Fetched" if text else "Empty/failed",
                        "Method": f"Phase 8I deep PDF — {method}",
                        "Source Grade": source_grade_from_url(url, symbol),
                    })
                    if text:
                        documents.append({"url": url, "title": label or url, "text": text, "method": method, "depth": depth})
                    continue

                index_pages += 1
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "noscript", "svg"]):
                    tag.decompose()
                title = _safe(soup.title.get_text(" ", strip=True) if soup.title else label or url)
                text = _safe(soup.get_text(" ", strip=True))
                attempts.append({
                    "URL": url,
                    "Domain": _domain(url),
                    "Status": "Fetched",
                    "Method": f"Phase 8I HTML discovery depth={depth}",
                    "Source Grade": source_grade_from_url(url, symbol),
                })

                low = text.casefold()
                relevant_text = any(term.casefold() in low for term in target_terms)
                relevant_route = _link_score(title, url, target_terms) > 0
                if len(text) >= 160 and (depth == 0 or relevant_text or relevant_route):
                    documents.append({
                        "url": url,
                        "title": title,
                        "text": text[:220_000],
                        "method": f"HTML text extraction depth={depth}",
                        "depth": depth,
                    })
                    if len(documents) >= max_documents:
                        break

                if depth >= max_depth:
                    continue
                for anchor in soup.find_all("a", href=True):
                    anchor_label = _safe(anchor.get_text(" ", strip=True))
                    absolute = urldefrag(urljoin(url, anchor.get("href", "")))[0]
                    if not absolute.startswith(("http://", "https://")):
                        continue
                    if not _same_domain(absolute, root_domain):
                        continue
                    if absolute in seen or absolute in queued:
                        continue
                    if not _looks_document_or_index(anchor_label, absolute, target_terms):
                        continue
                    score = _link_score(anchor_label, absolute, target_terms)
                    queue.append((score, depth + 1, absolute, anchor_label or absolute, root_domain))
                    queued.add(absolute)
            except Exception as exc:
                attempts.append({
                    "URL": url,
                    "Domain": _domain(url),
                    "Status": f"Fetch failed: {exc}",
                    "Method": f"Phase 8I deep retrieval depth={depth}",
                    "Source Grade": source_grade_from_url(url, symbol),
                })

    attempts_df = pd.DataFrame(attempts, columns=ATTEMPT_COLUMNS)
    note = (
        f"{symbol}: Phase 8I visited {index_pages} HTML index/report page(s), attempted {len(attempts_df)} official URL(s), "
        f"retained {len(documents)} text document(s), max_depth={max_depth}."
    )
    return documents, attempts_df, note


def _windows_for_dimension(
    text: str,
    terms: Iterable[str],
    *,
    window: int = 650,
    max_windows: int = 2,
) -> list[str]:
    clean = _safe(text)
    if not clean:
        return []
    low = clean.casefold()
    positions: list[int] = []
    for term in terms:
        needle = _safe(term).casefold()
        start = 0
        while needle and len(positions) < 80:
            pos = low.find(needle, start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + max(1, len(needle))
    out: list[str] = []
    for pos in sorted(set(positions)):
        snippet = _safe(clean[max(0, pos - window): min(len(clean), pos + window)])
        if snippet and snippet not in out:
            out.append(snippet)
        if len(out) >= max_windows:
            break
    return out


def documents_to_gap_candidates(
    documents: list[dict[str, Any]],
    ticker: str,
    targets: pd.DataFrame,
    manager_reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Extract direct official-text candidate windows for only the planned open dimensions."""
    rows: list[dict[str, Any]] = []
    symbol = _safe(ticker).upper()
    if not isinstance(targets, pd.DataFrame) or targets.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)

    for _, target in targets.iterrows():
        question = _safe(target.get("Question"))
        key = _safe(target.get("Dimension Key"))
        dim = _dimension(question, key)
        if dim is None or not dim.source_locked:
            continue
        for document in documents or []:
            text = _safe(document.get("text"))
            url = _safe(document.get("url"))
            if not text or not url:
                continue
            low = text.casefold()
            if not any(term.casefold() in low for term in dim.terms):
                continue
            title = _safe(document.get("title")) or url
            method = _safe(document.get("method")) or "official deep retrieval"
            for idx, snippet in enumerate(_windows_for_dimension(text, dim.terms, max_windows=2)):
                snippet_low = snippet.casefold()
                if question == "Q47" and not any(term.casefold() in snippet_low for term in Q47_EXPLICIT_TERMS):
                    continue
                manager_id, manager = _manager_match(snippet, manager_reference)
                rows.append({
                    "Select": False,
                    "Candidate ID": _candidate_id(question, key, manager_id, url, snippet, idx),
                    "Question": question,
                    "Manager ID": manager_id,
                    "Manager": manager,
                    "Subtopic": dim.label,
                    "Direction": direction_cue(snippet),
                    "Source Grade": source_grade_from_url(url, symbol),
                    "Explicitness": "Deep official source text — analyst verify",
                    "Source Title": title[:240],
                    "Source URL / File": url,
                    "Source Date": "",
                    "As-of Date": _year_candidate(f"{title} {url} {snippet}"),
                    "Evidence Text / Reference": snippet[:1200],
                    "Source Method": f"Phase 8I official deep retrieval — {key} — {method}",
                    "Data Origin": "Direct official/company source text — analyst verification required",
                    "Status": "Candidate — analyst verify",
                })
    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)


def _merge_candidates(existing: pd.DataFrame, new_candidates: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    left = existing.copy() if isinstance(existing, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
    right = new_candidates.copy() if isinstance(new_candidates, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
    for frame in (left, right):
        for column in CANDIDATE_COLUMNS:
            if column not in frame.columns:
                frame[column] = None
    before = set(left.get("Candidate ID", pd.Series(dtype="object")).fillna("").astype(str))
    merged = pd.concat([left[CANDIDATE_COLUMNS], right[CANDIDATE_COLUMNS]], ignore_index=True)
    if not merged.empty:
        merged = merged.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)
    after = set(merged.get("Candidate ID", pd.Series(dtype="object")).fillna("").astype(str))
    return merged, len(after - before)


def _open_count(coverage: pd.DataFrame) -> int:
    if not isinstance(coverage, pd.DataFrame) or coverage.empty:
        return 0
    return int((coverage["Source Locked"].eq("Yes") & ~coverage["Coverage Status"].eq("Candidate coverage — analyst verify")).sum())


class OfficialDeepRetrievalAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def search(
        self,
        ticker: str,
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        max_targets: int = 48,
        max_index_pages: int = 12,
        max_documents: int = 24,
        max_depth: int = 2,
    ) -> OfficialDeepRetrievalResult:
        before = build_dimension_coverage(existing_candidates)
        targets = build_official_deep_targets(existing_candidates, max_targets=max_targets)
        documents, attempts, discovery_note = discover_official_document_pool(
            ticker,
            targets,
            max_index_pages=max_index_pages,
            max_documents=max_documents,
            max_depth=max_depth,
        )
        new_candidates = documents_to_gap_candidates(documents, ticker, targets, manager_reference)
        merged, added = _merge_candidates(existing_candidates, new_candidates)
        after = build_dimension_coverage(merged)
        remaining = enhanced_research_gaps(merged, manager_reference)
        quality = evidence_quality_summary(merged)
        document_table = pd.DataFrame([
            {
                "URL": _safe(doc.get("url")),
                "Title": _safe(doc.get("title")),
                "Method": _safe(doc.get("method")),
                "Depth": doc.get("depth", ""),
                "Text chars": len(_safe(doc.get("text"))),
            }
            for doc in documents
        ])
        note = (
            f"{discovery_note} Phase 8I targeted {len(targets)} open source-locked dimension(s); "
            f"added {added} unique candidate(s); open dimensions {_open_count(before)} -> {_open_count(after)}. "
            "Candidates still require analyst verification/promotion; no management score or investment signal is produced."
        )
        return OfficialDeepRetrievalResult(
            targets=targets,
            source_attempts=attempts,
            documents=document_table,
            new_candidates=new_candidates,
            merged_candidates=merged,
            before_coverage=before,
            after_coverage=after,
            remaining_gaps=remaining,
            quality=quality,
            note=note,
        )


__all__ = [
    "OfficialDeepRetrievalAgent",
    "OfficialDeepRetrievalResult",
    "build_official_deep_targets",
    "discover_official_document_pool",
    "documents_to_gap_candidates",
]
