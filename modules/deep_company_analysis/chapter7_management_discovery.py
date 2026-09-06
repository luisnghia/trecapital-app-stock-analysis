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
from urllib.parse import urljoin, urlparse, quote_plus, urldefrag
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
    ("Chairman", ("chủ tịch hđqt", "chủ tịch hội đồng quản trị", "ct hđqt", "ct hdqt", "chairman"), 100),
    ("CEO", ("tổng giám đốc", "tgđ", "tgd", "chief executive officer", " ceo "), 98),
    ("Vice Chairman", ("phó chủ tịch hđqt", "phó chủ tịch hội đồng quản trị", "phó chủ tịch", "vice chairman"), 94),
    ("CFO", ("giám đốc tài chính", "chief financial officer", " cfo "), 90),
    ("COO", ("giám đốc vận hành", "chief operating officer", " coo "), 89),
    ("Deputy CEO", ("phó tổng giám đốc", "p. tgđ", "p tgđ", "ptgđ", "deputy general director", "deputy ceo"), 86),
    ("Chief Accountant", ("kế toán trưởng", "chief accountant"), 82),
    ("Independent Director", ("thành viên hđqt độc lập", "thành viên hội đồng quản trị độc lập", "tv hđqt độc lập", "tv hdqt doc lap", "independent director"), 78),
    ("Board Director", ("thành viên hđqt", "ủy viên hđqt", "thành viên hội đồng quản trị", "tv hđqt", "tv hdqt", "board member", "director"), 72),
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

MANAGEMENT_PRIORITY_TERMS = (
    "thay đổi nhân sự", "thay doi nhan su", "nhân sự", "nhan su", "bổ nhiệm", "bo nhiem", "miễn nhiệm", "mien nhiem",
    "tổng giám đốc", "tong giam doc", "chủ tịch", "chu tich", "phó tổng giám đốc", "pho tong giam doc",
    "kế toán trưởng", "ke toan truong", "hội đồng quản trị", "hoi dong quan tri", "hdqt",
)

REPORT_PRIORITY_TERMS = (
    "báo cáo thường niên", "bao cao thuong nien", "annual report", "bctn",
    "báo cáo quản trị", "bao cao quan tri", "tình hình quản trị", "tinh hinh quan tri", "corporate governance",
    "báo cáo tài chính", "bao cao tai chinh", "financial statement", "financial report", "bctc",
    "quý 4", "quy 4", "quarter 4", "kiểm toán", "kiem toan", "audited",
)

# Name extraction intentionally does not require the role to be adjacent. Official PDF table extraction
# often returns a column of names followed by a column of roles. Role is therefore a separately verified field.
PERSON_NAME_PATTERN = re.compile(
    r"(?<![A-Za-zÀ-ỹĐđ])(?i:Ông|Bà|Mr\.?|Ms\.?)\s+"
    r"([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\.-]+"
    r"(?:\s+[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\.-]+){1,5})"
)

# Official governance/financial PDFs often render table cells without an honorific, e.g.
# `Đào Hữu Huyền    Chủ tịch HĐQT`. Bare names are therefore considered only when a
# role is present in the same/adjacent preserved-layout line; they are never accepted globally.
BARE_NAME_PATTERN = re.compile(
    r"(?<![A-Za-zÀ-ỹĐđ])([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\.-]+"
    r"(?:\s+[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\.-]+){1,5})"
)


