from __future__ import annotations

"""Chapter 8 Phase 8C — Management Operations Evidence Research Assistant.

This module researches candidate evidence for Michael Shearn Chapter 8 Q39-Q47.
It is deliberately evidence-only:
- Chapter 7 remains the manager identity/background single source of truth.
- Trecapital canonical financial data remains the financial single source of truth.
- Web/official disclosures are qualitative/event evidence candidates, never a parallel financial dataset.
- Nothing here writes analyst assessments, management scores, MOS, Research Gate, or BUY/HOLD/SELL.
- Search snippets and extracted text require analyst verification before promotion into the Chapter 8 workspace.
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

from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS, WebEvidenceAgent
import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_data_bridge import (
    MANAGER_SOURCE_LABEL,
    build_manager_reference,
)
from modules.deep_company_analysis.chapter7_research import fetch_document_text


QUESTION_ORDER = ch8.QUESTION_KEYS
RESEARCH_BOUNDARY = (
    "Evidence candidates only — analyst verification/promotion required; no management score, "
    "no automatic competence conclusion, no MOS/Research Gate, and no BUY/HOLD/SELL."
)

FOCUS_TERMS: dict[str, tuple[str, ...]] = {
    "Q39": (
        "stakeholder", "các bên liên quan", "khách hàng", "customer", "employee", "nhân viên",
        "supplier", "nhà cung cấp", "shareholder", "cổ đông", "partner", "đối tác",
        "community", "cộng đồng", "sustainability", "phát triển bền vững",
    ),
    "Q40": (
        "continuous improvement", "cải tiến liên tục", "kaizen", "lean", "operational excellence",
        "nâng cao hiệu quả", "strategic plan", "kế hoạch chiến lược", "chiến lược", "strategy",
        "frontline", "tuyến đầu", "feedback", "phản hồi", "adapt", "thích ứng", "transformation", "chuyển đổi",
    ),
    "Q41": (
        "guidance", "earnings guidance", "revenue guidance", "profit guidance", "forecast",
        "kế hoạch doanh thu", "kế hoạch lợi nhuận", "kế hoạch kinh doanh", "chỉ tiêu kinh doanh",
        "điều chỉnh kế hoạch", "revised guidance", "withdraw guidance", "rút kế hoạch",
    ),
    "Q42": (
        "centralized", "centralised", "tập trung", "decentralized", "decentralised", "phân quyền",
        "ủy quyền", "uỷ quyền", "autonomy", "tự chủ", "business unit", "đơn vị kinh doanh",
        "subsidiary", "công ty con", "decision authority", "thẩm quyền quyết định",
    ),
    "Q43": (
        "employee", "nhân viên", "người lao động", "human resources", "nhân sự", "training", "đào tạo",
        "retention", "giữ chân", "turnover", "nghỉ việc", "promote from within", "thăng tiến nội bộ",
        "career path", "lộ trình nghề nghiệp", "culture", "văn hóa", "văn hoá", "shared values", "giá trị cốt lõi",
        "engagement", "gắn kết", "layoff", "sa thải", "recruit", "tuyển dụng", "benefit", "phúc lợi",
    ),
    "Q44": (
        "hiring", "recruitment", "tuyển dụng", "bổ nhiệm", "appointed", "promoted", "thăng chức",
        "internal candidate", "ứng viên nội bộ", "external hire", "tuyển bên ngoài", "succession", "kế nhiệm",
        "leadership development", "phát triển lãnh đạo", "talent", "nhân tài",
    ),
    "Q45": (
        "cost cutting", "cost reduction", "cắt giảm chi phí", "tiết giảm chi phí", "cost saving", "tiết kiệm chi phí",
        "efficiency", "hiệu quả", "restructuring", "tái cấu trúc", "layoff", "sa thải",
        "procurement savings", "tối ưu mua hàng", "overhead", "chi phí quản lý", "waste", "lãng phí",
    ),
    "Q46": (
        "capital allocation", "phân bổ vốn", "reinvest", "tái đầu tư", "capex", "đầu tư dự án",
        "cash reserve", "tiền mặt", "dividend", "cổ tức", "buyback", "share repurchase", "mua lại cổ phiếu",
        "acquisition", "m&a", "mua bán sáp nhập", "hurdle rate", "tỷ suất sinh lời yêu cầu", "roic", "irr",
    ),
    "Q47": (
        "buyback", "share repurchase", "stock repurchase", "repurchase program", "treasury shares",
        "mua lại cổ phiếu", "mua cổ phiếu quỹ", "cổ phiếu quỹ", "hủy cổ phiếu quỹ", "huỷ cổ phiếu quỹ",
        "repurchase authorization", "phương án mua lại", "giá mua lại", "average repurchase price",
    ),
}

QUERY_TERMS: dict[str, tuple[str, str]] = {
    "Q39": (
        "khách hàng nhân viên nhà cung cấp cổ đông đối tác cộng đồng phát triển bền vững",
        "stakeholders customers employees suppliers shareholders partners community sustainability",
    ),
    "Q40": (
        "cải tiến liên tục hiệu quả vận hành kế hoạch chiến lược phản hồi tuyến đầu thích ứng",
        "continuous improvement operational excellence strategic plan frontline feedback adaptation",
    ),
    "Q41": (
        "kế hoạch doanh thu lợi nhuận chỉ tiêu kinh doanh điều chỉnh kế hoạch",
        "earnings guidance revenue profit forecast revised withdrawn guidance",
    ),
    "Q42": (
        "tập trung phân quyền ủy quyền tự chủ công ty con thẩm quyền quyết định",
        "centralized decentralized delegation autonomy business unit decision authority",
    ),
    "Q43": (
        "nhân viên người lao động đào tạo giữ chân thăng tiến văn hóa phúc lợi tuyển dụng",
        "employees training retention promotion culture engagement benefits recruiting",
    ),
    "Q44": (
        "tuyển dụng bổ nhiệm thăng chức kế nhiệm phát triển lãnh đạo nhân tài",
        "hiring recruitment appointment promotion succession leadership development talent",
    ),
    "Q45": (
        "cắt giảm chi phí tiết kiệm chi phí hiệu quả tái cấu trúc lãng phí",
        "cost cutting cost reduction efficiency restructuring waste overhead savings",
    ),
    "Q46": (
        "phân bổ vốn tái đầu tư cổ tức mua lại cổ phiếu mua bán sáp nhập tỷ suất sinh lời",
        "capital allocation reinvest dividends buybacks acquisitions hurdle rate ROIC",
    ),
    "Q47": (
        "mua lại cổ phiếu cổ phiếu quỹ phương án mua lại giá mua lại",
        "buyback share repurchase treasury shares authorization repurchase price",
    ),
}

SUBTOPICS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "Q39": (
        ("Customers", ("customer", "khách hàng")),
        ("Employees", ("employee", "nhân viên", "người lao động")),
        ("Suppliers", ("supplier", "nhà cung cấp")),
        ("Shareholders", ("shareholder", "cổ đông")),
        ("Business partners", ("partner", "đối tác")),
        ("Other stakeholders", ("community", "cộng đồng", "sustainability", "phát triển bền vững")),
    ),
    "Q40": (
        ("Continuous improvement", ("continuous improvement", "cải tiến liên tục", "kaizen", "lean", "operational excellence")),
        ("Strategic plan / transformation", ("strategic plan", "kế hoạch chiến lược", "strategy", "chiến lược", "transformation", "chuyển đổi")),
        ("Frontline feedback", ("frontline", "tuyến đầu", "feedback", "phản hồi")),
        ("Adaptation", ("adapt", "thích ứng")),
    ),
    "Q41": (
        ("Guidance issued", ("guidance", "forecast", "kế hoạch doanh thu", "kế hoạch lợi nhuận", "kế hoạch kinh doanh", "chỉ tiêu kinh doanh")),
        ("Guidance revised / withdrawn", ("revised guidance", "withdraw guidance", "điều chỉnh kế hoạch", "rút kế hoạch")),
    ),
    "Q42": (
        ("Central control", ("centralized", "centralised", "tập trung")),
        ("Delegation / autonomy", ("decentralized", "decentralised", "phân quyền", "ủy quyền", "uỷ quyền", "autonomy", "tự chủ")),
        ("Business-unit decision rights", ("business unit", "đơn vị kinh doanh", "subsidiary", "công ty con", "decision authority", "thẩm quyền quyết định")),
    ),
    "Q43": (
        ("Training resources", ("training", "đào tạo")),
        ("Retention / turnover", ("retention", "giữ chân", "turnover", "nghỉ việc")),
        ("Promotion / career path", ("promote from within", "thăng tiến nội bộ", "career path", "lộ trình nghề nghiệp")),
        ("Culture / shared values", ("culture", "văn hóa", "văn hoá", "shared values", "giá trị cốt lõi")),
        ("Employee voice / engagement", ("engagement", "gắn kết", "employee feedback", "ý kiến người lao động")),
        ("Benefits / treatment", ("benefit", "phúc lợi", "layoff", "sa thải")),
        ("Recruitment attractiveness", ("recruit", "tuyển dụng", "applicant", "ứng viên")),
    ),
    "Q44": (
        ("Internal promotion / succession", ("promoted", "thăng chức", "internal candidate", "ứng viên nội bộ", "succession", "kế nhiệm")),
        ("External hire", ("external hire", "tuyển bên ngoài")),
        ("Selection / talent development", ("hiring", "recruitment", "tuyển dụng", "talent", "nhân tài", "leadership development", "phát triển lãnh đạo")),
        ("Appointment evidence", ("appointed", "bổ nhiệm")),
    ),
    "Q45": (
        ("Cost reduction / savings", ("cost cutting", "cost reduction", "cắt giảm chi phí", "tiết giảm chi phí", "cost saving", "tiết kiệm chi phí")),
        ("Restructuring / layoffs", ("restructuring", "tái cấu trúc", "layoff", "sa thải")),
        ("Efficiency / waste", ("efficiency", "hiệu quả", "waste", "lãng phí", "overhead", "chi phí quản lý")),
    ),
    "Q46": (
        ("Reinvest in business / new projects", ("reinvest", "tái đầu tư", "capex", "đầu tư dự án")),
        ("Hold cash", ("cash reserve", "tiền mặt")),
        ("Pay dividends", ("dividend", "cổ tức")),
        ("Buy back stock", ("buyback", "share repurchase", "mua lại cổ phiếu")),
        ("Make acquisitions", ("acquisition", "m&a", "mua bán sáp nhập")),
        ("Discipline / hurdle evidence", ("hurdle rate", "tỷ suất sinh lời yêu cầu", "roic", "irr", "capital allocation", "phân bổ vốn")),
    ),
    "Q47": (
        ("Authorization / program", ("repurchase authorization", "repurchase program", "phương án mua lại")),
        ("Execution / shares / cash", ("share repurchase", "stock repurchase", "mua lại cổ phiếu", "mua cổ phiếu quỹ", "cổ phiếu quỹ")),
        ("Price / valuation context", ("giá mua lại", "average repurchase price")),
    ),
}

POSITIVE_CUES = (
    "improved", "cải thiện", "training", "đào tạo", "retention", "giữ chân", "promotion", "thăng tiến",
    "employee development", "phát triển nhân viên", "cost saving", "tiết kiệm chi phí", "return on invested capital",
    "hurdle rate", "open market repurchase", "mua lại trên thị trường",
)
COUNTER_CUES = (
    "complaint", "khiếu nại", "strike", "đình công", "high turnover", "nghỉ việc cao", "layoff", "sa thải",
    "failed", "thất bại", "overrun", "vượt chi phí", "impairment", "suy giảm", "write-off", "xóa sổ",
    "dilution", "pha loãng", "penalty", "xử phạt", "violation", "vi phạm",
)

OFFICIAL_LINK_TERMS = (
    "annual report", "bao cao thuong nien", "báo cáo thường niên", "bctn",
    "governance", "quan tri", "quản trị", "bao cao quan tri", "báo cáo quản trị",
    "sustainability", "phat trien ben vung", "phát triển bền vững",
    "human resource", "nhan su", "nhân sự", "employee", "nguoi lao dong", "người lao động",
    "strategy", "chien luoc", "chiến lược", "ke hoach", "kế hoạch",
    "agm", "dhdcd", "dai hoi", "đại hội", "nghi quyet", "nghị quyết",
    "cbtt", "cong bo thong tin", "công bố thông tin", "disclosure",
    "dividend", "co tuc", "cổ tức", "buyback", "repurchase", "co phieu quy", "cổ phiếu quỹ",
    "esop", "thu lao", "thù lao", "remuneration", "appointment", "bo nhiem", "bổ nhiệm",
    "restructuring", "tai cau truc", "tái cấu trúc", "cost", "chi phi", "chi phí",
)

CANDIDATE_COLUMNS = [
    "Select",
    "Candidate ID",
    "Question",
    "Manager ID",
    "Manager",
    "Subtopic",
    "Direction",
    "Source Grade",
    "Explicitness",
    "Source Title",
    "Source URL / File",
    "Source Date",
    "As-of Date",
    "Evidence Text / Reference",
    "Source Method",
    "Data Origin",
    "Status",
]

ATTEMPT_COLUMNS = ["URL", "Domain", "Status", "Method", "Source Grade"]


@dataclass
class Chapter8ResearchResult:
    candidates: pd.DataFrame
    quality: pd.DataFrame
    gaps: pd.DataFrame
    manager_reference: pd.DataFrame
    source_attempts: pd.DataFrame
    raw_paths: list[str]
    note: str


def _safe_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _same_domain(url: str, root_domain: str) -> bool:
    d = _domain(url)
    return bool(d and root_domain and (d == root_domain or d.endswith("." + root_domain) or root_domain.endswith("." + d)))


def _known_domains(ticker: str) -> set[str]:
    out: set[str] = set()
    for url in KNOWN_COMPANY_DOMAINS.get(str(ticker or "").upper().strip(), []):
        d = _domain(url)
        if d:
            out.add(d)
    return out


def source_grade_from_url(url: str, ticker: str) -> str:
    domain = _domain(url)
    known = _known_domains(ticker)
    if any(domain == d or domain.endswith("." + d) for d in known):
        return "A — Company/Official disclosure"
    group = WebEvidenceAgent._domain_group(domain)
    if group == "Nguồn công bố chính thức":
        return "A — Exchange/Regulator disclosure"
    if group == "Nguồn doanh nghiệp/IR":
        return "A — Company/Official disclosure"
    if group == "Dữ liệu/tin tài chính":
        return "B — Independent financial source/research"
    return "C — Secondary/context source"


def _year_candidate(text: str) -> str:
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", str(text or ""))
    return years[-1] if years else ""


def _candidate_id(*parts: Any) -> str:
    payload = "\x1f".join(_safe_text(x) for x in parts)
    return sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _manager_match(text: str, manager_reference: pd.DataFrame | None) -> tuple[str, str]:
    if not isinstance(manager_reference, pd.DataFrame) or manager_reference.empty:
        return "", ""
    low = _safe_text(text).casefold()
    rows = []
    for _, row in manager_reference.iterrows():
        name = _safe_text(row.get("Manager"))
        if name:
            rows.append((_safe_text(row.get("Manager ID")), name))
    for manager_id, name in sorted(rows, key=lambda x: len(x[1]), reverse=True):
        if name.casefold() in low:
            return manager_id, name
    return "", ""


def _subtopic(question: str, text: str) -> str:
    low = _safe_text(text).casefold()
    for label, terms in SUBTOPICS.get(question, ()):
        if any(term.casefold() in low for term in terms):
            return label
    return "General evidence"


def direction_cue(text: str) -> str:
    low = _safe_text(text).casefold()
    pos = sum(1 for term in POSITIVE_CUES if term.casefold() in low)
    neg = sum(1 for term in COUNTER_CUES if term.casefold() in low)
    if pos and neg:
        return "Mixed cue — analyst assess"
    if neg:
        return "Counter-evidence cue — analyst assess"
    if pos:
        return "Supporting cue — analyst assess"
    return "Neutral / context — analyst assess"


class _FocusedChapter8Agent(WebEvidenceAgent):
    def __init__(self, raw_dir: str | Path, focus: str, manager_names: list[str] | None = None):
        super().__init__(raw_dir)
        self.focus = focus
        self.manager_names = [_safe_text(x) for x in (manager_names or []) if _safe_text(x)]

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:
        clean = self._clean_company_name(company_name)
        name = clean or company_name or ticker
        vi, en = QUERY_TERMS[self.focus]
        manager_clause = " ".join(f'"{x}"' for x in self.manager_names[:2])
        manager_part = f" {manager_clause}" if manager_clause else ""
        domains = []
        for root in KNOWN_COMPANY_DOMAINS.get(str(ticker).upper().strip(), []):
            d = self._domain(root)
            if d and d not in domains:
                domains.append(d)
        queries: list[str] = []
        if domains:
            queries.append(f'site:{domains[0]} "{ticker}"{manager_part} {vi}')
        queries.append(f'"{ticker}" "{name}"{manager_part} {vi}')
        queries.append(f'"{ticker}" "{name}"{manager_part} {en}')
        return list(dict.fromkeys(queries))


def classify_search_rows(
    raw: pd.DataFrame,
    ticker: str,
    focus: str,
    manager_reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Convert search-result title/snippet rows to candidates.

    Query strings and generic direct source links are never treated as evidence.
    """
    if focus not in QUESTION_ORDER or not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, item in raw.iterrows():
        source = item.to_dict()
        status = _safe_text(source.get("Trạng thái"))
        if status not in {"Tìm thấy", "Evidence trích từ nguồn chính thức", "Evidence trích từ PDF chính thức"}:
            continue
        title = _safe_text(source.get("Tiêu đề"))
        snippet = _safe_text(source.get("Trích yếu"))
        url = _safe_text(source.get("Nguồn/URL"))
        text = _safe_text(f"{title} {snippet}")
        if not text:
            continue
        if not any(term.casefold() in text.casefold() for term in FOCUS_TERMS[focus]):
            continue
        manager_id, manager = _manager_match(text, manager_reference)
        rows.append({
            "Select": False,
            "Candidate ID": _candidate_id(focus, manager_id, url, title, snippet),
            "Question": focus,
            "Manager ID": manager_id,
            "Manager": manager,
            "Subtopic": _subtopic(focus, text),
            "Direction": direction_cue(text),
            "Source Grade": source_grade_from_url(url, ticker),
            "Explicitness": "Search title/snippet candidate — analyst verify",
            "Source Title": title[:240],
            "Source URL / File": url,
            "Source Date": "",
            "As-of Date": _year_candidate(text),
            "Evidence Text / Reference": snippet[:900],
            "Source Method": "Phase 8C focused web research",
            "Data Origin": "External research candidate — analyst verification required",
            "Status": "Candidate — analyst verify",
        })
    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(
        subset=["Question", "Manager ID", "Source URL / File", "Evidence Text / Reference"],
        keep="first",
    ).reset_index(drop=True)


