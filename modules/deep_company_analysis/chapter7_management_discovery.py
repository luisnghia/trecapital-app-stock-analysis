from __future__ import annotations

"""Chapter 7 management-target discovery hotfix.

The helper discovers *candidate* senior-manager identities and official management documents.
It never writes to the analyst Management Profile and never classifies OO/LT/HH, Lion/Hyena,
management quality, insider conviction, MOS or BUY/HOLD/SELL.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
import re

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS, WebEvidenceAgent


MANAGER_CANDIDATE_COLUMNS = [
    "Select",
    "Manager",
    "Role Raw",
    "Role Normalized",
    "As-of Date",
    "Source Title",
    "Source URL / File",
    "Source Grade",
    "Evidence Text / Reference",
    "Status",
]

ROLE_RULES: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("Chairman", ("chủ tịch hđqt", "chủ tịch hội đồng quản trị", "chairman"), 100),
    ("CEO", ("tổng giám đốc", "chief executive officer", " ceo "), 98),
    ("Vice Chairman", ("phó chủ tịch", "vice chairman"), 94),
    ("CFO", ("giám đốc tài chính", "chief financial officer", " cfo "), 90),
    ("COO", ("giám đốc vận hành", "chief operating officer", " coo "), 89),
    ("Deputy CEO", ("phó tổng giám đốc", "deputy general director", "deputy ceo"), 86),
    ("Chief Accountant", ("kế toán trưởng", "chief accountant"), 82),
    ("Independent Director", ("thành viên hđqt độc lập", "thành viên hội đồng quản trị độc lập", "independent director"), 78),
    ("Board Director", ("thành viên hđqt", "ủy viên hđqt", "thành viên hội đồng quản trị", "board member", "director"), 72),
)

LINK_TERMS = (
    "ban lanh dao", "ban-lanh-dao", "ban điều hành", "ban dieu hanh", "management", "leadership",
    "hoi dong quan tri", "hội đồng quản trị", "hdqt", "nhan su", "nhân sự", "bo nhiem", "bổ nhiệm",
    "mien nhiem", "miễn nhiệm", "bao cao thuong nien", "báo cáo thường niên", "annual report", "bctn",
    "bao cao quan tri", "báo cáo quản trị", "corporate governance", "cbtt", "cong bo thong tin",
    "công bố thông tin", "thu lao", "thù lao", "esop", "giao dich", "giao dịch", "nguoi noi bo", "người nội bộ",
)

ROLE_CUE = "|".join(sorted({re.escape(term) for _, terms, _ in ROLE_RULES for term in terms}, key=len, reverse=True))
PERSON_PATTERN = re.compile(
    rf"(?:Ông|Bà|Mr\.?|Ms\.?)\s+"
    rf"([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\.-]+"
    rf"(?:\s+[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\.-]+){{1,4}}?)"
    rf"(?=\s+(?:{ROLE_CUE}|\(|,|;|\.|từ ngày|giữ chức|được bổ nhiệm|được miễn nhiệm)|$)",
    flags=re.IGNORECASE,
)


@dataclass
class ManagementDiscoveryResult:
    managers: pd.DataFrame
    documents: list[dict[str, Any]]
    target_names: list[str]
    note: str


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _same_domain(url: str, domain: str) -> bool:
    d = _domain(url)
    return bool(d and domain and (d == domain or d.endswith("." + domain) or domain.endswith("." + d)))


def _year(text: str) -> str:
    values = re.findall(r"\b(20\d{2}|19\d{2})\b", str(text or ""))
    return max(values) if values else ""


def _role_from_context(context: str) -> tuple[str, str, int]:
    low = f" {_clean_text(context).casefold()} "
    best = ("", "", 0)
    for normalized, terms, priority in ROLE_RULES:
        for term in terms:
            pos = low.find(term.casefold())
            if pos >= 0 and priority > best[2]:
                best = (term, normalized, priority)
    return best


def _candidate_name(raw_name: str) -> str:
    name = _clean_text(raw_name).strip(" ,.;:-")
    # Keep Vietnamese personal names; reject obvious role fragments accidentally captured by OCR/PDF text.
    banned = {"chủ", "tịch", "tổng", "giám", "đốc", "phó", "thành", "viên", "hội", "đồng", "quản", "trị", "kế", "toán", "trưởng"}
    tokens = name.split()
    while tokens and tokens[-1].casefold() in banned:
        tokens.pop()
    return " ".join(tokens)


def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5) -> pd.DataFrame:
    """Extract person/role candidates from already-fetched official document text.

    The output is a discovery layer only. Conflicting roles and historical episodes are preserved.
    """
    rows: list[dict[str, Any]] = []
    for document in documents:
        text = _clean_text(document.get("text"))
        if not text:
            continue
        source_url = _clean_text(document.get("url"))
        source_title = _clean_text(document.get("title")) or source_url
        as_of = _year(f"{source_title} {source_url} {text[:3000]}")
        for match in PERSON_PATTERN.finditer(text):
            manager = _candidate_name(match.group(1))
            if len(manager.split()) < 2:
                continue
            start = max(0, match.start() - 120)
            end = min(len(text), match.end() + 220)
            context = _clean_text(text[start:end])
            role_raw, role_norm, priority = _role_from_context(context)
            if not role_norm:
                continue
            rows.append({
                "Select": False,
                "Manager": manager,
                "Role Raw": role_raw,
                "Role Normalized": role_norm,
                "As-of Date": as_of,
                "Source Title": source_title[:240],
                "Source URL / File": source_url,
                "Source Grade": "A — Company/Official disclosure",
                "Evidence Text / Reference": context[:900],
                "Status": "Discovered candidate — analyst verify",
                "_priority": priority,
            })
    if not rows:
        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)
    frame = pd.DataFrame(rows)
    frame["_year_num"] = pd.to_numeric(frame["As-of Date"], errors="coerce").fillna(0)
    frame = frame.sort_values(["_year_num", "_priority"], ascending=[False, False])
    frame = frame.drop_duplicates(subset=["Manager", "Role Normalized", "As-of Date", "Source URL / File"], keep="first")
    return frame[MANAGER_CANDIDATE_COLUMNS].reset_index(drop=True)


def choose_research_targets(managers: pd.DataFrame, max_targets: int = 5) -> list[str]:
    if not isinstance(managers, pd.DataFrame) or managers.empty:
        return []
    ranked = managers.copy()
    priority_map = {normalized: priority for normalized, _, priority in ROLE_RULES}
    ranked["_priority"] = ranked["Role Normalized"].map(priority_map).fillna(0)
    ranked["_year"] = pd.to_numeric(ranked["As-of Date"], errors="coerce").fillna(0)
    ranked = ranked.sort_values(["_year", "_priority"], ascending=[False, False])
    names: list[str] = []
    for value in ranked["Manager"].astype(str):
        name = _clean_text(value)
        if name and name not in names:
            names.append(name)
        if len(names) >= max_targets:
            break
    return names


def _fetch_text(client: httpx.Client, url: str, max_pages: int = 120, max_chars: int = 420_000) -> tuple[str, str, str, list[tuple[str, str]]]:
    response = client.get(url)
    response.raise_for_status()
    content = response.content
    ctype = _clean_text(response.headers.get("content-type")).lower()
    final_url = str(response.url)
    is_pdf = "pdf" in ctype or final_url.lower().split("?")[0].endswith(".pdf") or content[:4] == b"%PDF"
    if is_pdf:
        reader = PdfReader(BytesIO(content))
        parts: list[str] = []
        total = 0
        for page in reader.pages[:max_pages]:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            if page_text:
                parts.append(page_text)
                total += len(page_text)
            if total >= max_chars:
                break
        return _clean_text(" ".join(parts))[:max_chars], "PDF text extraction (no OCR)", final_url, []
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    links: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(final_url, anchor.get("href", ""))
        label = _clean_text(anchor.get_text(" ", strip=True))
        if href.startswith(("http://", "https://")):
            links.append((label, href))
    return _clean_text(soup.get_text(" ", strip=True))[:max_chars], "HTML text extraction", final_url, links


def _link_score(label: str, url: str) -> int:
    text = f"{label} {url}".casefold()
    score = sum(4 for term in LINK_TERMS if term.casefold() in text)
    year = _year(text)
    if year:
        score += max(0, int(year) - 2020)
    if url.lower().endswith(".pdf"):
        score += 2
    return score


def discover_management_candidates(
    ticker: str,
    company_name: str = "",
    *,
    max_documents: int = 10,
    max_targets: int = 5,
    timeout_seconds: float = 8.0,
) -> ManagementDiscoveryResult:
    """Crawl known company/IR sources and discover candidate senior managers.

    Only same-domain company documents are crawled. The function does not confirm identities or
    mutate Chapter-7 analyst records.
    """
    safe = _clean_text(ticker).upper()
    seeds = list(KNOWN_COMPANY_DOMAINS.get(safe, []))
    if not seeds:
        return ManagementDiscoveryResult(
            pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS), [], [],
            "No known company/IR domain configured; manager discovery skipped.",
        )

    documents: list[dict[str, Any]] = []
    seen: set[str] = set()
    candidate_links: list[tuple[int, str, str]] = []
    errors: list[str] = []
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(timeout_seconds, connect=min(3.0, timeout_seconds)), follow_redirects=True) as client:
        for seed in seeds:
            try:
                text, method, final_url, links = _fetch_text(client, seed, max_pages=30, max_chars=180_000)
                seen.add(final_url)
                documents.append({"title": f"{safe} official/IR seed", "url": final_url, "text": text, "method": method})
                domain = _domain(final_url)
                for label, href in links:
                    if _same_domain(href, domain):
                        score = _link_score(label, href)
                        if score > 0:
                            candidate_links.append((score, label, href))
            except Exception as exc:
                errors.append(f"seed {seed}: {exc}")

        # Prefer current official disclosures/annual reports and management pages.
        candidate_links = sorted(candidate_links, key=lambda x: x[0], reverse=True)
        for _, label, href in candidate_links:
            if len(documents) >= max_documents:
                break
            if href in seen:
                continue
            seen.add(href)
            try:
                text, method, final_url, _ = _fetch_text(client, href)
                if len(text) < 80:
                    continue
                documents.append({
                    "title": label or f"{safe} official management disclosure",
                    "url": final_url,
                    "text": text,
                    "method": method,
                })
            except Exception as exc:
                errors.append(f"document {href}: {exc}")

    managers = extract_management_candidates_from_documents(documents, max_targets=max_targets)
    targets = choose_research_targets(managers, max_targets=max_targets)
    note = f"Crawled {len(documents)} official/company documents; discovered {len(managers)} manager-role candidates; research targets={len(targets)}."
    if errors:
        note += " Some sources failed: " + " | ".join(errors[:3])
    return ManagementDiscoveryResult(managers, documents, targets, note)


__all__ = [
    "MANAGER_CANDIDATE_COLUMNS",
    "ManagementDiscoveryResult",
    "extract_management_candidates_from_documents",
    "choose_research_targets",
    "discover_management_candidates",
]