NOISE_NAME_TOKENS = {
    "báo", "thay", "đổi", "nhân", "sự", "qua", "bầu", "nghị", "quyết", "thông", "tin", "công", "bố",
    "xem", "thêm", "họp", "đại", "hội", "đồng", "quản", "trị", "ty", "tập", "đoàn", "chủ", "tịch",
    "tổng", "giám", "đốc", "phó", "thành", "viên", "kế", "toán", "trưởng", "điều", "lệ", "bổ", "nhiệm",
    "ông", "bà", "mr", "ms", "ủy", "uỷ", "ban", "kiểm", "soát", "giữ", "chức", "vụ", "được", "đảm", "sinh",
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
    # Match specificity must outrank seniority priority so compound titles do not collapse:
    # "Phó Tổng Giám đốc" -> Deputy CEO, not CEO; "Phó Chủ tịch HĐQT" -> Vice Chairman,
    # not Chairman; "Thành viên HĐQT độc lập" -> Independent Director, not Board Director.
    best = ("", "", 0)
    best_key = (0, 0)
    for normalized, terms, priority in ROLE_RULES:
        for term in terms:
            needle = term.casefold().strip()
            if not needle or needle not in low:
                continue
            key = (len(needle), priority)
            if key > best_key:
                best = (term.strip(), normalized, priority)
                best_key = key
    return best


def _candidate_name(raw_name: str) -> str:
    tokens = [t.strip(" ,.;:()-") for t in _clean_text(raw_name).split() if t.strip(" ,.;:()-")]
    forbidden = {
        "cbtt", "biên", "bản", "giấy", "đề", "cử", "tiếng", "english",
        "board", "management", "directors", "director", "report", "annual",
    }
    kept: list[str] = []
    for token in tokens:
        folded = token.casefold().rstrip(".")
        if folded in NOISE_NAME_TOKENS or folded in forbidden:
            break
        if not re.fullmatch(r"[A-Za-zÀ-ỹĐđ'\.-]+", token):
            break
        kept.append(token)
        if len(kept) >= 5:
            break
    if not (2 <= len(kept) <= 5):
        return ""
    name = " ".join(kept)
    low = name.casefold()
    if any(phrase in low for phrase in (
        "board of management", "board of directors", "tiếng việt", "cbtt ",
        "giấy đề cử", "biên bản", "nghị quyết", "công bố thông tin",
    )):
        return ""
    if all(t.isupper() for t in kept) and any(t.casefold() in NOISE_NAME_TOKENS for t in kept):
        return ""
    return name


COMMON_VN_SURNAMES = {
    "nguyễn", "trần", "lê", "phạm", "hoàng", "huỳnh", "phan", "vũ", "võ", "đặng", "bùi", "đỗ", "hồ", "ngô",
    "dương", "lý", "đào", "đinh", "lưu", "mai", "trịnh", "cao", "lâm", "tạ", "tô", "tăng", "thái", "quách",
    "châu", "chu", "hà", "kiều", "la", "mạc", "ninh", "tôn", "trương", "vương", "lại", "doãn", "thân", "thạch",
}

NON_PERSON_NAME_TOKENS = {
    "dgc", "ctcp", "tnhh", "cp", "jsc", "group", "joint", "stock", "company", "corporation", "chemical", "chemicals",
    "phòng", "ban", "stt", "họ", "cbtt", "report", "annual", "board", "management", "directors", "director",
    "mua", "bán", "cổ", "phiếu", "giấy", "đề", "cử", "biên", "bản", "nghị", "quyết", "tiếng", "english",
    "thời", "gian", "còn", "lại", "ứng", "viên", "thông", "tin", "công", "bố", "hoá", "hóa", "chất",
}

NON_PERSON_NAME_PHRASES = {
    "board of management", "board of directors", "duc giang chemicals", "dgc cho thời gian", "mua cổ phiếu của",
    "giấy đề cử", "biên bản", "nghị quyết", "công bố thông tin", "hóa chất đức giang", "hoá chất đức giang",
    "việt nam", "viöt nam", "bình dương", "lào cai", "đà nẵng", "miền nam", "phòng phòng phòng",
}

RELATED_PERSON_CUES = (
    "mẹ", "cha", "bố", "vợ", "chồng", "con", "anh", "chị", "em", "người liên quan", "related person",
)


def _has_honorific_reference(name: str, evidence: str) -> bool:
    safe = re.escape(_clean_text(name)).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![A-Za-zÀ-ỹĐđ])(?i:Ông|Bà|Mr\.?|Ms\.?)\s+{safe}(?![A-Za-zÀ-ỹĐđ])", str(evidence or "")))


def _relation_cue_after_name(name: str, evidence: str) -> bool:
    """Reject a related-person row only when the relationship label immediately follows the name.

    Do not scan an arbitrary trailing window: the next manager may legitimately contain words such
    as `Anh` in their own name, which must not be mistaken for a relationship cue.
    """
    low = _clean_text(evidence).casefold()
    needle = _clean_text(name).casefold()
    pos = low.find(needle)
    if pos < 0:
        return False
    tail = low[pos + len(needle):].lstrip(" -–—,:;()[]")
    tail = re.sub(r"^(?:là|la)\s+", "", tail)
    for cue in RELATED_PERSON_CUES:
        if re.match(rf"^{re.escape(cue.casefold())}(?:\s|[-–—,:;()])", tail):
            return True
    return False


