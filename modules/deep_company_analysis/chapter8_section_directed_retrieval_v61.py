from __future__ import annotations

"""Chapter 8 Phase 8P / V61 — official document expansion + section-directed retrieval.

V60 showed that higher OCR resolution alone does not materially close the remaining management
research gaps. V61 therefore expands the official-document set first, then uses the still-open
source-locked dimensions to choose the most relevant issuer archive sections and documents.

Boundaries:
- only issuer/company-IR URLs already accepted by the Chapter 8 official-source allow-list are used;
- discovery is bounded and same-domain; no search-engine result is treated as evidence;
- Trecapital canonical remains the financial SSOT and Chapter 7 remains manager identity SSOT;
- extracted rows remain ``Candidate — analyst verify`` and are never auto-promoted;
- no analyst assessment/status/confidence, management score, MOS/Research Gate or signal is written;
- Q43/Q46/Q47 source-lock rules are inherited unchanged.
"""

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urldefrag, urljoin, urlparse
import re
import unicodedata

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS
from modules.deep_company_analysis.chapter8_official_deep_retrieval import build_official_deep_targets
from modules.deep_company_analysis.chapter8_official_file_ingestion_v60 import OfficialFileIngestionAgentV60
from modules.deep_company_analysis.chapter8_official_source_adapters import is_official_url
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS


SECTION_PLAN_COLUMNS = [
    "Section",
    "Open Target Count",
    "Questions",
    "Dimension Keys",
    "Document Families",
    "Section Terms",
]
DISCOVERY_COLUMNS = [
    "Section",
    "Title",
    "Year",
    "Landing Page",
    "Document URL",
    "Score",
    "Official URL",
    "Discovery Method",
]
DOWNLOAD_COLUMNS = [
    "Section",
    "Title",
    "Year",
    "Document URL",
    "Status",
    "Bytes",
    "Text Layer chars",
    "OCR Candidate",
]


@dataclass(frozen=True)
class SectionRule:
    name: str
    questions: tuple[str, ...]
    families: tuple[str, ...]
    terms: tuple[str, ...]


SECTION_RULES: tuple[SectionRule, ...] = (
    SectionRule(
        "People / culture / hiring",
        ("Q43", "Q44"),
        ("Annual report", "Sustainability/ESG", "Governance report", "AGM materials"),
        (
            "nhan su", "nhân sự", "nguoi lao dong", "người lao động", "dao tao", "đào tạo",
            "tuyen dung", "tuyển dụng", "phuc loi", "phúc lợi", "van hoa", "văn hóa", "culture",
            "employee", "training", "recruitment", "succession", "talent", "appointment", "bo nhiem", "bổ nhiệm",
        ),
    ),
    SectionRule(
        "Stakeholders",
        ("Q39",),
        ("Annual report", "Sustainability/ESG", "AGM materials"),
        (
            "khach hang", "khách hàng", "nha cung cap", "nhà cung cấp", "co dong", "cổ đông", "doi tac", "đối tác",
            "stakeholder", "customer", "supplier", "shareholder", "partner", "community", "cong dong", "cộng đồng",
        ),
    ),
    SectionRule(
        "Strategy / operating model",
        ("Q40", "Q42"),
        ("Annual report", "Board resolutions", "Business-plan updates", "AGM materials"),
        (
            "chien luoc", "chiến lược", "ke hoach", "kế hoạch", "chuyen doi", "chuyển đổi", "cai tien", "cải tiến",
            "phan cap", "phân cấp", "uy quyen", "ủy quyền", "strategy", "business plan", "transformation", "delegation",
            "autonomy", "operating model", "decision rights",
        ),
    ),
    SectionRule(
        "Guidance / accountability",
        ("Q41",),
        ("Business-plan updates", "Board resolutions", "Annual report", "AGM materials"),
        (
            "ke hoach quy", "kế hoạch quý", "ke hoach nam", "kế hoạch năm", "guidance", "forecast", "outlook",
            "muc tieu", "mục tiêu", "thuc hien", "thực hiện", "ket qua", "kết quả",
        ),
    ),
    SectionRule(
        "Cost discipline",
        ("Q45",),
        ("Annual report", "Board resolutions", "AGM materials", "Restructuring disclosures"),
        (
            "chi phi", "chi phí", "tiet kiem", "tiết kiệm", "cat giam", "cắt giảm", "tai cau truc", "tái cấu trúc",
            "cost reduction", "cost control", "efficiency", "waste", "restructuring", "productivity",
        ),
    ),
    SectionRule(
        "Capital allocation / buyback",
        ("Q46", "Q47"),
        ("Board resolutions", "AGM materials", "Annual report", "M&A disclosures", "Dividend/buyback disclosures"),
        (
            "co tuc", "cổ tức", "dau tu", "đầu tư", "mua lai co phieu", "mua lại cổ phiếu", "co phieu quy", "cổ phiếu quỹ",
            "mua lai", "mua lại", "sap nhap", "sáp nhập", "mua co phan", "mua cổ phần", "acquisition", "buyback",
            "share repurchase", "dividend", "capital allocation", "cash", "m&a",
        ),
    ),
)

