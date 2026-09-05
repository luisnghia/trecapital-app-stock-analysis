from __future__ import annotations

"""Chapter 7 Phase 7C — Management Evidence & Research Assistant.

This module searches and extracts *candidate* evidence for Michael Shearn Q33–Q38.
It is deliberately evidence-only: no automatic OO/LT/HH classification, no Lion/Hyena
classification or score, no Management Quality conclusion, no Research Gate/MOS, and no
BUY/HOLD/SELL. Candidate evidence reaches the persisted Chapter-7 Evidence Matrix only after
an explicit analyst promote action.
"""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
import re

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS, WebEvidenceAgent


QUESTION_ORDER = ("Q33", "Q34", "Q35", "Q36", "Q37", "Q38")
RESEARCH_BOUNDARY = (
    "No automatic OO/LT/HH, Lion/Hyena or Management Quality conclusion; no automatic insider "
    "buy/sell signal; no MOS, Research Gate or BUY/HOLD/SELL. Analyst promotion is required."
)

FOCUS_TERMS: dict[str, tuple[str, ...]] = {
    "Q33": (
        "founder", "sáng lập", "chairman", "chủ tịch", "chief executive", "ceo", "tổng giám đốc",
        "management", "ban lãnh đạo", "appointed", "bổ nhiệm", "joined", "gia nhập", "ownership", "sở hữu",
    ),
    "Q34": (
        "appointed", "bổ nhiệm", "external", "outsider", "from", "gia nhập", "transition", "chuyển giao",
        "restructuring", "tái cấu trúc", "cost cutting", "cắt giảm", "strategy", "chiến lược", "culture", "văn hóa",
        "employee", "nhân viên", "customer", "khách hàng",
    ),
    "Q35": (
        "ethics", "đạo đức", "integrity", "liêm chính", "long-term", "dài hạn", "employee", "nhân viên",
        "partner", "đối tác", "learning", "học hỏi", "perseverance", "kiên trì", "shortcut", "lối tắt",
        "governance", "quản trị", "violation", "vi phạm", "sanction", "xử phạt",
    ),
    "Q36": (
        "biography", "tiểu sử", "career", "sự nghiệp", "experience", "kinh nghiệm", "previously", "trước đây",
        "appointed", "bổ nhiệm", "joined", "gia nhập", "director", "giám đốc", "manager", "quản lý",
    ),
    "Q37": (
        "compensation", "remuneration", "thù lao", "lương", "bonus", "thưởng", "esop", "option", "rsu",
        "restricted stock", "share award", "cổ phiếu thưởng", "ownership", "sở hữu", "shares held", "cổ phiếu nắm giữ",
        "vesting", "performance metric", "kpi",
    ),
    "Q38": (
        "insider", "người nội bộ", "related person", "người liên quan", "transaction", "giao dịch", "registered",
        "đăng ký mua", "đăng ký bán", "executed", "đã mua", "đã bán", "purchase", "sale", "buy", "sell",
        "ownership before", "ownership after", "sở hữu trước", "sở hữu sau",
    ),
}

QUERY_TERMS: dict[str, tuple[str, str]] = {
    "Q33": (
        "ban lãnh đạo tổng giám đốc chủ tịch sáng lập sở hữu bổ nhiệm",
        "management CEO chairman founder ownership appointment biography",
    ),
    "Q34": (
        "bổ nhiệm tổng giám đốc từ bên ngoài tái cấu trúc chiến lược văn hóa nhân sự",
        "external CEO appointment transition restructuring strategy culture employees customers",
    ),
    "Q35": (
        "ban lãnh đạo đạo đức liêm chính nhân viên đối tác dài hạn quản trị vi phạm",
        "management ethics integrity employees partners long-term governance violation sanction",
    ),
    "Q36": (
        "tiểu sử ban lãnh đạo kinh nghiệm sự nghiệp bổ nhiệm quá trình công tác",
        "management biography career experience appointed previous company executive profile",
    ),
    "Q37": (
        "thù lao ban điều hành lương thưởng ESOP quyền chọn sở hữu cổ phiếu",
        "executive compensation remuneration bonus ESOP options ownership shares held",
    ),
    "Q38": (
        "người nội bộ đăng ký mua bán cổ phiếu kết quả giao dịch sở hữu trước sau",
        "insider transaction registered purchase sale executed ownership before after",
    ),
}