def _plausible_manager_candidate(name: str, evidence: str = "", company_name: str = "") -> bool:
    """Conservative identity filter for candidate research targets, never a manager conclusion.

    A Vietnamese-domain bare name must look like a person (typically a common surname) unless the
    source explicitly uses an honorific. Organization/navigation/place fragments are rejected.
    """
    clean = _clean_text(name)
    tokens = [t.casefold().strip(".,;:()[]{}") for t in clean.split() if t.strip(".,;:()[]{}")]
    if not (2 <= len(tokens) <= 5):
        return False
    low = " ".join(tokens)
    if any(token in NON_PERSON_NAME_TOKENS for token in tokens):
        return False
    if any(phrase in low for phrase in NON_PERSON_NAME_PHRASES):
        return False
    if _relation_cue_after_name(clean, evidence):
        return False

    honorific = _has_honorific_reference(clean, evidence)
    if honorific:
        return True

    company_low = _clean_text(company_name).casefold()
    if company_low and low in company_low:
        return False

    return tokens[0] in COMMON_VN_SURNAMES


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


def _role_span_in_line(line: str) -> tuple[tuple[str, str, int], int, int]:
    clean = _clean_text(line)
    low = clean.casefold()
    best_role = ("", "", 0)
    best_span = (-1, -1)
    best_key = (0, 0)
    for normalized, terms, priority in ROLE_RULES:
        for term in terms:
            needle = term.casefold().strip()
            if not needle:
                continue
            pos = low.find(needle)
            if pos < 0:
                continue
            key = (len(needle), priority)
            if key > best_key:
                best_role = (term.strip(), normalized, priority)
                best_span = (pos, pos + len(needle))
                best_key = key
    return best_role, best_span[0], best_span[1]


def _line_role_candidates(raw_text: str) -> dict[str, tuple[str, str, int]]:
    """Map honorific person segments to roles without crossing into the next person.

    Official HTML often flattens several management rows into one long text line. Therefore a
    physical line is not a safe role boundary. Each Ông/Bà/Mr/Ms marker defines its own segment;
    the role is resolved only inside that segment, with a narrow two-line continuation fallback.
    """
    lines = [line for line in _preserve_lines(raw_text).split("\n") if line]
    mapping: dict[str, tuple[str, str, int]] = {}
    honorific_marker = re.compile(r"(?<![A-Za-zÀ-ỹĐđ])(?i:Ông|Bà|Mr\.?|Ms\.?)\s+")

    for idx, line in enumerate(lines):
        clean_line = _clean_text(line)
        markers = list(honorific_marker.finditer(clean_line))
        for pos, marker in enumerate(markers):
            seg_end = markers[pos + 1].start() if pos + 1 < len(markers) else len(clean_line)
            segment = clean_line[marker.start():seg_end]
            role, role_start, _ = _role_span_in_line(segment)
            prefix = segment[:role_start] if role_start >= 0 else segment
            person_match = PERSON_NAME_PATTERN.search(prefix)
            if not person_match:
                continue
            manager = _candidate_name(person_match.group(1))
            if not manager:
                continue

            local_role = role
            if not local_role[1] and pos + 1 == len(markers):
                # Only the final person segment on a physical line can continue to the next line.
                for j in range(idx + 1, min(len(lines), idx + 3)):
                    next_line = _clean_text(lines[j])
                    next_role, next_role_start, _ = _role_span_in_line(next_line)
                    next_prefix = next_line[:next_role_start] if next_role_start >= 0 else next_line
                    if honorific_marker.search(next_prefix):
                        break
                    next_bare = any(
                        _candidate_name(m.group(1))
                        for m in BARE_NAME_PATTERN.finditer(next_prefix)
                    )
                    if next_bare:
                        break
                    if next_role[1]:
                        local_role = next_role
                        break

            if local_role[1] and local_role[2] > mapping.get(manager, ("", "", 0))[2]:
                mapping[manager] = local_role
    return mapping


