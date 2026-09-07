from __future__ import annotations

"""Chapter 9 Phase 9D — Evidence Research Assistant for Q48-Q52.

This module follows the existing Chapter 7/8 research-assistant pattern and turns the
source-locked Chapter 9 contract into *candidate evidence* only.

Boundaries
----------
- Michael Shearn Chapter 9 Q48-Q52 and the 26 Phase 9B dimensions remain the source contract.
- Chapter 7 remains the manager identity/background single source of truth (SSOT).
- Phase 9C supplies manager/CEO scoping; this module never creates replacement manager IDs.
- Search snippets are candidates, not facts. Original source text is preferred when available.
- Direction labels are research cues only and never a positive/negative management conclusion.
- No automatic management score, rank, character classification, MOS, Research Gate,
  BUY/HOLD/SELL, database persistence, or Streamlit/UI behavior is introduced here.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
import re

import pandas as pd

from adapters.module2_web_research import KNOWN_COMPANY_DOMAINS, WebEvidenceAgent
import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_data_bridge as bridge
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract
from modules.deep_company_analysis.chapter8_research import (
    ATTEMPT_COLUMNS,
    discover_official_documents,
    source_grade_from_url,
)


QUESTION_ORDER = ch9.QUESTION_KEYS
RESEARCH_BOUNDARY = (
    "Evidence candidates only — analyst verification/promotion required; no automatic management "
    "quality/character conclusion, no score/rank, no MOS/Research Gate, and no BUY/HOLD/SELL."
)

# Terms are operational search/matching vocabulary derived from the Phase 9B source dimensions.
# They are not extra checklist criteria and do not change the source-locked question set.
DIMENSION_TERMS: dict[str, tuple[str, ...]] = {
    "q48_career_vs_job": (
        "career", "sự nghiệp", "nghề nghiệp", "joined", "gia nhập", "founded", "sáng lập",
        "industry experience", "kinh nghiệm ngành", "career history", "quá trình công tác",
    ),
    "q48_refuse_sale": (
        "refused to sell", "refuse to sell", "rejected acquisition", "rejected takeover",
        "sale offer", "acquisition offer", "takeover offer", "đề nghị mua lại", "từ chối bán",
        "không bán công ty", "thâu tóm", "mua lại doanh nghiệp",
    ),
    "q48_money_motivation": (
        "compensation", "remuneration", "wealth", "lifestyle", "spending", "salary", "bonus",
        "thù lao", "lương thưởng", "tài sản cá nhân", "mức sống", "chi tiêu", "ownership stake",
    ),
    "q48_appearances_vs_business": (
        "outside board", "external board", "social engagement", "public appearance", "celebrity",
        "prestige", "outside commitments", "hội đồng quản trị bên ngoài", "hoạt động xã hội",
        "sự kiện xã hội", "cam kết bên ngoài",
    ),
    "q48_philanthropy": (
        "philanthropy", "philanthropic", "foundation", "charity", "donation", "nonprofit", "non-profit",
        "từ thiện", "quỹ", "quỹ từ thiện", "quyên góp", "thiện nguyện", "trách nhiệm cộng đồng",
    ),
    "q48_lifelong_learning": (
        "continuous improvement", "lifelong learning", "learn continuously", "learning culture",
        "kaizen", "continuous learning", "cải tiến liên tục", "học hỏi liên tục", "học tập suốt đời",
        "đổi mới liên tục", "thích ứng công nghệ",
    ),
    "q49_words_actions_consistency": (
        "consistent with", "words and actions", "said and did", "followed through", "kept promise",
        "commitment", "cam kết", "nhất quán", "lời nói và hành động", "thực hiện cam kết",
        "không thực hiện cam kết", "contradictory action",
    ),
    "q49_integrity_moment": (
        "integrity", "ethical", "ethics", "honesty", "transparent", "responsibility", "accountability",
        "liêm chính", "đạo đức", "trung thực", "minh bạch", "chịu trách nhiệm", "nhận trách nhiệm",
        "conflict of interest", "xung đột lợi ích",
    ),
    "q49_adversity_response_pattern": (
        "crisis", "adversity", "downturn", "product recall", "lawsuit", "negative media", "incident",
        "khủng hoảng", "suy thoái", "thu hồi sản phẩm", "kiện tụng", "sự cố", "truyền thông tiêu cực",
        "response", "ứng phó",
    ),
    "q49_long_term_problem_solving": (
        "root cause", "long-term solution", "long term solution", "follow-up", "corrective action",
        "durable solution", "remediation", "nguyên nhân gốc rễ", "giải pháp dài hạn", "khắc phục",
        "theo dõi sau", "biện pháp khắc phục",
    ),
    "q50_shareholder_letters": (
        "shareholder letter", "letter to shareholders", "annual letter", "chairman's letter", "ceo letter",
        "thư cổ đông", "thư gửi cổ đông", "thông điệp tổng giám đốc", "thông điệp chủ tịch",
        "annual report", "báo cáo thường niên",
    ),
    "q50_conference_calls": (
        "conference call", "earnings call", "earnings transcript", "call transcript", "question and answer",
        "q&a", "investor call", "họp nhà đầu tư", "hội nghị nhà đầu tư", "hỏi đáp", "biên bản cuộc gọi",
    ),
    "q50_adversity_communication": (
        "communicated during", "crisis communication", "adversity communication", "apology", "acknowledged",
        "owned the mistake", "thông tin khủng hoảng", "xin lỗi", "thừa nhận", "nhận trách nhiệm",
        "công bố sự cố", "giải trình sự cố",
    ),
    "q50_good_news_balance": (
        "adjusted", "pro forma", "non-gaap", "underlying results", "bad news", "good news", "one-off",
        "điều chỉnh", "lợi nhuận điều chỉnh", "số liệu pro forma", "tin xấu", "tin tốt", "bất thường",
        "loại trừ", "không bao gồm",
    ),
    "q50_easy_to_listen": (
        "clear explanation", "plain language", "easy to understand", "straightforward", "clear communication",
        "giải thích rõ", "dễ hiểu", "ngôn ngữ rõ ràng", "trình bày mạch lạc", "thẳng thắn",
    ),
    "q50_learn_from_manager": (
        "explains the business", "operating insight", "business model explanation", "teaches", "educates investors",
        "giải thích mô hình kinh doanh", "hiểu hoạt động", "chia sẻ kiến thức", "giải thích vận hành",
        "insight", "operating model",
    ),
    "q50_corporate_speak": (
        "corporate speak", "corporate jargon", "jargon", "buzzword", "synergy", "transformational",
        "world class", "best in class", "ngôn ngữ sáo rỗng", "thuật ngữ doanh nghiệp", "khẩu hiệu",
    ),
    "q50_double_speak": (
        "double speak", "doublespeak", "contradictory statement", "contradiction", "inconsistent statement",
        "mâu thuẫn", "phát biểu trái ngược", "nói nước đôi", "không nhất quán trong phát biểu",
    ),
    "q51_resist_industry_copying": (
        "competitor", "peer", "industry trend", "follow competitors", "copy competitors", "did not follow",
        "đối thủ", "doanh nghiệp cùng ngành", "xu hướng ngành", "không chạy theo", "sao chép đối thủ",
    ),
    "q51_long_term_focus": (
        "long-term", "long term", "short-term pressure", "quarterly pressure", "shareholder pressure",
        "dài hạn", "áp lực ngắn hạn", "áp lực quý", "áp lực cổ đông", "đầu tư dài hạn",
    ),
    "q51_own_plan_vs_benchmark_copy": (
        "own strategy", "independent strategy", "distinct strategy", "benchmark competitors", "copycat",
        "customer needs", "chiến lược riêng", "chiến lược độc lập", "benchmark đối thủ", "bắt chước",
        "nhu cầu khách hàng", "khác biệt chiến lược",
    ),
    "q52_self_brand_and_pitch": (
        "personal brand", "self promotion", "self-promoting", "flamboyant", "charisma", "center of attention",
        "aggressive salesmanship", "larger than life", "thương hiệu cá nhân", "tự quảng bá", "hào nhoáng",
        "lôi cuốn", "trung tâm chú ý", "quảng bá mạnh",
    ),
    "q52_wall_street_event_frequency": (
        "investor conference", "broker conference", "sell-side conference", "roadshow", "investor event",
        "analyst conference", "hội nghị nhà đầu tư", "roadshow", "sự kiện nhà đầu tư", "hội nghị chứng khoán",
    ),
    "q52_media_touting": (
        "television", "tv interview", "financial press", "media interview", "press interview", "podcast interview",
        "truyền hình", "phỏng vấn báo chí", "phỏng vấn truyền thông", "báo tài chính", "xuất hiện truyền thông",
    ),
    "q52_stock_price_focus": (
        "stock price", "share price", "market capitalization", "market cap target", "share performance",
        "giá cổ phiếu", "thị giá", "vốn hóa", "mục tiêu giá cổ phiếu", "diễn biến cổ phiếu",
    ),
    "q52_financing_context": (
        "equity issuance", "share issuance", "debt issuance", "bond issuance", "capital raise", "fundraising",
        "acquisition financing", "expansion financing", "phát hành cổ phiếu", "phát hành trái phiếu",
        "huy động vốn", "tài trợ mua lại", "vốn mở rộng",
    ),
}

QUERY_TERMS: dict[str, tuple[str, str]] = {
    "Q48": (
        "CEO sự nghiệp động cơ tiền bạc từ thiện cải tiến liên tục đề nghị mua lại hoạt động xã hội",
        "CEO career motivation money philanthropy continuous improvement sale offer lifestyle outside boards",
    ),
    "Q49": (
        "CEO ban lãnh đạo liêm chính khủng hoảng sự cố trách nhiệm cam kết giải pháp dài hạn",
        "CEO management integrity crisis adversity accountability commitments long-term solution response",
    ),
    "Q50": (
        "CEO thư cổ đông báo cáo thường niên họp nhà đầu tư hỏi đáp giao tiếp khủng hoảng lợi nhuận điều chỉnh",
        "CEO shareholder letter annual report conference call Q&A communication adversity adjusted pro forma jargon",
    ),
    "Q51": (
        "ban lãnh đạo chiến lược độc lập đối thủ dài hạn áp lực cổ đông không chạy theo ngành",
        "management independent strategy competitors peers long-term shareholder pressure industry copying",
    ),
    "Q52": (
        "CEO tự quảng bá hội nghị nhà đầu tư truyền thông giá cổ phiếu huy động vốn roadshow",
        "CEO self promotion investor conference media stock price roadshow financing equity debt acquisition",
    ),
}

# These cues are deliberately non-conclusive. They only help the analyst sort candidates.
SUPPORTING_CUES = (
    "integrity", "liêm chính", "transparent", "minh bạch", "accepted responsibility", "nhận trách nhiệm",
    "long-term solution", "giải pháp dài hạn", "continuous improvement", "cải tiến liên tục",
    "refused to sell", "từ chối bán", "did not follow competitors", "không chạy theo",
    "plain language", "dễ hiểu", "openly communicated", "communicated openly",
)
COUNTER_CUES = (
    "blamed", "đổ lỗi", "lawyered", "pr-crafted", "quick fix", "short-term remedy", "che giấu",
    "violation", "vi phạm", "fraud", "gian lận", "penalty", "xử phạt", "contradictory", "mâu thuẫn",
    "self-promoting", "self promotion", "flamboyant", "aggressive salesmanship", "stock price target",
    "tự quảng bá", "hào nhoáng", "mục tiêu giá cổ phiếu", "corporate jargon", "double speak",
)
FINANCING_CONTEXT_CUES = (
    "equity issuance", "debt issuance", "bond issuance", "capital raise", "acquisition financing",
    "expansion financing", "phát hành cổ phiếu", "phát hành trái phiếu", "huy động vốn", "tài trợ mua lại",
)

CANDIDATE_COLUMNS = [
    "Select",
    "Candidate ID",
    "Question",
    "Dimension Key",
    "Dimension",
    "Manager ID",
    "Manager",
    "Current Role",
    "Source Family",
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

QUALITY_COLUMNS = [
    "Question",
    "Dimension Key",
    "Dimension",
    "Candidates",
    "A — Official",
    "B — Independent",
    "C — Context",
    "Direct-source text",
    "Manager-linked",
    "Supporting cues",
    "Counter cues",
    "Mixed cues",
    "Boundary",
]

RESEARCH_GAP_COLUMNS = bridge.SCOPE_GAP_COLUMNS


@dataclass
class Chapter9ResearchResult:
    candidates: pd.DataFrame
    quality: pd.DataFrame
    gaps: pd.DataFrame
    manager_reference: pd.DataFrame
    dimension_scope: pd.DataFrame
    source_attempts: pd.DataFrame
    raw_paths: list[str]
    note: str


def _safe_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _candidate_id(*parts: Any) -> str:
    payload = "\x1f".join(_safe_text(x) for x in parts)
    return sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _year_candidate(text: str) -> str:
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", _safe_text(text))
    return years[-1] if years else ""


def _dimension_map() -> dict[str, contract.SourceDimension]:
    return {dim.key: dim for dim in contract.all_dimensions()}


def matched_dimensions(question: str, text: str, *, max_dimensions: int = 3) -> list[str]:
    """Return the strongest source-dimension matches for a text fragment."""
    low = _safe_text(text).casefold()
    if question not in QUESTION_ORDER or not low:
        return []
    allowed = {dim.key for dim in contract.QUESTION_DIMENSIONS[question]}
    scored: list[tuple[int, int, str]] = []
    for key in allowed:
        terms = DIMENSION_TERMS.get(key, ())
        matched = [term for term in terms if term.casefold() in low]
        if matched:
            # Prefer more matches and then longer matched phrases to reduce generic-token noise.
            scored.append((len(matched), max(len(term) for term in matched), key))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [key for _, _, key in scored[: max(1, int(max_dimensions))]]


def _manager_scope_for_question(dimension_scope: pd.DataFrame | None, question: str) -> pd.DataFrame:
    if not isinstance(dimension_scope, pd.DataFrame) or dimension_scope.empty:
        return pd.DataFrame()
    out = dimension_scope[dimension_scope["Question"].eq(question)].copy()
    if out.empty:
        return out
    return out.drop_duplicates(subset=["Manager ID", "Manager", "Current Role"], keep="first")


def _manager_match(text: str, question: str, dimension_scope: pd.DataFrame | None) -> tuple[str, str, str]:
    scope = _manager_scope_for_question(dimension_scope, question)
    if scope.empty:
        return "", "", ""
    low = _safe_text(text).casefold()
    rows: list[tuple[str, str, str]] = []
    for _, row in scope.iterrows():
        name = _safe_text(row.get("Manager"))
        if name:
            rows.append((_safe_text(row.get("Manager ID")), name, _safe_text(row.get("Current Role"))))
    for manager_id, name, role in sorted(rows, key=lambda x: len(x[1]), reverse=True):
        if name.casefold() in low:
            return manager_id, name, role
    return "", "", ""


def source_family(question: str, text: str, url: str = "") -> str:
    low = f"{_safe_text(text)} {_safe_text(url)}".casefold()
    if question == "Q48":
        if any(x in low for x in ("philanth", "foundation", "charity", "nonprofit", "từ thiện", "quỹ")):
            return "Foundation/nonprofit/giving record"
        if any(x in low for x in ("interview", "profile", "biography", "tiểu sử", "phỏng vấn")):
            return "Published manager interview/profile"
        if any(x in low for x in ("career", "experience", "quá trình công tác", "sự nghiệp")):
            return "Proxy/background biography"
        return "Company/personal disclosure context"
    if question == "Q49":
        if any(x in low for x in ("conference call", "earnings call", "transcript", "họp nhà đầu tư")):
            return "Historical conference-call transcript"
        if any(x in low for x in ("press release", "thông cáo", "công bố thông tin", "cbtt")):
            return "Press release during event"
        if any(x in low for x in ("regulator", "exchange", "hsx", "hnx", "ssc", "ủy ban chứng khoán")):
            return "Regulatory/exchange filing"
        return "Historical adversity article/context"
    if question == "Q50":
        if any(x in low for x in ("shareholder letter", "letter to shareholders", "thư cổ đông")):
            return "Sequential shareholder letter"
        if any(x in low for x in ("conference call", "earnings call", "transcript", "q&a", "họp nhà đầu tư")):
            return "Historical conference-call transcript"
        if any(x in low for x in ("adjusted", "pro forma", "non-gaap", "lợi nhuận điều chỉnh")):
            return "Adjusted/pro-forma financial disclosure"
        if any(x in low for x in ("press release", "thông cáo", "công bố thông tin")):
            return "Press release/stakeholder communication"
        return "Annual report/shareholder communication"
    if question == "Q51":
        if any(x in low for x in ("interview", "phỏng vấn")):
            return "Manager interview explaining rationale"
        if any(x in low for x in ("competitor", "peer", "đối thủ", "cùng ngành")):
            return "Peer action/context"
        if any(x in low for x in ("shareholder", "cổ đông", "annual report", "báo cáo thường niên")):
            return "Shareholder communication"
        return "Documented strategic/operating decision"
    if question == "Q52":
        if any(x in low for x in ("investor conference", "roadshow", "sell-side", "sự kiện nhà đầu tư")):
            return "Investor-relations conference calendar/event"
        if any(x in low for x in ("television", "tv interview", "financial press", "media interview", "truyền hình", "báo chí")):
            return "Financial-press/TV appearance"
        if any(x in low for x in FINANCING_CONTEXT_CUES):
            return "Debt/equity/acquisition financing context"
        return "Annual report/shareholder-letter language"
    return "Source-contract evidence family"


def direction_cue(dimension_key: str, text: str) -> str:
    """Return a sorting cue only; never a character or management-quality conclusion."""
    low = _safe_text(text).casefold()
    if dimension_key == "q52_financing_context" and any(term.casefold() in low for term in FINANCING_CONTEXT_CUES):
        return "Context / exception cue — analyst assess"
    supporting = sum(1 for term in SUPPORTING_CUES if term.casefold() in low)
    counter = sum(1 for term in COUNTER_CUES if term.casefold() in low)
    if supporting and counter:
        return "Mixed cue — analyst assess"
    if counter:
        return "Counter-evidence cue — analyst assess"
    if supporting:
        return "Supporting cue — analyst assess"
    return "Neutral / context — analyst assess"


class _FocusedChapter9Agent(WebEvidenceAgent):
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
        domains: list[str] = []
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
    dimension_scope: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Convert search title/snippet rows to dimension-level candidates.

    Generic direct-source links and query strings are never treated as evidence.
    """
    if focus not in QUESTION_ORDER or not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    dim_map = _dimension_map()
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
        dimensions = matched_dimensions(focus, text)
        if not dimensions:
            continue
        manager_id, manager, role = _manager_match(text, focus, dimension_scope)
        for dimension_key in dimensions:
            dim = dim_map[dimension_key]
            rows.append(
                {
                    "Select": False,
                    "Candidate ID": _candidate_id(focus, dimension_key, manager_id, url, title, snippet),
                    "Question": focus,
                    "Dimension Key": dimension_key,
                    "Dimension": dim.label,
                    "Manager ID": manager_id,
                    "Manager": manager,
                    "Current Role": role,
                    "Source Family": source_family(focus, text, url),
                    "Direction": direction_cue(dimension_key, text),
                    "Source Grade": source_grade_from_url(url, ticker),
                    "Explicitness": "Search title/snippet candidate — analyst verify original source",
                    "Source Title": title[:240],
                    "Source URL / File": url,
                    "Source Date": "",
                    "As-of Date": _year_candidate(text),
                    "Evidence Text / Reference": snippet[:900],
                    "Source Method": "Phase 9D focused web research",
                    "Data Origin": "External research candidate — analyst verification required",
                    "Status": "Candidate — analyst verify",
                }
            )
    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)