SUBTOPICS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "Q33": (
        ("Leadership identity / role", ("chief executive", "ceo", "tổng giám đốc", "chairman", "chủ tịch")),
        ("Founder / owner background", ("founder", "sáng lập", "ownership", "sở hữu")),
        ("Appointment / tenure", ("appointed", "bổ nhiệm", "joined", "gia nhập")),
    ),
    "Q34": (
        ("Outside-management transition", ("external", "outsider", "transition", "chuyển giao", "bổ nhiệm")),
        ("Early actions / restructuring", ("restructuring", "tái cấu trúc", "cost cutting", "cắt giảm", "strategy", "chiến lược")),
        ("Culture / stakeholder learning", ("culture", "văn hóa", "employee", "nhân viên", "customer", "khách hàng")),
    ),
    "Q35": (
        ("Ethics / integrity", ("ethics", "đạo đức", "integrity", "liêm chính", "violation", "vi phạm", "sanction")),
        ("Long-term / shortcuts", ("long-term", "dài hạn", "shortcut", "lối tắt")),
        ("Learning / partners / employees", ("learning", "học hỏi", "partner", "đối tác", "employee", "nhân viên")),
    ),
    "Q36": (
        ("Career chronology", ("career", "sự nghiệp", "biography", "tiểu sử", "previously", "trước đây")),
        ("Operating / functional experience", ("experience", "kinh nghiệm", "director", "giám đốc", "manager", "quản lý")),
    ),
    "Q37": (
        ("Cash compensation", ("compensation", "remuneration", "thù lao", "lương", "bonus", "thưởng")),
        ("Equity awards", ("esop", "option", "rsu", "restricted stock", "share award", "cổ phiếu thưởng")),
        ("Actual ownership", ("ownership", "sở hữu", "shares held", "cổ phiếu nắm giữ")),
    ),
    "Q38": (
        ("Registered insider transaction", ("registered", "đăng ký mua", "đăng ký bán")),
        ("Executed insider transaction", ("executed", "đã mua", "đã bán", "purchase", "sale", "buy", "sell")),
        ("Ownership before / after", ("ownership before", "ownership after", "sở hữu trước", "sở hữu sau")),
    ),
}

# These are research cues only. They never produce a management classification.
COUNTER_CUES = (
    "violation", "vi phạm", "sanction", "xử phạt", "fraud", "gian lận", "restatement", "từ chức",
    "resigned", "dismissed", "miễn nhiệm", "lawsuit", "khởi kiện", "penalty", "phạt", "conflict of interest",
    "xung đột lợi ích", "failed to execute", "không thực hiện", "không hoàn tất giao dịch",
)
SUPPORTING_CUES = (
    "long-term", "dài hạn", "integrity", "liêm chính", "employee development", "phát triển nhân viên",
    "customer focus", "khách hàng", "direct purchase", "mua trực tiếp", "open market purchase",
)

CANDIDATE_COLUMNS = [
    "Select",
    "Candidate ID",
    "Question",
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


@dataclass
class Chapter7ResearchResult:
    candidates: pd.DataFrame
    raw_paths: list[str]
    note: str


def _safe_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _known_company_domains(ticker: str) -> set[str]:
    out: set[str] = set()
    for url in KNOWN_COMPANY_DOMAINS.get(str(ticker).upper().strip(), []):
        domain = WebEvidenceAgent._domain(url)
        if domain:
            out.add(domain)
    return out


def source_grade(row: dict[str, Any], ticker: str) -> str:
    domain = _safe_text(row.get("Tên miền") or row.get("Domain")).lower().replace("www.", "")
    group = _safe_text(row.get("Nhóm thông tin") or row.get("Source Group"))
    known = _known_company_domains(ticker)
    if any(domain == d or domain.endswith("." + d) for d in known):
        return "A — Company/Official disclosure"
    if "Nguồn công bố chính thức" in group or "Nguồn doanh nghiệp/IR" in group:
        return "A — Company/Official disclosure"
    if "Dữ liệu/tin tài chính" in group:
        return "B — Independent financial source/research"
    return "C — Secondary/context source"


def _subtopic(question: str, text: str) -> str:
    low = text.casefold()
    for label, terms in SUBTOPICS.get(question, ()):
        if any(term.casefold() in low for term in terms):
            return label
    return "General management evidence"


def direction_cue(question: str, text: str) -> str:
    """Return a non-conclusive evidence cue; never a Lion/Hyena or manager classification."""
    low = text.casefold()
    counter = sum(1 for term in COUNTER_CUES if term.casefold() in low)
    supporting = sum(1 for term in SUPPORTING_CUES if term.casefold() in low)
    if counter > supporting and counter > 0:
        return "Counter-evidence cue — analyst assess"
    if supporting > counter and supporting > 0:
        return "Supporting cue — analyst assess"
    return "Neutral / context — analyst assess"


def _year_candidate(text: str) -> str:
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text or "")
    return years[-1] if years else ""