def _bare_line_role_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:
    """Extract bare names only from the portion of a row preceding a locally recognized role."""
    lines = [line for line in _preserve_lines(raw_text).split("\n") if line]
    out: list[tuple[str, tuple[str, str, int], str]] = []
    for idx, line in enumerate(lines):
        clean_line = _clean_text(line)
        role, role_start, _ = _role_span_in_line(clean_line)
        prefix = clean_line[:role_start] if role_start >= 0 else clean_line

        bare_people: list[str] = []
        for match in BARE_NAME_PATTERN.finditer(prefix):
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            before = prefix[max(0, match.start() - 8):match.start()].casefold().rstrip()
            if any(before.endswith(x) for x in ("ông", "bà", "mr", "mr.", "ms", "ms.")):
                continue
            bare_people.append(manager)

        if not bare_people:
            continue

        local_role = role
        context = clean_line
        if not local_role[1] and idx + 1 < len(lines):
            next_line = _clean_text(lines[idx + 1])
            next_role, next_role_start, _ = _role_span_in_line(next_line)
            next_prefix = next_line[:next_role_start] if next_role_start >= 0 else next_line
            next_honorific = bool(PERSON_NAME_PATTERN.search(next_prefix))
            next_bare = any(
                _candidate_name(m.group(1))
                for m in BARE_NAME_PATTERN.finditer(next_prefix)
            )
            if next_role[1] and not next_honorific and not next_bare:
                local_role = next_role
                context = f"{clean_line} {next_line}"

        if not local_role[1]:
            continue
        for manager in bare_people:
            out.append((manager, local_role, _clean_text(context)[:900]))

    deduped: list[tuple[str, tuple[str, str, int], str]] = []
    seen: set[tuple[str, str]] = set()
    for manager, role, context in out:
        key = (manager.casefold(), role[1])
        if key in seen:
            continue
        seen.add(key)
        deduped.append((manager, role, context))
    return deduped


def _role_then_name_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:
    """Extract signature/table layouts where a recognized role precedes the person's name.

    Examples from official filings include `CHỦ TỊCH HĐQT` on one line and the signatory name on
    the next line. The fallback is deliberately local: same line after the role, or exactly one
    following line when that line has no competing role.
    """
    lines = [line for line in _preserve_lines(raw_text).split("\n") if line]
    out: list[tuple[str, tuple[str, str, int], str]] = []
    for idx, line in enumerate(lines):
        clean_line = _clean_text(line)
        role, role_start, role_end = _role_span_in_line(clean_line)
        if not role[1] or role_start < 0:
            continue

        candidates: list[tuple[str, str]] = []
        suffix = clean_line[role_end:].strip()
        for match in BARE_NAME_PATTERN.finditer(suffix):
            manager = _candidate_name(match.group(1))
            if manager:
                candidates.append((manager, clean_line))
                break

        if not candidates and idx + 1 < len(lines):
            next_line = _clean_text(lines[idx + 1])
            next_role, _, _ = _role_span_in_line(next_line)
            if not next_role[1]:
                for match in BARE_NAME_PATTERN.finditer(next_line):
                    manager = _candidate_name(match.group(1))
                    if manager:
                        candidates.append((manager, f"{clean_line} {next_line}"))
                        break

        for manager, context in candidates:
            out.append((manager, role, _clean_text(context)[:900]))

    deduped: list[tuple[str, tuple[str, str, int], str]] = []
    seen: set[tuple[str, str]] = set()
    for manager, role, context in out:
        key = (manager.casefold(), role[1])
        if key in seen:
            continue
        seen.add(key)
        deduped.append((manager, role, context))
    return deduped


