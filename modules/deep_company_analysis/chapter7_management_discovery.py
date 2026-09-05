from __future__ import annotations

"""Chapter 7 management-target discovery hotfix.

Discovers candidate senior-manager identities and official management documents.
Discovered rows are research targets only: this module never writes analyst Management Profile,
never confirms current office, and never classifies OO/LT/HH, Lion/Hyena, management quality,
insider conviction, MOS or BUY/HOLD/SELL.
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Any
from urllib.parse import urljoin, urlparse, quote_plus
import re

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS


MANAGER_CANDIDATE_COLUMNS = [
    "Select", "Manager", "Role Raw", "Role Normalized", "As-of Date",
    "Source Title", "Source URL / File", "Source Grade",
    "Evidence Text / Reference", "Status",
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
    "ban lanh dao", "ban-lanh-dao", "ban lãnh đạo", "ban điều hành", "ban dieu hanh", "management", "leadership",
    "hoi dong quan tri", "hội đồng quản trị", "hdqt", "nhan su", "nhân sự", "bo nhiem", "bổ nhiệm",
    "mien nhiem", "miễn nhiệm", "bao cao thuong nien", "báo cáo thường niên", "annual report", "bctn",
    "bao cao quan tri", "báo cáo quản trị", "corporate governance", "cbtt", "cong bo thong tin", "công bố thông tin",
    "bao cao tai chinh", "báo cáo tài chính", "bctc", "financial statement", "kiem toan", "kiểm toán", "soat xet", "soát xét",
    "thu lao", "thù lao", "esop", "giao dich", "giao dịch", "nguoi noi bo", "người nội bộ",
    "ke toan truong", "kế toán trưởng", "tong giam doc", "tổng giám đốc", "chu tich", "chủ tịch",
)

# Name extraction intentionally does not require the role to be adjacent. Official PDF table extraction
# often returns a column of names followed by a column of roles. Role is therefore a separately verified field.
PERSON_NAME_PATTERN = re.compile(
    r"(?<![A-Za-zÀ-ỹĐđ])(?:Ông|Bà|Mr\.?|Ms\.?)\s+"
    r"([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\.-]+"
    r"(?:\s+[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\.-]+){1,5})",
    flags=re.IGNORECASE,
)

NOISE_NAME_TOKENS = {
    "báo", "thay", "đổi", "nhân", "sự", "qua", "bầu", "nghị", "quyết", "thông", "tin", "công", "bố",
    "xem", "thêm", "họp", "đại", "hội", "đồng", "quản", "trị", "ty", "tập", "đoàn", "chủ", "tịch",
    "tổng", "giám", "đốc", "phó", "thành", "viên", "kế", "toán", "trưởng", "điều", "lệ", "bổ", "nhiệm",
    "ông", "bà", "mr", "ms", "ủy", "uỷ", "ban", "kiểm", "soát",
}


@dataclass
class ManagementDiscoveryResult:
    managers: pd.DataFrame
    documents: list[dict[str, Any]]
    target_names: list[str]
    note: str


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _preserve_lines(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[\t ]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


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
            needle = term.casefold().strip()
            if needle and needle in low and priority > best[2]:
                best = (term.strip(), normalized, priority)
    return best


def _candidate_name(raw_name: str) -> str:
    tokens = [t.strip(" ,.;:()-") for t in _clean_text(raw_name).split() if t.strip(" ,.;:()-")]
    kept: list[str] = []
    for token in tokens:
        folded = token.casefold().rstrip(".")
        if folded in NOISE_NAME_TOKENS:
            break
        if not re.fullmatch(r"[A-Za-zÀ-ỹĐđ'\.-]+", token):
            break
        kept.append(token)
        if len(kept) >= 5:
            break
    if not (2 <= len(kept) <= 5):
        return ""
    # Reject all-uppercase menu/headline fragments unless they have a common Vietnamese surname-like length/name shape.
    name = " ".join(kept)
    if all(t.isupper() for t in kept) and any(t.casefold() in NOISE_NAME_TOKENS for t in kept):
        return ""
    return name


def _nearest_role(raw_text: str, start: int, end: int) -> tuple[str, str, int]:
    """Find a role only in the same local person segment; do not cross into another person row."""
    after_raw = raw_text[end:min(len(raw_text), end + 180)]
    next_person = re.search(r"(?<![A-Za-zÀ-ỹĐđ])(?:Ông|Bà|Mr\.?|Ms\.?)\s+", after_raw, flags=re.I)
    if next_person:
        after_raw = after_raw[:next_person.start()]
    role = _role_from_context(after_raw)
    if role[1]:
        return role

    before_raw = raw_text[max(0, start - 140):start]
    prev = list(re.finditer(r"(?<![A-Za-zÀ-ỹĐđ])(?:Ông|Bà|Mr\.?|Ms\.?)\s+", before_raw, flags=re.I))
    if prev:
        before_raw = before_raw[prev[-1].end():]
    return _role_from_context(before_raw)


def _line_role_candidates(raw_text: str) -> dict[str, tuple[str, str, int]]:
    """Use preserved HTML/PDF line layout for common `person | role` and two-line patterns."""
    lines = [line for line in _preserve_lines(raw_text).split("\n") if line]
    mapping: dict[str, tuple[str, str, int]] = {}
    for idx, line in enumerate(lines):
        for match in PERSON_NAME_PATTERN.finditer(line):
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            candidates = [line[match.end():]]
            # Only consult next lines until another honorific appears; avoids assigning next person's role.
            for j in range(idx + 1, min(len(lines), idx + 3)):
                if re.search(r"(?<![A-Za-zÀ-ỹĐđ])(?:Ông|Bà|Mr\.?|Ms\.?)\s+", lines[j], flags=re.I):
                    break
                candidates.append(lines[j])
            role = _role_from_context(" ".join(candidates))
            if role[1] and role[2] > mapping.get(manager, ("", "", 0))[2]:
                mapping[manager] = role
    return mapping


def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5) -> pd.DataFrame:
    """Extract candidate identities and, when locally supported, roles from official text.

    `Unknown` role is deliberately allowed: a reliably named manager from a management document is
    still useful as a research target. The role stays Unknown until an adjacent/line-local source supports it.
    """
    rows: list[dict[str, Any]] = []
    for document in documents:
        raw_text = _preserve_lines(document.get("text"))
        plain = _clean_text(raw_text)
        if not plain:
            continue
        source_url = _clean_text(document.get("url"))
        source_title = _clean_text(document.get("title")) or source_url
        as_of = _year(f"{source_title} {source_url} {plain[:5000]}")
        line_roles = _line_role_candidates(raw_text)
        for match in PERSON_NAME_PATTERN.finditer(plain):
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            role_raw, role_norm, priority = line_roles.get(manager, ("", "", 0))
            if not role_norm:
                role_raw, role_norm, priority = _nearest_role(plain, match.start(), match.end())
            if not role_norm:
                role_raw, role_norm, priority = "", "Unknown", 1
            context = _clean_text(plain[max(0, match.start() - 140):min(len(plain), match.end() + 240)])
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
    ranked["_priority"] = ranked["Role Normalized"].map(priority_map).fillna(1)
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
                try:
                    page_text = page.extract_text(extraction_mode="layout") or ""
                except TypeError:
                    page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            if page_text:
                parts.append(page_text)
                total += len(page_text)
            if total >= max_chars:
                break
        return _preserve_lines("\n".join(parts))[:max_chars], "PDF text extraction (no OCR)", final_url, []

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    links: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(final_url, anchor.get("href", ""))
        label = _clean_text(anchor.get_text(" ", strip=True))
        if href.startswith(("http://", "https://")):
            links.append((label, href))
    return _preserve_lines(soup.get_text("\n", strip=True))[:max_chars], "HTML text extraction", final_url, links


def _link_score(label: str, url: str) -> int:
    text = f"{label} {url}".casefold()
    score = sum(5 for term in LINK_TERMS if term.casefold() in text)
    year = _year(text)
    if year:
        score += max(0, int(year) - 2020)
    if url.lower().split("?")[0].endswith(".pdf"):
        score += 5
    if "/category/" not in url.lower() and len(urlparse(url).path.strip("/").split("/")) >= 2:
        score += 3
    return score


def _index_like(url: str, links: list[tuple[str, str]]) -> bool:
    low = url.lower()
    return "/category/" in low or (len(links) >= 20 and low.rstrip("/").endswith("quan-he-co-dong"))


def _document_has_management_signal(text: str) -> bool:
    low = _clean_text(text).casefold()
    role_hit = any(term.strip().casefold() in low for _, terms, _ in ROLE_RULES for term in terms if term.strip())
    person_hit = bool(PERSON_NAME_PATTERN.search(_clean_text(text)))
    compensation_hit = any(x in low for x in ("thù lao", "remuneration", "esop", "cổ phần nắm giữ", "ownership", "người nội bộ", "giao dịch"))
    return (role_hit and person_hit) or compensation_hit


def _wordpress_search_urls(seed: str) -> list[str]:
    parsed = urlparse(seed)
    if not parsed.scheme or not parsed.netloc:
        return []
    root = f"{parsed.scheme}://{parsed.netloc}/"
    terms = ("nhân sự", "tổng giám đốc", "chủ tịch", "báo cáo thường niên", "báo cáo tài chính")
    return [root + "?s=" + quote_plus(term) for term in terms]


def discover_management_candidates(
    ticker: str,
    company_name: str = "",
    *,
    max_documents: int = 10,
    max_targets: int = 5,
    timeout_seconds: float = 8.0,
) -> ManagementDiscoveryResult:
    """Crawl configured company/IR sources and discover candidate manager research targets."""
    safe = _clean_text(ticker).upper()
    seeds = list(KNOWN_COMPANY_DOMAINS.get(safe, []))
    if not seeds:
        return ManagementDiscoveryResult(
            pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS), [], [],
            "No known company/IR domain configured; manager discovery skipped.",
        )

    documents: list[dict[str, Any]] = []
    fetched: set[str] = set()
    queued: set[str] = set()
    queue: list[tuple[int, int, str, str, str]] = []
    errors: list[str] = []
    fetch_count = 0
    max_fetches = max(30, max_documents * 6)

    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(timeout_seconds, connect=min(3.0, timeout_seconds)), follow_redirects=True) as client:
        for seed in seeds:
            domain = _domain(seed)
            starters = [(100, f"{safe} official/IR seed", seed)]
            starters += [(92, f"{safe} official site search", u) for u in _wordpress_search_urls(seed)]
            for score, label, href in starters:
                if href not in queued:
                    queue.append((score, 0, label, href, domain))
                    queued.add(href)

        while queue and len(documents) < max_documents and fetch_count < max_fetches:
            queue.sort(key=lambda x: (x[0], -x[1]), reverse=True)
            score, depth, label, href, root_domain = queue.pop(0)
            if href in fetched:
                continue
            fetched.add(href)
            fetch_count += 1
            try:
                text, method, final_url, links = _fetch_text(client, href)
            except Exception as exc:
                errors.append(f"document {href}: {exc}")
                continue
            if len(_clean_text(text)) < 80:
                continue

            is_pdf = "PDF" in method
            is_index = _index_like(final_url, links)
            if (is_pdf or not is_index) and _document_has_management_signal(text):
                documents.append({
                    "title": label or f"{safe} official management disclosure",
                    "url": final_url,
                    "text": text,
                    "method": method,
                })

            # Index/search pages are discovery surfaces. Follow relevant same-domain links up to 3 hops.
            if links and depth < 3:
                for child_label, child_href in links:
                    if child_href in fetched or child_href in queued or not _same_domain(child_href, root_domain):
                        continue
                    child_score = _link_score(child_label, child_href)
                    if child_score <= 0:
                        continue
                    queue.append((child_score, depth + 1, child_label, child_href, root_domain))
                    queued.add(child_href)

    managers = extract_management_candidates_from_documents(documents, max_targets=max_targets)
    targets = choose_research_targets(managers, max_targets=max_targets)
    note = (
        f"Fetched {fetch_count} official/company URLs; retained {len(documents)} substantive management documents; "
        f"discovered {len(managers)} manager-role candidates; research targets={len(targets)}."
    )
    if errors:
        note += " Some sources failed: " + " | ".join(errors[:3])
    return ManagementDiscoveryResult(managers, documents, targets, note)


__all__ = [
    "MANAGER_CANDIDATE_COLUMNS", "ManagementDiscoveryResult",
    "extract_management_candidates_from_documents", "choose_research_targets",
    "discover_management_candidates",
]