def _manager_from_text(text: str, managers: Iterable[str]) -> str:
    low = text.casefold()
    for manager in managers:
        name = _safe_text(manager)
        if name and name.casefold() in low:
            return name
    return ""


def _candidate_id(*parts: Any) -> str:
    payload = "\x1f".join(_safe_text(x) for x in parts)
    return sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:16]


class _FocusedManagementAgent(WebEvidenceAgent):
    def __init__(self, raw_dir: str | Path, focus: str, managers: list[str] | None = None):
        super().__init__(raw_dir)
        self.focus = focus
        self.managers = [_safe_text(x) for x in (managers or []) if _safe_text(x)]

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:
        clean = self._clean_company_name(company_name)
        name = clean or company_name or ticker
        manager = self.managers[0] if self.managers else ""
        vi, en = QUERY_TERMS[self.focus]
        manager_vi = f' "{manager}"' if manager else ""
        return [
            f'"{ticker}" "{name}"{manager_vi} {vi}',
            f'"{ticker}" "{name}"{manager_vi} {en}',
        ]


def classify_search_rows(raw: pd.DataFrame, ticker: str, focus: str, managers: list[str] | None = None) -> pd.DataFrame:
    """Classify title/snippet rows only; query text itself is never treated as evidence."""
    if focus not in QUESTION_ORDER or not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]
    rows: list[dict[str, Any]] = []
    for _, item in raw.iterrows():
        source = item.to_dict()
        status = _safe_text(source.get("Trạng thái"))
        if status not in {"Tìm thấy", "Evidence trích từ nguồn chính thức", "Evidence trích từ PDF chính thức", "Link nguồn ưu tiên"}:
            continue
        title = _safe_text(source.get("Tiêu đề"))
        snippet = _safe_text(source.get("Trích yếu"))
        url = _safe_text(source.get("Nguồn/URL"))
        text = _safe_text(f"{title} {snippet}")
        if not text and not url:
            continue
        low = text.casefold()
        grade = source_grade(source, ticker)
        term_match = any(term.casefold() in low for term in FOCUS_TERMS[focus])
        manager_match = bool(_manager_from_text(text, manager_names))
        # Generic direct official pages are useful source leads, but must not masquerade as extracted evidence.
        is_source_lead = status == "Link nguồn ưu tiên" and grade.startswith("A —")
        if not term_match and not manager_match and not is_source_lead:
            continue
        manager = _manager_from_text(text, manager_names)
        explicitness = "Source lead — open/verify" if is_source_lead and not term_match else "Explicit title/snippet candidate"
        candidate_id = _candidate_id(focus, manager, url, snippet, title, explicitness)
        rows.append({
            "Select": False,
            "Candidate ID": candidate_id,
            "Question": focus,
            "Manager": manager,
            "Subtopic": _subtopic(focus, text),
            "Direction": direction_cue(focus, text),
            "Source Grade": grade,
            "Explicitness": explicitness,
            "Source Title": title[:240],
            "Source URL / File": url,
            "Source Date": "",
            "As-of Date": _year_candidate(text),
            "Evidence Text / Reference": snippet[:900],
            "Source Method": "Phase 7C focused web research",
            "Data Origin": "External research candidate — analyst verification required",
            "Status": "Candidate — analyst verify",
        })
    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["Question", "Manager", "Source URL / File", "Evidence Text / Reference"], keep="first").reset_index(drop=True)