def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5, company_name: str = "") -> pd.DataFrame:
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
        for manager, (role_raw, role_norm, priority), context in _bare_line_role_candidates(raw_text):
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
        for manager, (role_raw, role_norm, priority), context in _role_then_name_candidates(raw_text):
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
    plausible = frame.apply(
        lambda row: _plausible_manager_candidate(
            row.get("Manager", ""), row.get("Evidence Text / Reference", ""), company_name
        ),
        axis=1,
    )
    frame = frame[plausible].copy()
    if frame.empty:
        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)

    # If the same source/role contains both a full name and a shorter suffix fragment, retain the
    # longest candidate. This handles table extraction such as `TRẦN THỊ XUÂN` plus `THỊ XUÂN`.
    drop_idx: set[int] = set()
    for _, group in frame.groupby(["Source URL / File", "Role Normalized", "As-of Date"], dropna=False):
        entries = [(idx, _clean_text(row["Manager"]).casefold()) for idx, row in group.iterrows()]
        for idx, short in entries:
            for other_idx, long_name in entries:
                if idx == other_idx:
                    continue
                if len(long_name.split()) > len(short.split()) and (long_name.endswith(" " + short) or long_name.startswith(short + " ")):
                    drop_idx.add(idx)
                    break
    if drop_idx:
        frame = frame.drop(index=list(drop_idx))

    frame["_year_num"] = pd.to_numeric(frame["As-of Date"], errors="coerce").fillna(0)
    current_year = pd.Timestamp.utcnow().year
    frame["_year_num"] = frame["_year_num"].clip(upper=current_year)
    frame = frame.sort_values(["_year_num", "_priority"], ascending=[False, False])
    frame = frame.drop_duplicates(subset=["Manager", "Role Normalized", "As-of Date", "Source URL / File"], keep="first")
    return frame[MANAGER_CANDIDATE_COLUMNS].reset_index(drop=True)


def choose_research_targets(managers: pd.DataFrame, max_targets: int = 5, company_name: str = "") -> list[str]:
    if not isinstance(managers, pd.DataFrame) or managers.empty:
        return []
    ranked = managers.copy()
    ranked = ranked[
        ranked.apply(
            lambda row: _plausible_manager_candidate(
                row.get("Manager", ""), row.get("Evidence Text / Reference", ""), company_name
            ),
            axis=1,
        )
    ].copy()
    if ranked.empty:
        return []

    priority_map = {normalized: priority for normalized, _, priority in ROLE_RULES}
    ranked["_priority"] = ranked["Role Normalized"].map(priority_map).fillna(1)
    ranked["_year"] = pd.to_numeric(ranked["As-of Date"], errors="coerce").fillna(0)
    current_year = pd.Timestamp.utcnow().year
    ranked["_year"] = ranked["_year"].clip(upper=current_year)
    ranked["_source_count"] = ranked.groupby("Manager")["Source URL / File"].transform("nunique")
    ranked = ranked.sort_values(["_year", "_priority", "_source_count"], ascending=[False, False, False])

    names: list[str] = []
    # Always seed the research queue with the strongest Chairman and CEO candidates when available;
    # this is target coverage, not confirmation of office or management quality.
    for required_role in ("Chairman", "CEO"):
        role_rows = ranked[ranked["Role Normalized"].eq(required_role)]
        for value in role_rows["Manager"].astype(str):
            name = _clean_text(value)
            if name and name not in names:
                names.append(name)
                break
        if len(names) >= max_targets:
            return names[:max_targets]

    for value in ranked["Manager"].astype(str):
        name = _clean_text(value)
        if name and name not in names:
            names.append(name)
        if len(names) >= max_targets:
            break
    return names[:max_targets]


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
        href = urldefrag(urljoin(final_url, anchor.get("href", "")))[0]
        label = _clean_text(anchor.get_text(" ", strip=True))
        if href.startswith(("http://", "https://")):
            links.append((label, href))
    return _preserve_lines(soup.get_text("\n", strip=True))[:max_chars], "HTML text extraction", final_url, links


def _link_score(label: str, url: str) -> int:
    text = f"{label} {url}".casefold()
    score = sum(3 for term in LINK_TERMS if term.casefold() in text)
    score += sum(30 for term in MANAGEMENT_PRIORITY_TERMS if term.casefold() in text)
    score += sum(18 for term in REPORT_PRIORITY_TERMS if term.casefold() in text)
    year = _year(text)
    if year:
        score += max(0, int(year) - 2020) * 2
    if url.lower().split("?")[0].endswith(".pdf"):
        score += 65
        # Personnel resolutions, governance reports and signed appointment PDFs should outrank
        # generic IR category pages because they carry the actual named management evidence.
        if any(token in text for token in (
            "hdqt", "tgd", "nhan-su", "nhân sự", "bo-nhiem", "bổ nhiệm",
            "mien-nhiem", "miễn nhiệm", "chu-tich", "chủ tịch", "tong-giam-doc",
            "báo cáo quản trị", "bao-cao-quan-tri",
        )):
            score += 120
    if "/category/" not in url.lower() and len(urlparse(url).path.strip("/").split("/")) >= 2:
        score += 5
    return score