def _relevant_windows(
    text: str,
    dimension_key: str,
    manager_names: Iterable[str] | None = None,
    *,
    window: int = 440,
    max_windows: int = 2,
) -> list[str]:
    clean = _safe_text(text)
    if not clean:
        return []
    low = clean.casefold()
    needles = list(DIMENSION_TERMS.get(dimension_key, ())) + [
        _safe_text(x) for x in (manager_names or []) if _safe_text(x)
    ]
    positions: list[int] = []
    for needle in needles:
        n = needle.casefold()
        if not n:
            continue
        start = 0
        while len(positions) < 60:
            pos = low.find(n, start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + max(1, len(n))
    if not positions:
        return []
    out: list[str] = []
    dimension_terms = DIMENSION_TERMS.get(dimension_key, ())
    for pos in sorted(set(positions)):
        snippet = _safe_text(clean[max(0, pos - window): min(len(clean), pos + window)])
        if not snippet:
            continue
        if not any(term.casefold() in snippet.casefold() for term in dimension_terms):
            continue
        if snippet not in out:
            out.append(snippet)
        if len(out) >= max_windows:
            break
    return out


def official_documents_to_candidates(
    documents: list[dict[str, Any]],
    ticker: str,
    dimension_scope: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Extract source-locked dimension windows from company/official documents."""
    dim_map = _dimension_map()
    rows: list[dict[str, Any]] = []
    for document in documents or []:
        text = _safe_text(document.get("text"))
        url = _safe_text(document.get("url"))
        if not text or not url:
            continue
        title = _safe_text(document.get("title")) or url
        method = _safe_text(document.get("method")) or "Official source extraction"
        for question in QUESTION_ORDER:
            scope = _manager_scope_for_question(dimension_scope, question)
            manager_names = scope.get("Manager", pd.Series(dtype="object")).dropna().astype(str).tolist() if not scope.empty else []
            for dim in contract.QUESTION_DIMENSIONS[question]:
                if not any(term.casefold() in text.casefold() for term in DIMENSION_TERMS.get(dim.key, ())):
                    continue
                for idx, snippet in enumerate(_relevant_windows(text, dim.key, manager_names)):
                    manager_id, manager, role = _manager_match(snippet, question, dimension_scope)
                    rows.append(
                        {
                            "Select": False,
                            "Candidate ID": _candidate_id(question, dim.key, manager_id, url, snippet, idx),
                            "Question": question,
                            "Dimension Key": dim.key,
                            "Dimension": dim_map[dim.key].label,
                            "Manager ID": manager_id,
                            "Manager": manager,
                            "Current Role": role,
                            "Source Family": source_family(question, f"{title} {snippet}", url),
                            "Direction": direction_cue(dim.key, snippet),
                            "Source Grade": source_grade_from_url(url, ticker),
                            "Explicitness": "Extracted original source text — analyst verify context",
                            "Source Title": title[:240],
                            "Source URL / File": url,
                            "Source Date": "",
                            "As-of Date": _year_candidate(f"{title} {url} {snippet}"),
                            "Evidence Text / Reference": snippet[:900],
                            "Source Method": f"Phase 9D official/document extraction — {method}",
                            "Data Origin": "Direct source text — analyst verification required",
                            "Status": "Candidate — analyst verify",
                        }
                    )
    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)


def evidence_quality_summary(candidates: pd.DataFrame) -> pd.DataFrame:
    dim_map = _dimension_map()
    rows: list[dict[str, Any]] = []
    for dim in contract.all_dimensions():
        sub = (
            candidates[candidates["Dimension Key"].eq(dim.key)]
            if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Dimension Key" in candidates.columns
            else pd.DataFrame()
        )
        grades = sub.get("Source Grade", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        explicit = sub.get("Explicitness", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        directions = sub.get("Direction", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        managers = sub.get("Manager ID", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        rows.append(
            {
                "Question": dim.question,
                "Dimension Key": dim.key,
                "Dimension": dim_map[dim.key].label,
                "Candidates": len(sub),
                "A — Official": int(grades.str.startswith("A —").sum()),
                "B — Independent": int(grades.str.startswith("B —").sum()),
                "C — Context": int(grades.str.startswith("C —").sum()),
                "Direct-source text": int(explicit.str.startswith("Extracted original source text").sum()),
                "Manager-linked": int(managers.str.len().gt(0).sum()),
                "Supporting cues": int(directions.str.startswith("Supporting cue").sum()),
                "Counter cues": int(directions.str.startswith("Counter-evidence cue").sum()),
                "Mixed cues": int(directions.str.startswith("Mixed cue").sum()),
                "Boundary": "Coverage only — not a management score",
            }
        )
    return pd.DataFrame(rows, columns=QUALITY_COLUMNS)


def research_gaps(
    candidates: pd.DataFrame,
    dimension_scope: pd.DataFrame | None,
    scope_gaps: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Generate research-completeness gaps without inferring good/bad management."""
    rows: list[dict[str, Any]] = []
    for dim in contract.all_dimensions():
        sub = (
            candidates[candidates["Dimension Key"].eq(dim.key)]
            if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Dimension Key" in candidates.columns
            else pd.DataFrame()
        )
        target = "; ".join(dim.evidence_targets) if dim.evidence_targets else "source-locked evidence"
        families = "; ".join(contract.SOURCE_EVIDENCE_FAMILIES.get(dim.question, ()))
        next_action = f"Collect/verify {target}. Preferred source families: {families}."
        if sub.empty:
            rows.append(
                {
                    "Question": dim.question,
                    "Dimension Key": dim.key,
                    "Research Gap": "No usable evidence candidate found for this source-locked dimension.",
                    "Materiality": "Analyst decide",
                    "Next Action": next_action,
                    "Status": "Open — evidence gap",
                    "Analyst Note": "",
                }
            )
            continue

        explicit = sub.get("Explicitness", pd.Series(dtype="object")).astype(str)
        grades = sub.get("Source Grade", pd.Series(dtype="object")).astype(str)
        if not explicit.str.startswith("Extracted original source text").any():
            rows.append(
                {
                    "Question": dim.question,
                    "Dimension Key": dim.key,
                    "Research Gap": "Only title/snippet candidates are available; original source text has not yet been captured.",
                    "Materiality": "Analyst decide",
                    "Next Action": f"Open and verify the original source before promotion. {next_action}",
                    "Status": "Open — verification gap",
                    "Analyst Note": "",
                }
            )
        if not (grades.str.startswith("A —").any() or grades.str.startswith("B —").any()):
            rows.append(
                {
                    "Question": dim.question,
                    "Dimension Key": dim.key,
                    "Research Gap": "No A/B-quality candidate yet; secondary/profile context should be corroborated.",
                    "Materiality": "Analyst decide",
                    "Next Action": next_action,
                    "Status": "Open — source-quality gap",
                    "Analyst Note": "",
                }
            )

        # For CEO-specific questions, do not silently attach company-level evidence to an unnamed CEO.
        if dim.question in bridge.CEO_QUESTIONS:
            scoped = _manager_scope_for_question(dimension_scope, dim.question)
            has_assigned_ceo = not scoped.empty and scoped["Manager ID"].astype(str).str.len().gt(0).any()
            manager_linked = sub.get("Manager ID", pd.Series(dtype="object")).astype(str).str.len().gt(0).any()
            if has_assigned_ceo and not manager_linked:
                rows.append(
                    {
                        "Question": dim.question,
                        "Dimension Key": dim.key,
                        "Research Gap": "Candidates exist but none is linked by exact manager-name match to the Chapter 7 CEO reference.",
                        "Materiality": "High",
                        "Next Action": "Verify the candidate names/CEO role against Chapter 7 before attaching evidence; do not infer identity from company context alone.",
                        "Status": "Open — manager-link verification gap",
                        "Analyst Note": "",
                    }
                )

    if isinstance(scope_gaps, pd.DataFrame) and not scope_gaps.empty:
        for _, item in scope_gaps.iterrows():
            rows.append({col: item.get(col, "") for col in RESEARCH_GAP_COLUMNS})
    return pd.DataFrame(rows, columns=RESEARCH_GAP_COLUMNS)


class Chapter9ResearchAgent:
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
    ) -> Chapter9ResearchResult:
        symbol = str(ticker or "").upper().strip()
        context = bridge.build_context(chapter7_payload)
        pieces: list[pd.DataFrame] = []
        raw_paths: list[str] = []
        notes: list[str] = [context.note]

        try:
            documents, attempts, official_note = discover_official_documents(
                symbol, max_documents=max_official_documents
            )
            notes.append(official_note)
            direct = official_documents_to_candidates(documents, symbol, context.dimension_scope)
            if not direct.empty:
                pieces.append(direct)
        except Exception as exc:
            attempts = pd.DataFrame(columns=ATTEMPT_COLUMNS)
            notes.append(f"Official/company discovery failed safely: {exc}")

        for focus in QUESTION_ORDER:
            scope = _manager_scope_for_question(context.dimension_scope, focus)
            manager_names = (
                scope.get("Manager", pd.Series(dtype="object")).dropna().astype(str).tolist()
                if not scope.empty
                else []
            )
            try:
                agent = _FocusedChapter9Agent(self.raw_dir, focus, manager_names)
                result = agent.search(symbol, company_name, max_results_per_query=max_results_per_query)
                candidate = classify_search_rows(result.table.copy(), symbol, focus, context.dimension_scope)
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
        gaps = research_gaps(frame, context.dimension_scope, context.gaps)
        return Chapter9ResearchResult(
            candidates=frame,
            quality=quality,
            gaps=gaps,
            manager_reference=context.manager_reference,
            dimension_scope=context.dimension_scope,
            source_attempts=attempts,
            raw_paths=raw_paths,
            note=" | ".join(notes),
        )


__all__ = [
    "CANDIDATE_COLUMNS",
    "COUNTER_CUES",
    "DIMENSION_TERMS",
    "FINANCING_CONTEXT_CUES",
    "QUALITY_COLUMNS",
    "QUERY_TERMS",
    "QUESTION_ORDER",
    "RESEARCH_BOUNDARY",
    "RESEARCH_GAP_COLUMNS",
    "SUPPORTING_CUES",
    "Chapter9ResearchAgent",
    "Chapter9ResearchResult",
    "classify_search_rows",
    "direction_cue",
    "evidence_quality_summary",
    "matched_dimensions",
    "official_documents_to_candidates",
    "research_gaps",
    "source_family",
]