class Chapter7ResearchAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def search(
        self,
        ticker: str,
        company_name: str = "",
        managers: list[str] | None = None,
        max_results_per_query: int = 3,
    ) -> Chapter7ResearchResult:
        pieces: list[pd.DataFrame] = []
        raw_paths: list[str] = []
        notes: list[str] = []
        manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]
        for focus in QUESTION_ORDER:
            agent = _FocusedManagementAgent(self.raw_dir, focus, manager_names)
            result = agent.search(ticker, company_name, max_results_per_query=max_results_per_query)
            raw = result.table.copy()
            candidate = classify_search_rows(raw, ticker, focus, manager_names)
            if not candidate.empty:
                pieces.append(candidate)
            if result.raw_path:
                raw_paths.append(str(result.raw_path))
            notes.append(f"{focus}: {result.note}")
        frame = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=CANDIDATE_COLUMNS)
        if not frame.empty:
            frame = frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)
        return Chapter7ResearchResult(frame, raw_paths, " | ".join(notes))


def evidence_quality_summary(candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for question in QUESTION_ORDER:
        sub = candidates[candidates["Question"].eq(question)] if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Question" in candidates.columns else pd.DataFrame()
        grades = sub.get("Source Grade", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        directions = sub.get("Direction", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        rows.append({
            "Question": question,
            "Candidates": int(len(sub)),
            "A — Official": int(grades.str.startswith("A —").sum()) if not grades.empty else 0,
            "B — Independent": int(grades.str.startswith("B —").sum()) if not grades.empty else 0,
            "C — Secondary": int(grades.str.startswith("C —").sum()) if not grades.empty else 0,
            "Counter-evidence cues": int(directions.str.startswith("Counter-evidence").sum()) if not directions.empty else 0,
            "Boundary": "Coverage only — not a management score",
        })
    return pd.DataFrame(rows)


def research_gaps(candidates: pd.DataFrame, managers: list[str] | None = None) -> pd.DataFrame:
    manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]
    tasks = {
        "Q33": "Verify current leader identity, appointment/tenure, founder/family/internal/external background and actual ownership from original disclosures.",
        "Q34": "If outside management applies, verify prior-industry/customer overlap, first major actions, culture/stakeholder learning and early outcomes. Otherwise document N/A basis.",
        "Q35": "Collect both supporting and counter-evidence across all seven Table 7.1 dimensions; do not infer Lion/Hyena from absence of evidence.",
        "Q36": "Build 5–10Y chronology for up to top five managers from official biographies/historical annual reports; keep unexplained gaps Unknown.",
        "Q37": "Verify compensation components, performance horizon and actual shares separately from options/RSU/ESOP/unvested awards for 5–10Y when disclosed.",
        "Q38": "Verify registered vs executed insider trades, dates, before/after ownership and transaction type from exchange/company/SSC disclosures.",
    }
    rows: list[dict[str, Any]] = []
    for question in QUESTION_ORDER:
        sub = candidates[candidates["Question"].eq(question)] if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Question" in candidates.columns else pd.DataFrame()
        if sub.empty:
            rows.append({
                "Question": question,
                "Manager ID": "",
                "Manager": manager_names[0] if manager_names else "",
                "Research Gap": "No usable external evidence candidate found in this run.",
                "Materiality": "Analyst decide",
                "Next Action": tasks[question],
                "Status": "Open — evidence gap",
                "Analyst Note": "",
            })
            continue
        has_a = sub["Source Grade"].astype(str).str.startswith("A —").any()
        if not has_a:
            rows.append({
                "Question": question,
                "Manager ID": "",
                "Manager": manager_names[0] if manager_names else "",
                "Research Gap": "No A-quality company/official disclosure candidate yet.",
                "Materiality": "Analyst decide",
                "Next Action": tasks[question],
                "Status": "Open — source-quality gap",
                "Analyst Note": "",
            })
    if not manager_names:
        rows.append({
            "Question": "Q36",
            "Manager ID": "",
            "Manager": "",
            "Research Gap": "Management Profile is empty, so top-5 manager-targeted chronology research cannot be scoped reliably.",
            "Materiality": "High",
            "Next Action": "Populate/confirm Management Profile identities, then rerun Phase 7C.",
            "Status": "Open — identity gap",
            "Analyst Note": "",
        })
    return pd.DataFrame(rows)


def _plain_html_text(content: bytes) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return _safe_text(soup.get_text(" ", strip=True))


def fetch_document_text(url: str, timeout_seconds: float = 6.0, max_pages: int = 40, max_chars: int = 180_000) -> tuple[str, str]:
    """Fetch a public HTML/PDF source. No OCR and no inference; returns extracted text + method."""
    clean_url = _safe_text(url)
    if not clean_url.startswith(("http://", "https://")):
        return "", "Unsupported/empty URL"
    try:
        with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(timeout_seconds, connect=min(3.0, timeout_seconds)), follow_redirects=True) as client:
            response = client.get(clean_url)
            response.raise_for_status()
        content_type = _safe_text(response.headers.get("content-type")).lower()
        content = response.content
        is_pdf = "pdf" in content_type or clean_url.lower().split("?")[0].endswith(".pdf") or content[:4] == b"%PDF"
        if is_pdf:
            reader = PdfReader(BytesIO(content))
            parts: list[str] = []
            for page in reader.pages[:max_pages]:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    continue
                if sum(len(x) for x in parts) >= max_chars:
                    break
            return _safe_text(" ".join(parts))[:max_chars], "PDF text extraction (no OCR)"
        return _plain_html_text(content)[:max_chars], "HTML text extraction"
    except Exception as exc:
        return "", f"Fetch/extract failed: {exc}"


def _relevant_windows(text: str, question: str, managers: list[str] | None = None, *, window: int = 420, max_windows: int = 4) -> list[str]:
    clean = _safe_text(text)
    if not clean:
        return []
    low = clean.casefold()
    needles = list(FOCUS_TERMS.get(question, ())) + [_safe_text(x) for x in (managers or []) if _safe_text(x)]
    positions: list[int] = []
    for needle in needles:
        pos = low.find(needle.casefold())
        if pos >= 0:
            positions.append(pos)
    positions = sorted(dict.fromkeys(positions))
    out: list[str] = []
    for pos in positions[:max_windows]:
        start = max(0, pos - window)
        end = min(len(clean), pos + window)
        snippet = _safe_text(clean[start:end])
        if snippet and snippet not in out:
            out.append(snippet[:900])
    return out


def deep_extract_candidates(candidates: pd.DataFrame, selected_ids: Iterable[str], managers: list[str] | None = None, max_sources: int = 8) -> pd.DataFrame:
    """Deep-extract selected public PDF/HTML sources into additional analyst-verification candidates."""
    if not isinstance(candidates, pd.DataFrame) or candidates.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    selected = {str(x) for x in selected_ids if str(x)}
    if not selected:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    source_rows = candidates[candidates["Candidate ID"].astype(str).isin(selected)].head(max_sources)
    out: list[dict[str, Any]] = []
    manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]
    for _, row in source_rows.iterrows():
        item = row.to_dict()
        url = _safe_text(item.get("Source URL / File"))
        question = _safe_text(item.get("Question"))
        if question not in QUESTION_ORDER or not url:
            continue
        text, method = fetch_document_text(url)
        if not text:
            continue
        for idx, snippet in enumerate(_relevant_windows(text, question, manager_names)):
            manager = _manager_from_text(snippet, manager_names) or _safe_text(item.get("Manager"))
            cid = _candidate_id(question, manager, url, snippet, "deep", idx)
            out.append({
                "Select": False,
                "Candidate ID": cid,
                "Question": question,
                "Manager": manager,
                "Subtopic": _subtopic(question, snippet),
                "Direction": direction_cue(question, snippet),
                "Source Grade": _safe_text(item.get("Source Grade")),
                "Explicitness": "Extracted source text candidate — analyst verify",
                "Source Title": _safe_text(item.get("Source Title"))[:240],
                "Source URL / File": url,
                "Source Date": _safe_text(item.get("Source Date")),
                "As-of Date": _year_candidate(snippet) or _safe_text(item.get("As-of Date")),
                "Evidence Text / Reference": snippet[:900],
                "Source Method": f"Phase 7C deep extraction — {method}",
                "Data Origin": "External PDF/HTML source text — analyst verification required",
                "Status": "Candidate — analyst verify",
            })
    frame = pd.DataFrame(out, columns=CANDIDATE_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)