def _index_like(url: str, links: list[tuple[str, str]]) -> bool:
    low = url.lower()
    return "/category/" in low or (len(links) >= 20 and low.rstrip("/").endswith("quan-he-co-dong"))


def _document_has_management_signal(text: str) -> bool:
    low = _clean_text(text).casefold()
    role_hit = any(term.strip().casefold() in low for _, terms, _ in ROLE_RULES for term in terms if term.strip())
    person_hit = bool(PERSON_NAME_PATTERN.search(_clean_text(text)))
    bare_role_hit = bool(_bare_line_role_candidates(text))
    role_then_name_hit = bool(_role_then_name_candidates(text))
    compensation_hit = any(x in low for x in ("thù lao", "remuneration", "esop", "cổ phần nắm giữ", "ownership", "người nội bộ", "giao dịch"))
    return (role_hit and (person_hit or bare_role_hit or role_then_name_hit)) or compensation_hit


def _wordpress_search_urls(seed: str) -> list[str]:
    parsed = urlparse(seed)
    if not parsed.scheme or not parsed.netloc:
        return []
    root = f"{parsed.scheme}://{parsed.netloc}/"
    terms = ("nhân sự", "tổng giám đốc", "chủ tịch HĐQT", "hội đồng quản trị", "ban tổng giám đốc", "báo cáo thường niên", "báo cáo quản trị", "tình hình quản trị", "báo cáo tài chính quý 4", "thông tin về doanh nghiệp")
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
    # Vietnamese listed-company IR sites frequently expose a short friendly /quan-he-co-dong/
    # URL while actual disclosures live under WordPress category paths. Add common category and
    # recent pagination seeds generically. These remain same-domain official sources.
    expanded_seeds = list(seeds)
    for seed in list(seeds):
        parsed = urlparse(seed)
        root = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else ""
        if root:
            expanded_seeds.append(root)
        if "quan-he-co-dong" not in parsed.path.casefold() or not root:
            continue
        bases = [
            root + "category/quan-he-co-dong/",
            root + "category/quan-he-co-dong/bao-cao-thuong-nien/",
            root + "category/quan-he-co-dong/bao-cao-quan-tri/",
            root + "category/quan-he-co-dong/bao-cao-tai-chinh/",
            root + "category/quan-he-co-dong/thong-bao/",
        ]
        expanded_seeds.extend(bases)
        # Personnel changes often move off page 1 quickly. Crawl only a shallow recent history.
        for page in range(2, 7):
            expanded_seeds.append(root + f"category/quan-he-co-dong/thong-bao/page/{page}/")
        for page in range(2, 4):
            expanded_seeds.append(root + f"category/quan-he-co-dong/bao-cao-thuong-nien/page/{page}/")
            expanded_seeds.append(root + f"category/quan-he-co-dong/bao-cao-quan-tri/page/{page}/")
        # Some IR themes paginate the top-level shareholder archive with a query parameter rather than /page/N/.
        for page in range(1, 4):
            expanded_seeds.append(root + f"category/quan-he-co-dong/?page_number_0={page}")
    seeds = list(dict.fromkeys(expanded_seeds))
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
    max_fetches = max(80, max_documents * 12)

    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(timeout_seconds, connect=min(3.0, timeout_seconds)), follow_redirects=True) as client:
        for seed in seeds:
            domain = _domain(seed)
            seed_score = 150 if "/category/quan-he-co-dong/" in seed else 120
            starters = [(seed_score, f"{safe} official/IR seed", seed)]
            starters += [(70, f"{safe} official site search", u) for u in _wordpress_search_urls(seed)]
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

            if links and depth < 3:
                for child_label, child_href in links:
                    if child_href in fetched or child_href in queued or not _same_domain(child_href, root_domain):
                        continue
                    child_score = _link_score(child_label, child_href)
                    if child_score <= 0:
                        continue
                    queue.append((child_score, depth + 1, child_label, child_href, root_domain))
                    queued.add(child_href)

    managers = extract_management_candidates_from_documents(documents, max_targets=max_targets, company_name=company_name)
    targets = choose_research_targets(managers, max_targets=max_targets, company_name=company_name)
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