ARCHIVE_HINTS = (
    "quan-he-co-dong", "investor", "investor-relations", "bao-cao-thuong-nien", "annual-report",
    "bao-cao-quan-tri", "governance", "dai-hoi-co-dong", "agm", "nghi-quyet", "resolution",
    "thong-bao", "cong-bo-thong-tin", "disclosure", "sustainability", "esg", "/page/",
)
DEFAULT_ARCHIVE_SUFFIXES = (
    "category/quan-he-co-dong/bao-cao-thuong-nien/",
    "category/quan-he-co-dong/bao-cao-quan-tri/",
    "category/quan-he-co-dong/dai-hoi-co-dong/",
    "category/quan-he-co-dong/nghi-quyet-dai-hoi-co-dong/",
    "category/quan-he-co-dong/thong-bao/",
    "investor-relations/",
    "annual-reports/",
)


@dataclass
class SectionDirectedRetrievalResult:
    targets: pd.DataFrame
    section_plan: pd.DataFrame
    discovery: pd.DataFrame
    downloads: pd.DataFrame
    ingestion: Any
    note: str


def _safe(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _safe(value).casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.casefold().replace("www.", "")
    except Exception:
        return ""


def _same_domain(url: str, root: str) -> bool:
    left = _domain(url)
    right = _domain(root)
    return bool(left and right and (left == right or left.endswith("." + right) or right.endswith("." + left)))


def _year(text: str) -> int:
    years = [int(x) for x in re.findall(r"\b(20\d{2})\b", str(text or ""))]
    return max(years) if years else 0


def _rule_for_question(question: str) -> SectionRule:
    for rule in SECTION_RULES:
        if question in rule.questions:
            return rule
    return SECTION_RULES[2]


def build_section_plan(targets: pd.DataFrame) -> pd.DataFrame:
    """Group currently open dimensions into section/document-family retrieval priorities."""
    if not isinstance(targets, pd.DataFrame) or targets.empty:
        return pd.DataFrame(columns=SECTION_PLAN_COLUMNS)
    rows: list[dict[str, Any]] = []
    for rule in SECTION_RULES:
        subset = targets[targets["Question"].astype(str).isin(rule.questions)].copy()
        if subset.empty:
            continue
        keys = [f"{_safe(row.get('Question'))}:{_safe(row.get('Dimension Key'))}" for _, row in subset.iterrows()]
        rows.append({
            "Section": rule.name,
            "Open Target Count": int(len(subset)),
            "Questions": ", ".join(sorted(set(subset["Question"].astype(str)))),
            "Dimension Keys": ", ".join(keys),
            "Document Families": " | ".join(rule.families),
            "Section Terms": " | ".join(rule.terms),
        })
    frame = pd.DataFrame(rows, columns=SECTION_PLAN_COLUMNS)
    if frame.empty:
        return frame
    return frame.sort_values(["Open Target Count", "Section"], ascending=[False, True], kind="stable").reset_index(drop=True)


def filter_targets_to_keys(targets: pd.DataFrame, keys: set[tuple[str, str]] | None) -> pd.DataFrame:
    if not keys or not isinstance(targets, pd.DataFrame) or targets.empty:
        return targets.copy() if isinstance(targets, pd.DataFrame) else pd.DataFrame()
    mask = [(_safe(row.get("Question")), _safe(row.get("Dimension Key"))) in keys for _, row in targets.iterrows()]
    return targets.loc[mask].reset_index(drop=True)


def _section_score(text: str, rule: SectionRule) -> int:
    folded = _fold(text)
    score = 0
    for term in rule.terms:
        folded_term = _fold(term)
        if folded_term and folded_term in folded:
            score += 4 if " " in folded_term else 2
    for family in rule.families:
        for token in _fold(family).split():
            if len(token) >= 5 and token in folded:
                score += 1
    return score


def _best_section(text: str, active_sections: set[str]) -> tuple[str, int]:
    ranked: list[tuple[int, str]] = []
    for rule in SECTION_RULES:
        if active_sections and rule.name not in active_sections:
            continue
        ranked.append((_section_score(text, rule), rule.name))
    if not ranked:
        return "", 0
    score, name = max(ranked, key=lambda item: (item[0], item[1]))
    return name, score


def _is_archive_link(label: str, url: str) -> bool:
    folded = _fold(f"{label} {url}")
    return any(_fold(hint) in folded for hint in ARCHIVE_HINTS)


def _candidate_seeds(ticker: str, explicit_seed_urls: Iterable[str] | None) -> list[str]:
    symbol = _safe(ticker).upper()
    roots = [urldefrag(str(url))[0].rstrip("/") + "/" for url in KNOWN_COMPANY_DOMAINS.get(symbol, [])]
    seeds: list[str] = []
    for root in roots:
        if root not in seeds:
            seeds.append(root)
        for suffix in DEFAULT_ARCHIVE_SUFFIXES:
            url = urljoin(root, suffix)
            if url not in seeds:
                seeds.append(url)
    for url in explicit_seed_urls or ():
        clean = urldefrag(str(url))[0]
        if clean and clean not in seeds and any(_same_domain(clean, root) for root in roots):
            seeds.append(clean)
    return seeds


def discover_section_directed_sources(
    ticker: str,
    targets: pd.DataFrame,
    *,
    seed_urls: Iterable[str] | None = None,
    max_index_pages: int = 18,
    max_landing_pages: int = 24,
    max_documents: int = 18,
    year_floor: int | None = None,
    timeout_seconds: float = 5.0,
) -> pd.DataFrame:
    """Discover historical official documents from issuer archive/index pages.

    This is a bounded same-domain crawler. It follows investor-relations archive/category pages,
    then article/landing pages, and finally official PDF links. Search-engine snippets are not used.
    """
    symbol = _safe(ticker).upper()
    all_roots = [str(url) for url in KNOWN_COMPANY_DOMAINS.get(symbol, [])]
    if not all_roots:
        return pd.DataFrame(columns=DISCOVERY_COLUMNS)
    active_sections = set(build_section_plan(targets)["Section"].astype(str)) if not targets.empty else set()
    current_year = datetime.utcnow().year
    floor = int(year_floor or (current_year - 5))
    max_index_pages = max(1, min(int(max_index_pages), 40))
    max_landing_pages = max(1, min(int(max_landing_pages), 60))
    max_documents = max(1, min(int(max_documents), 40))

    seeds = _candidate_seeds(symbol, seed_urls)
    archive_queue: list[str] = list(seeds)
    landing_queue: list[tuple[int, str, str, str]] = []  # score, url, title, section
    seen_archive: set[str] = set()
    seen_landing: set[str] = set()
    found: dict[str, dict[str, Any]] = {}
    timeout = httpx.Timeout(timeout_seconds, connect=min(3.0, timeout_seconds))

    with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        while archive_queue and len(seen_archive) < max_index_pages:
            url = archive_queue.pop(0)
            if url in seen_archive or not any(_same_domain(url, root) for root in all_roots):
                continue
            seen_archive.add(url)
            try:
                response = client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
            except Exception:
                continue
            for anchor in soup.find_all("a", href=True):
                label = _safe(anchor.get_text(" ", strip=True))
                absolute = urldefrag(urljoin(str(response.url), str(anchor.get("href") or "")))[0]
                if not absolute.startswith(("http://", "https://")):
                    continue
                if not any(_same_domain(absolute, root) for root in all_roots):
                    continue
                text = f"{label} {absolute}"
                if absolute.lower().split("?", 1)[0].endswith(".pdf"):
                    if not is_official_url(absolute, symbol):
                        continue
                    section, section_score = _best_section(text, active_sections)
                    yr = _year(text)
                    if yr and yr < floor:
                        continue
                    score = section_score + (3 if yr >= current_year - 2 else 1 if yr else 0) + 5
                    found[absolute] = {
                        "Section": section,
                        "Title": label or absolute.rsplit("/", 1)[-1],
                        "Year": yr,
                        "Landing Page": str(response.url),
                        "Document URL": absolute,
                        "Score": score,
                        "Official URL": "Yes",
                        "Discovery Method": "Issuer archive direct PDF",
                    }
                    continue

                section, section_score = _best_section(text, active_sections)
                yr = _year(text)
                if _is_archive_link(label, absolute) and absolute not in seen_archive and absolute not in archive_queue:
                    archive_queue.append(absolute)
                if section_score > 0 or yr >= floor or _is_archive_link(label, absolute):
                    landing_queue.append((section_score + (2 if yr >= floor else 0), absolute, label, section))

        landing_queue.sort(key=lambda row: (-row[0], row[1]))
        for _, url, title_hint, section_hint in landing_queue:
            if len(seen_landing) >= max_landing_pages or len(found) >= max_documents * 3:
                break
            if url in seen_landing or url in seen_archive:
                continue
            seen_landing.add(url)
            try:
                response = client.get(url)
                response.raise_for_status()
                content_type = _safe(response.headers.get("content-type")).casefold()
                if "pdf" in content_type:
                    continue
                soup = BeautifulSoup(response.text, "html.parser")
            except Exception:
                continue
            page_title = _safe(soup.title.get_text(" ", strip=True) if soup.title else title_hint)
            page_text = _safe(soup.get_text(" ", strip=True))[:35_000]
            section, page_score = _best_section(f"{page_title} {page_text}", active_sections)
            if not section:
                section = section_hint
            landing_year = _year(f"{page_title} {page_text[:5000]} {url}")
            if landing_year and landing_year < floor:
                continue
            for anchor in soup.find_all("a", href=True):
                absolute = urldefrag(urljoin(str(response.url), str(anchor.get("href") or "")))[0]
                if not absolute.lower().split("?", 1)[0].endswith(".pdf"):
                    continue
                if not is_official_url(absolute, symbol):
                    continue
                label = _safe(anchor.get_text(" ", strip=True))
                doc_year = _year(f"{label} {absolute} {page_title}") or landing_year
                if doc_year and doc_year < floor:
                    continue
                link_section, link_score = _best_section(f"{page_title} {label} {absolute}", active_sections)
                final_section = link_section or section
                score = max(page_score, link_score) + 8 + (3 if doc_year >= current_year - 2 else 1 if doc_year else 0)
                previous = found.get(absolute)
                row = {
                    "Section": final_section,
                    "Title": label or page_title or absolute.rsplit("/", 1)[-1],
                    "Year": doc_year,
                    "Landing Page": str(response.url),
                    "Document URL": absolute,
                    "Score": int(score),
                    "Official URL": "Yes",
                    "Discovery Method": "Issuer archive -> landing page -> PDF",
                }
                if previous is None or int(row["Score"]) > int(previous.get("Score", 0)):
                    found[absolute] = row

    frame = pd.DataFrame(found.values(), columns=DISCOVERY_COLUMNS)
    if frame.empty:
        return frame
    frame["Score"] = pd.to_numeric(frame["Score"], errors="coerce").fillna(0).astype(int)
    frame["Year"] = pd.to_numeric(frame["Year"], errors="coerce").fillna(0).astype(int)
    frame = frame.sort_values(["Score", "Year", "Section", "Document URL"], ascending=[False, False, True, True], kind="stable")

    # Diversify so one section/year cannot consume the entire document budget.
    selected: list[int] = []
    seen_sections: set[str] = set()
    for idx, row in frame.iterrows():
        section = _safe(row.get("Section"))
        if section and section not in seen_sections and len(selected) < max_documents:
            selected.append(idx)
            seen_sections.add(section)
    for idx in frame.index:
        if len(selected) >= max_documents:
            break
        if idx not in selected:
            selected.append(idx)
    return frame.loc[selected].reset_index(drop=True)


def _pdf_text_chars(data: bytes, *, max_pages: int = 6) -> int:
    try:
        reader = PdfReader(BytesIO(data))
        chars = 0
        for page in reader.pages[: max(1, int(max_pages))]:
            chars += len(_safe(page.extract_text() or ""))
            if chars >= 1000:
                break
        return chars
    except Exception:
        return 0


def download_section_documents(
    ticker: str,
    discovery: pd.DataFrame,
    *,
    max_files: int = 10,
    max_scanned_ocr_docs: int = 2,
    max_bytes: int = 30 * 1024 * 1024,
    timeout_seconds: float = 25.0,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Download diversified discovered PDFs, preferring text-layer documents before scanned PDFs."""
    symbol = _safe(ticker).upper()
    if not isinstance(discovery, pd.DataFrame) or discovery.empty:
        return [], pd.DataFrame(columns=DOWNLOAD_COLUMNS)
    max_files = max(1, min(int(max_files), 20))
    max_scanned_ocr_docs = max(0, min(int(max_scanned_ocr_docs), 4))
    timeout = httpx.Timeout(timeout_seconds, connect=min(8.0, timeout_seconds))
    attempts: list[dict[str, Any]] = []
    downloaded: list[tuple[dict[str, Any], dict[str, Any], int]] = []
    with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        for _, row in discovery.iterrows():
            url = _safe(row.get("Document URL"))
            base = {
                "Section": _safe(row.get("Section")),
                "Title": _safe(row.get("Title")),
                "Year": int(row.get("Year") or 0),
                "Document URL": url,
                "Status": "",
                "Bytes": 0,
                "Text Layer chars": 0,
                "OCR Candidate": "No",
            }
            if not is_official_url(url, symbol):
                attempts.append({**base, "Status": "Rejected: not official"})
                continue
            try:
                headers = {**HEADERS, "Accept": "application/pdf,*/*;q=0.8", "Referer": _safe(row.get("Landing Page"))}
                with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError("document too large")
                        chunks.append(chunk)
                data = b"".join(chunks)
                if not data.lstrip().startswith(b"%PDF-"):
                    attempts.append({**base, "Status": "Rejected: non-PDF response", "Bytes": len(data)})
                    continue
                text_chars = _pdf_text_chars(data)
                item = {
                    "name": url.rsplit("/", 1)[-1].split("?", 1)[0] or "official.pdf",
                    "bytes": data,
                    "issuer": "Company/IR",
                    "source_url": url,
                    "official_confirmed": True,
                    "title": _safe(row.get("Title")),
                    "section": _safe(row.get("Section")),
                    "year": int(row.get("Year") or 0),
                }
                attempt = {
                    **base,
                    "Status": "Fetched",
                    "Bytes": len(data),
                    "Text Layer chars": int(text_chars),
                    "OCR Candidate": "Yes" if text_chars == 0 else "No",
                }
                attempts.append(attempt)
                downloaded.append((item, attempt, text_chars))
            except Exception as exc:
                attempts.append({**base, "Status": f"Fetch failed: {exc}"})

    # Prefer text-layer documents; allow only a small number of scanned documents into expensive OCR.
    text_items = [item for item, _, chars in downloaded if chars > 0]
    scan_items = [item for item, _, chars in downloaded if chars <= 0][:max_scanned_ocr_docs]
    files = (text_items + scan_items)[:max_files]
    selected_urls = {_safe(item.get("source_url")) for item in files}
    for attempt in attempts:
        if attempt["Status"] == "Fetched" and attempt["Document URL"] not in selected_urls:
            attempt["Status"] = "Fetched — deferred by V61 runtime budget"
    return files, pd.DataFrame(attempts, columns=DOWNLOAD_COLUMNS)


class SectionDirectedRetrievalAgentV61:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        ticker: str,
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        target_keys: set[tuple[str, str]] | None = None,
        seed_urls: Iterable[str] | None = None,
        max_targets: int = 48,
        max_documents: int = 12,
        max_files: int = 8,
        max_scanned_ocr_docs: int = 2,
        year_floor: int | None = None,
    ) -> SectionDirectedRetrievalResult:
        base_candidates = existing_candidates if isinstance(existing_candidates, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
        targets = build_official_deep_targets(base_candidates, max_targets=max_targets)
        targets = filter_targets_to_keys(targets, target_keys)
        plan = build_section_plan(targets)
        discovery = discover_section_directed_sources(
            ticker,
            targets,
            seed_urls=seed_urls,
            max_documents=max_documents,
            year_floor=year_floor,
        )
        files, downloads = download_section_documents(
            ticker,
            discovery,
            max_files=max_files,
            max_scanned_ocr_docs=max_scanned_ocr_docs,
        )
        ingestion_agent = OfficialFileIngestionAgentV60(self.raw_dir / "official_files")
        ingestion = ingestion_agent.ingest(
            ticker,
            files,
            existing_candidates=base_candidates,
            manager_reference=manager_reference,
            max_targets=max_targets,
            max_files=max_files,
            enable_ocr=True,
            ocr_languages="vie+eng",
            coarse_dpi=110,
            coarse_max_pages=30,
            coarse_workers=4,
            high_res_dpi=220,
            high_res_max_pages=8,
            neighbor_radius=1,
        )
        self.last_ocr_diagnostics = ingestion_agent.last_diagnostics
        fetched = int(downloads["Status"].astype(str).str.startswith("Fetched").sum()) if not downloads.empty else 0
        note = (
            f"Phase 8P section-directed retrieval: {len(targets)} open target(s) mapped to {len(plan)} section(s); "
            f"discovered {len(discovery)} official document candidate(s), fetched {fetched}, sent {len(files)} into local extraction/OCR; "
            f"new evidence candidates={len(ingestion.new_candidates)}. All remain Candidate — analyst verify."
        )
        return SectionDirectedRetrievalResult(targets, plan, discovery, downloads, ingestion, note)


__all__ = [
    "DISCOVERY_COLUMNS",
    "DOWNLOAD_COLUMNS",
    "SECTION_PLAN_COLUMNS",
    "SECTION_RULES",
    "SectionDirectedRetrievalAgentV61",
    "SectionDirectedRetrievalResult",
    "build_section_plan",
    "discover_section_directed_sources",
    "download_section_documents",
    "filter_targets_to_keys",
]