def _relevant_windows(
    text: str,
    question: str,
    manager_names: Iterable[str] | None = None,
    *,
    window: int = 420,
    max_windows: int = 3,
) -> list[str]:
    clean = _safe_text(text)
    if not clean:
        return []
    low = clean.casefold()
    needles = list(FOCUS_TERMS.get(question, ())) + [_safe_text(x) for x in (manager_names or []) if _safe_text(x)]
    positions: list[int] = []
    for needle in needles:
        start = 0
        needle_low = needle.casefold()
        while needle_low and len(positions) < 40:
            pos = low.find(needle_low, start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + max(1, len(needle_low))
    if not positions:
        return []
    out: list[str] = []
    for pos in sorted(set(positions)):
        snippet = _safe_text(clean[max(0, pos - window): min(len(clean), pos + window)])
        if not snippet:
            continue
        if not any(term.casefold() in snippet.casefold() for term in FOCUS_TERMS.get(question, ())):
            continue
        if snippet not in out:
            out.append(snippet)
        if len(out) >= max_windows:
            break
    return out


def official_documents_to_candidates(
    documents: list[dict[str, Any]],
    ticker: str,
    manager_reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Extract question-specific windows from company/official documents.

    A manager name may scope a candidate, but manager identity is only referenced from Chapter 7.
    """
    manager_names = (
        manager_reference.get("Manager", pd.Series(dtype="object")).dropna().astype(str).tolist()
        if isinstance(manager_reference, pd.DataFrame) and not manager_reference.empty
        else []
    )
    rows: list[dict[str, Any]] = []
    for document in documents or []:
        text = _safe_text(document.get("text"))
        url = _safe_text(document.get("url"))
        if not text or not url:
            continue
        title = _safe_text(document.get("title")) or url
        method = _safe_text(document.get("method")) or "Official source extraction"
        low = text.casefold()
        for question in QUESTION_ORDER:
            if not any(term.casefold() in low for term in FOCUS_TERMS[question]):
                continue
            for idx, snippet in enumerate(_relevant_windows(text, question, manager_names, max_windows=3)):
                manager_id, manager = _manager_match(snippet, manager_reference)
                rows.append({
                    "Select": False,
                    "Candidate ID": _candidate_id(question, manager_id, url, snippet, idx),
                    "Question": question,
                    "Manager ID": manager_id,
                    "Manager": manager,
                    "Subtopic": _subtopic(question, snippet),
                    "Direction": direction_cue(snippet),
                    "Source Grade": source_grade_from_url(url, ticker),
                    "Explicitness": "Extracted source text — analyst verify",
                    "Source Title": title[:240],
                    "Source URL / File": url,
                    "Source Date": "",
                    "As-of Date": _year_candidate(f"{title} {url} {snippet}"),
                    "Evidence Text / Reference": snippet[:900],
                    "Source Method": f"Phase 8C official/document extraction — {method}",
                    "Data Origin": "Direct source text — analyst verification required",
                    "Status": "Candidate — analyst verify",
                })
    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)


def _link_priority(label: str, href: str) -> int:
    text = f"{label} {href}".casefold()
    score = sum(3 for term in OFFICIAL_LINK_TERMS if term.casefold() in text)
    if href.lower().split("?")[0].endswith(".pdf"):
        score += 4
    if any(x in text for x in ("2026", "2025", "2024")):
        score += 2
    return score


def discover_official_documents(
    ticker: str,
    *,
    max_documents: int = 18,
    timeout_seconds: float = 4.5,
) -> tuple[list[dict[str, Any]], pd.DataFrame, str]:
    """Crawl a small, bounded set of same-domain official/IR documents.

    It does not OCR, does not infer missing facts, and preserves fetch failures in source_attempts.
    """
    symbol = str(ticker or "").upper().strip()
    roots = list(KNOWN_COMPANY_DOMAINS.get(symbol, []))
    attempts: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    if not roots:
        return documents, pd.DataFrame(columns=ATTEMPT_COLUMNS), f"{symbol}: no registered company/IR root."

    candidate_urls: list[tuple[int, str, str]] = []
    seen_urls: set[str] = set()
    timeout = httpx.Timeout(timeout_seconds, connect=min(2.5, timeout_seconds))
    with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        for root in roots:
            root_url = urldefrag(root)[0]
            root_domain = _domain(root_url)
            try:
                response = client.get(root_url)
                response.raise_for_status()
                content_type = _safe_text(response.headers.get("content-type")).lower()
                if "pdf" in content_type or root_url.lower().split("?")[0].endswith(".pdf"):
                    text, method = fetch_document_text(root_url, timeout_seconds=timeout_seconds, max_pages=35, max_chars=140_000)
                    status = "Fetched" if text else "Empty"
                    attempts.append({"URL": root_url, "Domain": root_domain, "Status": status, "Method": method, "Source Grade": source_grade_from_url(root_url, symbol)})
                    if text:
                        documents.append({"url": root_url, "title": root_url, "text": text, "method": method})
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "noscript", "svg"]):
                    tag.decompose()
                root_text = _safe_text(soup.get_text(" ", strip=True))
                attempts.append({"URL": root_url, "Domain": root_domain, "Status": "Fetched", "Method": "HTML root discovery", "Source Grade": source_grade_from_url(root_url, symbol)})
                if len(root_text) >= 120:
                    documents.append({"url": root_url, "title": _safe_text(soup.title.get_text(" ", strip=True) if soup.title else root_url), "text": root_text[:140_000], "method": "HTML text extraction"})

                for a in soup.find_all("a", href=True):
                    label = _safe_text(a.get_text(" ", strip=True))
                    absolute = urldefrag(urljoin(root_url, a.get("href", "")))[0]
                    if not absolute.startswith(("http://", "https://")) or not _same_domain(absolute, root_domain):
                        continue
                    priority = _link_priority(label, absolute)
                    if priority <= 0 or absolute in seen_urls:
                        continue
                    seen_urls.add(absolute)
                    candidate_urls.append((priority, absolute, label))
            except Exception as exc:
                attempts.append({
                    "URL": root_url,
                    "Domain": root_domain,
                    "Status": f"Fetch failed: {exc}",
                    "Method": "HTML root discovery",
                    "Source Grade": source_grade_from_url(root_url, symbol),
                })

    remaining = max(0, int(max_documents) - len(documents))
    for _, url, label in sorted(candidate_urls, key=lambda x: (-x[0], x[1]))[:remaining]:
        text, method = fetch_document_text(url, timeout_seconds=timeout_seconds, max_pages=35, max_chars=140_000)
        attempts.append({
            "URL": url,
            "Domain": _domain(url),
            "Status": "Fetched" if text else "Empty/failed",
            "Method": method,
            "Source Grade": source_grade_from_url(url, symbol),
        })
        if text:
            documents.append({"url": url, "title": label or url, "text": text, "method": method})
        if len(documents) >= max_documents:
            break

    attempts_df = pd.DataFrame(attempts, columns=ATTEMPT_COLUMNS)
    note = f"{symbol}: attempted {len(attempts_df)} official/company URLs; retained {len(documents)} text documents."
    return documents, attempts_df, note


def evidence_quality_summary(candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for question in QUESTION_ORDER:
        sub = (
            candidates[candidates["Question"].eq(question)]
            if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Question" in candidates.columns
            else pd.DataFrame()
        )
        grades = sub.get("Source Grade", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        directions = sub.get("Direction", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        rows.append({
            "Question": question,
            "Candidates": int(len(sub)),
            "A — Official": int(grades.str.startswith("A —").sum()) if not grades.empty else 0,
            "B — Independent": int(grades.str.startswith("B —").sum()) if not grades.empty else 0,
            "C — Secondary": int(grades.str.startswith("C —").sum()) if not grades.empty else 0,
            "Supporting cues": int(directions.str.startswith("Supporting").sum()) if not directions.empty else 0,
            "Counter-evidence cues": int(directions.str.startswith("Counter").sum()) if not directions.empty else 0,
            "Boundary": "Coverage only — not a management score",
        })
    return pd.DataFrame(rows)


def research_gaps(candidates: pd.DataFrame, manager_reference: pd.DataFrame | None = None) -> pd.DataFrame:
    tasks = {
        "Q39": "Collect original disclosures covering customers, employees, suppliers, shareholders, partners and other material stakeholders; keep counter-evidence.",
        "Q40": "Verify continuous-improvement practices versus strategic-plan/transformation evidence, including frontline feedback and adaptation.",
        "Q41": "Verify issued/revised/withdrawn guidance from dated original disclosures; enter numeric target/actual only when explicitly disclosed.",
        "Q42": "Map decision rights, delegation/autonomy, escalation controls and business-unit/customer proximity; analyst determines structure.",
        "Q43": "Research all fourteen Shearn employee-relation prompts where disclosed, including retention, promotion, training, culture and treatment.",
        "Q44": "Verify internal/external hiring, succession, selection process, challenge/candor evidence and observed outcomes.",
        "Q45": "Verify cost actions together with customer/employee impact, core investment preserved and restructuring/one-off context.",
        "Q46": "Research the five Shearn uses of excess FCF and explicit hurdle/discipline evidence; do not create a sixth debt-paydown bucket.",
        "Q47": "Verify explicit authorization/execution, shares/cash/price and valuation/liquidity context; do not infer a buyback from share-count change.",
    }
    rows: list[dict[str, Any]] = []
    manager_empty = not isinstance(manager_reference, pd.DataFrame) or manager_reference.empty
    for question in QUESTION_ORDER:
        sub = (
            candidates[candidates["Question"].eq(question)]
            if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Question" in candidates.columns
            else pd.DataFrame()
        )
        if sub.empty:
            rows.append({
                "Question": question,
                "Manager ID": "",
                "Manager": "",
                "Research Gap": "No usable evidence candidate found in this run.",
                "Materiality": "Analyst decide",
                "Next Action": tasks[question],
                "Status": "Open — evidence gap",
                "Analyst Note": "",
            })
        elif not sub["Source Grade"].astype(str).str.startswith("A —").any():
            rows.append({
                "Question": question,
                "Manager ID": "",
                "Manager": "",
                "Research Gap": "No A-quality company/exchange/regulator evidence candidate yet.",
                "Materiality": "Analyst decide",
                "Next Action": tasks[question],
                "Status": "Open — source-quality gap",
                "Analyst Note": "",
            })

        if manager_empty and question in {"Q41", "Q44", "Q46", "Q47"}:
            rows.append({
                "Question": question,
                "Manager ID": "",
                "Manager": "",
                "Research Gap": f"{MANAGER_SOURCE_LABEL} is empty/unavailable, so manager-targeted research cannot be reliably scoped.",
                "Materiality": "High",
                "Next Action": "Confirm manager identities in Chapter 7 first, then rerun Phase 8C; do not create replacement manager IDs in Chapter 8.",
                "Status": "Open — manager identity gap",
                "Analyst Note": "",
            })
    return pd.DataFrame(rows, columns=ch8.RESEARCH_GAP_COLUMNS)


class Chapter8ResearchAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def search(
        self,
        ticker: str,
        company_name: str = "",
        *,
        chapter7_payload: dict[str, Any] | None = None,
        max_results_per_query: int = 2,
        max_official_documents: int = 18,
    ) -> Chapter8ResearchResult:
        symbol = str(ticker or "").upper().strip()
        manager_reference = build_manager_reference(chapter7_payload)
        manager_names = (
            manager_reference.get("Manager", pd.Series(dtype="object")).dropna().astype(str).tolist()
            if not manager_reference.empty
            else []
        )
        pieces: list[pd.DataFrame] = []
        raw_paths: list[str] = []
        notes: list[str] = []

        try:
            documents, attempts, official_note = discover_official_documents(
                symbol, max_documents=max_official_documents
            )
            notes.append(official_note)
            direct = official_documents_to_candidates(documents, symbol, manager_reference)
            if not direct.empty:
                pieces.append(direct)
        except Exception as exc:
            documents = []
            attempts = pd.DataFrame(columns=ATTEMPT_COLUMNS)
            notes.append(f"Official/company discovery failed safely: {exc}")

        for focus in QUESTION_ORDER:
            try:
                agent = _FocusedChapter8Agent(self.raw_dir, focus, manager_names)
                result = agent.search(symbol, company_name, max_results_per_query=max_results_per_query)
                candidate = classify_search_rows(result.table.copy(), symbol, focus, manager_reference)
                if not candidate.empty:
                    pieces.append(candidate)
                if result.raw_path:
                    raw_paths.append(str(result.raw_path))
                notes.append(f"{focus}: {result.note}")
            except Exception as exc:
                notes.append(f"{focus}: focused research failed safely: {exc}")

        frame = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=CANDIDATE_COLUMNS)
        if not frame.empty:
            frame = frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)
        quality = evidence_quality_summary(frame)
        gaps = research_gaps(frame, manager_reference)
        return Chapter8ResearchResult(
            candidates=frame,
            quality=quality,
            gaps=gaps,
            manager_reference=manager_reference,
            source_attempts=attempts,
            raw_paths=raw_paths,
            note=" | ".join(notes),
        )