def _manager_id_map(record: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in record.get("management_profiles") or []:
        if not isinstance(row, dict):
            continue
        name = _safe_text(row.get("Manager"))
        if name:
            out[name.casefold()] = _safe_text(row.get("Manager ID"))
    return out


def promote_candidates_into_record(
    record: dict[str, Any],
    candidates: pd.DataFrame,
    selected_ids: Iterable[str],
    gaps: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Promote selected evidence/gaps only. Analyst-owned assessments are copied unchanged."""
    out = deepcopy(record)
    selected = {str(x) for x in selected_ids if str(x)}
    manager_ids = _manager_id_map(out)
    evidence = out.get("evidence_matrix") if isinstance(out.get("evidence_matrix"), list) else []
    seen = {
        (
            _safe_text(r.get("Question")),
            _safe_text(r.get("Manager")),
            _safe_text(r.get("Source URL / File")),
            _safe_text(r.get("Evidence Text / Reference")),
        )
        for r in evidence if isinstance(r, dict)
    }
    promoted = 0
    duplicates = 0
    if isinstance(candidates, pd.DataFrame) and not candidates.empty:
        subset = candidates[candidates["Candidate ID"].astype(str).isin(selected)] if selected else candidates.iloc[0:0]
        for _, row in subset.iterrows():
            item = row.to_dict()
            manager = _safe_text(item.get("Manager"))
            mapped = {
                "Question": _safe_text(item.get("Question")),
                "Manager ID": manager_ids.get(manager.casefold(), ""),
                "Manager": manager,
                "Claim": _safe_text(item.get("Subtopic")) or "Management evidence candidate",
                "Evidence Type": "External research candidate",
                "Source Grade": _safe_text(item.get("Source Grade")),
                "Source Title": _safe_text(item.get("Source Title")),
                "Source URL / File": _safe_text(item.get("Source URL / File")),
                "Source Date": _safe_text(item.get("Source Date")),
                "As-of Date": _safe_text(item.get("As-of Date")),
                "Evidence Text / Reference": _safe_text(item.get("Evidence Text / Reference")),
                "Direction": _safe_text(item.get("Direction")),
                "Status": "Promoted candidate — analyst verify",
                "Data Origin": _safe_text(item.get("Data Origin")) or "Phase 7C Research Assistant",
                "Analyst Note": "",
            }
            key = (mapped["Question"], mapped["Manager"], mapped["Source URL / File"], mapped["Evidence Text / Reference"])
            if key in seen:
                duplicates += 1
                continue
            evidence.append(mapped)
            seen.add(key)
            promoted += 1
    out["evidence_matrix"] = evidence

    gaps_added = 0
    if isinstance(gaps, pd.DataFrame) and not gaps.empty:
        existing_gaps = out.get("research_gaps_table") if isinstance(out.get("research_gaps_table"), list) else []
        gap_seen = {
            (_safe_text(r.get("Question")), _safe_text(r.get("Manager")), _safe_text(r.get("Research Gap")))
            for r in existing_gaps if isinstance(r, dict)
        }
        for _, row in gaps.iterrows():
            item = row.to_dict()
            key = (_safe_text(item.get("Question")), _safe_text(item.get("Manager")), _safe_text(item.get("Research Gap")))
            if key in gap_seen:
                continue
            existing_gaps.append({k: item.get(k, "") for k in [
                "Question", "Manager ID", "Manager", "Research Gap", "Materiality", "Next Action", "Status", "Analyst Note"
            ]})
            gap_seen.add(key)
            gaps_added += 1
        out["research_gaps_table"] = existing_gaps

    return out, {"promoted": promoted, "duplicates": duplicates, "gaps_added": gaps_added}


__all__ = [
    "CANDIDATE_COLUMNS",
    "Chapter7ResearchAgent",
    "Chapter7ResearchResult",
    "QUESTION_ORDER",
    "RESEARCH_BOUNDARY",
    "classify_search_rows",
    "deep_extract_candidates",
    "direction_cue",
    "evidence_quality_summary",
    "fetch_document_text",
    "promote_candidates_into_record",
    "research_gaps",
    "source_grade",
]
