from __future__ import annotations

"""Phase 4C.1 Research Assistant Evidence Quality Bridge for Shearn Chapter 4.

The engine is source-first and conservative. It combines:
- focused web-search candidates;
- direct extraction from trusted company/IR HTML pages;
- direct extraction from trusted annual-report PDFs already registered in Trecapital;
- transparent cache fallback when the network is unavailable.

Everything produced here remains *candidate evidence*. The module never sets moat, pricing power,
industry quality, competition intensity, supplier quality, Research Gate, or BUY/HOLD/SELL.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
import json
import re
import time
import unicodedata

import httpx
import pandas as pd

from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS, WebEvidenceAgent
from modules.deep_company_analysis.chapter2_evidence import (
    CHAPTER2_OFFICIAL_PAGES,
    CHAPTER2_OFFICIAL_PDFS,
    SourceFirstChapter2EvidenceAgent,
    _main_text_from_html,
)


FOCUSES = ("Q15_Q16", "Q17_Q18", "Q19", "Q20")
QUESTIONS = ("Q15", "Q16", "Q17", "Q18", "Q19", "Q20")

OFFICIAL_EVIDENCE_STATUS_PREFIX = "Evidence trích từ nguồn chính thức"


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip()


def _contains(text: str, terms: Iterable[str]) -> bool:
    normalized = _norm(text)
    return any(_norm(term) in normalized for term in terms)


def _clean_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in str(text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" \t•-–—")
        if len(line) < 4:
            continue
        if out and line == out[-1]:
            continue
        out.append(line)
    return out


def _context(lines: list[str], idx: int, radius: int = 1, limit: int = 900) -> str:
    return " | ".join(lines[max(0, idx - radius): min(len(lines), idx + radius + 1)])[:limit]


Q15_TERMS = (
    "lợi thế cạnh tranh", "competitive advantage", "moat", "thương hiệu", "brand", "bằng sáng chế",
    "patent", "giấy phép", "license", "quota", "switching cost", "chi phí chuyển đổi", "quy mô", "scale",
    "chi phí thấp", "cost advantage", "nguồn nguyên liệu", "tự chủ nguyên liệu", "mỏ", "location",
    "vị trí", "vertical integration", "tích hợp dọc", "network effect", "hệ sinh thái", "thị phần dẫn đầu",
)
Q16_PRICE_TERMS = (
    "tăng giá", "giảm giá", "giá bán", "selling price", "average selling price", "asp", "pricing",
    "price increase", "price decrease", "premium price", "pass through", "pass-through",
)
Q16_REACTION_TERMS = (
    "sản lượng", "volume", "khách hàng", "customer", "retention", "churn", "mất khách", "demand",
    "nhu cầu", "đơn hàng", "order", "market share", "thị phần",
)
Q17_TERMS = (
    "ngành", "industry", "biên lợi nhuận", "margin", "roic", "lợi nhuận trên vốn", "chu kỳ", "cyclical",
    "rào cản", "barrier", "công suất", "capacity", "nhu cầu", "demand", "cung cầu", "supply demand",
    "economics", "hiệu suất ngành", "giá hàng hóa", "commodity price",
)
Q18_TERMS = (
    "lịch sử", "history", "thay đổi", "chuyển dịch", "consolidation", "hợp nhất", "công nghệ", "technology",
    "quy định", "regulation", "công suất", "capacity", "dự án", "project", "mở rộng", "expansion",
    "tái cấu trúc", "restructuring", "xu hướng", "trend", "cấu trúc ngành", "industry structure",
)
Q19_TERMS = (
    "đối thủ", "competitor", "competition", "cạnh tranh", "thị phần", "market share", "price war",
    "chiến tranh giá", "substitute", "thay thế", "nhập khẩu", "import", "trung quốc", "china", "foreign",
    "đối thủ nước ngoài", "low cost", "giá rẻ", "công suất đối thủ", "competitor capacity",
)
Q20_TERMS = (
    "nhà cung cấp", "supplier", "nguồn cung", "supply", "nguyên liệu", "raw material", "apatit", "apatite",
    "lưu huỳnh", "sulfur", "phốt pho", "phosphorus", "commodity", "hedge", "hedging", "phụ thuộc",
    "concentration", "tập trung nhà cung cấp", "single source", "gián đoạn", "disruption", "chuỗi cung ứng",
    "supply chain", "nhập khẩu nguyên liệu", "điện", "electricity", "than", "coal",
)


class _FocusedChapter4Agent(WebEvidenceAgent):
    def __init__(self, raw_dir: str | Path, focus: str, industry_name: str = ""):
        super().__init__(raw_dir)
        self.focus = focus
        self.industry_name = str(industry_name or "").strip()

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:  # type: ignore[override]
        name = self._clean_company_name(company_name) or company_name or ticker
        industry = self.industry_name or "ngành"
        if self.focus == "Q15_Q16":
            return [
                f'"{ticker}" "{name}" lợi thế cạnh tranh thương hiệu bằng sáng chế giấy phép switching cost quy mô nguồn nguyên liệu suy yếu rủi ro thay thế erosion',
                f'"{ticker}" "{name}" tăng giá giá bán sản lượng khách hàng retention churn mất khách pricing power pass-through',
            ]
        if self.focus == "Q17_Q18":
            return [
                f'"{ticker}" "{industry}" ngành biên lợi nhuận ROIC chu kỳ rào cản công suất nhu cầu',
                f'"{industry}" lịch sử ngành công nghệ quy định hợp nhất công suất thay đổi cấu trúc',
            ]
        if self.focus == "Q19":
            return [
                f'"{ticker}" "{name}" đối thủ cạnh tranh thị phần price war substitute sản phẩm thay thế',
                f'"{ticker}" "{industry}" nhập khẩu đối thủ nước ngoài công suất cạnh tranh thất bại',
            ]
        return [
            f'"{ticker}" "{name}" nhà cung cấp nguyên liệu nguồn cung phụ thuộc supplier concentration',
            f'"{ticker}" "{name}" commodity giá nguyên liệu hedge hedging chuỗi cung ứng gián đoạn',
        ]


@dataclass
class Chapter4EvidenceResult:
    candidates: pd.DataFrame
    raw_tables: pd.DataFrame
    raw_paths: list[str]
    note: str
    source_audit: dict[str, Any] | None = None


def _direction(text: str) -> str:
    normalized = _norm(text)
    counter = (
        "suy giam", "mat thi phan", "ap luc", "rui ro", "giam bien", "canh tranh tang", "gia giam",
        "khach hang roi", "churn tang", "thay the", "het han", "gia phep bi rut", "gian doan", "thieu hut",
        "phu thuoc", "price war", "erosion", "deteriorat", "declin", "lost share", "substitute", "disruption",
        "gia nguyen lieu tang", "nguon cung han che", "import competition",
    )
    support = (
        "dan dau", "thi phan tang", "trung thanh", "premium", "gia tang", "retention cao", "doc quyen",
        "bang sang che", "giay phep", "chi phi thap", "quy mo", "loi the", "leader", "leading", "advantage",
        "strong retention", "exclusive", "cost advantage", "tu chu nguyen lieu", "tich hop doc",
    )
    if any(term in normalized for term in counter):
        return "Contradicting — Candidate"
    if any(term in normalized for term in support):
        return "Supporting — Candidate"
    return "Neutral — Candidate"


def _source_quality(row: dict[str, Any]) -> str:
    group = str(row.get("Nhóm thông tin") or "")
    status = str(row.get("Trạng thái") or "")
    method = str(row.get("_SourceMethod") or "")
    normalized = _norm(f"{group} {status} {method}")
    if any(token in normalized for token in ("nguon cong bo", "nguon doanh nghiep", "official", "bctn", "bctc", "pdf chinh thuc", "ir direct")):
        return "A — Company/Official disclosure"
    if "du lieu/tin tai chinh" in normalized or "independent" in normalized:
        return "B — Independent financial source"
    return "C — Other candidate source"


def _q15_subtopic(text: str) -> str:
    normalized = _norm(text)
    if any(term in normalized for term in ("network effect", "network economics", "hieu ung mang", "he sinh thai", "platform")):
        return "Network Economics"
    if any(term in normalized for term in ("thuong hieu", "brand", "trung thanh", "loyalty")):
        return "Brand Loyalty"
    if any(term in normalized for term in ("bang sang che", "patent", "so huu tri tue", "intellectual property")):
        return "Patents"
    if any(term in normalized for term in ("giay phep", "license", "regulator", "quota", "permit", "quy dinh")):
        return "Regulatory Licenses"
    if any(term in normalized for term in ("switching cost", "chi phi chuyen doi", "migration", "retention", "churn")):
        return "Switching Costs"
    if any(term in normalized for term in ("quy mo", "scale", "chi phi thap", "cost advantage", "vi tri", "location", "mo apatit", "mo ", "nguon nguyen lieu", "tu chu nguyen lieu", "unique asset", "vertical integration", "tich hop doc")):
        return "Cost Advantages — Scale / Location / Unique Asset"
    return "Competitive-advantage candidate"


def _is_evidence_row(data: dict[str, Any]) -> bool:
    status = str(data.get("Trạng thái") or "").strip()
    return status == "Tìm thấy" or status.startswith(OFFICIAL_EVIDENCE_STATUS_PREFIX)


def _candidate_rows(raw_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness",
        "Title", "URL", "Snippet", "Source Group", "Query", "Focus", "Source Method",
    ]
    if not isinstance(raw_df, pd.DataFrame) or raw_df.empty:
        return pd.DataFrame(columns=columns)
    out: list[dict[str, Any]] = []
    for _, row in raw_df.iterrows():
        data = row.to_dict()
        # Direct navigation links and generic placeholders are not evidence.
        if not _is_evidence_row(data):
            continue
        text = _norm(f"{data.get('Tiêu đề','')} {data.get('Trích yếu','')} {data.get('Truy vấn','')}")
        focus = str(data.get("_Focus") or "")
        base = {
            "Direction": _direction(text),
            "Evidence Quality": _source_quality(data),
            "Title": str(data.get("Tiêu đề") or ""),
            "URL": str(data.get("Nguồn/URL") or ""),
            "Snippet": str(data.get("Trích yếu") or ""),
            "Source Group": str(data.get("Nhóm thông tin") or ""),
            "Query": str(data.get("Truy vấn") or ""),
            "Focus": focus,
            "Source Method": str(data.get("_SourceMethod") or ("Search snippet" if str(data.get("Trạng thái") or "") == "Tìm thấy" else "Official direct extraction")),
        }
        if focus == "Q15_Q16":
            if _contains(text, Q15_TERMS) or not _contains(text, Q16_PRICE_TERMS):
                out.append({**base, "Question": "Q15", "Subtopic": _q15_subtopic(text), "Explicitness": "Candidate — analyst verify mechanism/copyability"})
            if _contains(text, Q16_PRICE_TERMS):
                explicit = "Explicit price + customer/volume candidate" if _contains(text, Q16_REACTION_TERMS) else "Price mention only — insufficient for Pricing Power"
                out.append({**base, "Question": "Q16", "Subtopic": "Actual Pricing / Customer Response", "Explicitness": explicit})
        elif focus == "Q17_Q18":
            if _contains(text, Q17_TERMS):
                out.append({**base, "Question": "Q17", "Subtopic": "Industry Economics", "Explicitness": "Industry-economics candidate"})
            if _contains(text, Q18_TERMS):
                out.append({**base, "Question": "Q18", "Subtopic": "Industry Evolution / Regime Change", "Explicitness": "Timeline/event candidate"})
            if not _contains(text, Q17_TERMS + Q18_TERMS):
                out.append({**base, "Question": "Q17", "Subtopic": "Industry source to review", "Explicitness": "General industry candidate"})
        elif focus == "Q19":
            if _contains(text, ("thay thế", "substitute")):
                subtopic = "Substitute Products"
            elif _contains(text, ("nhập khẩu", "nước ngoài", "foreign", "china", "trung quốc", "low cost")):
                subtopic = "Low-cost Country Competition"
            elif _contains(text, ("thất bại", "phá sản", "failure", "failed", "lỗ nặng")):
                subtopic = "Why Competitors Failed"
            elif _contains(text, ("price war", "chiến tranh giá", "giá rẻ")):
                subtopic = "Fierceness / Price Competition"
            else:
                subtopic = "Competitive Landscape"
            out.append({**base, "Question": "Q19", "Subtopic": subtopic, "Explicitness": "Competitor/threat candidate"})
        elif focus == "Q20":
            if _contains(text, ("commodity", "giá nguyên liệu", "hedge", "hedging", "apatit", "apatite", "lưu huỳnh", "sulfur")):
                subtopic = "Commodity Resource Dependence"
            elif _contains(text, ("tập trung nhà cung cấp", "supplier concentration", "phụ thuộc nhà cung cấp", "single source")):
                subtopic = "Supplier Concentration"
            elif _contains(text, ("gián đoạn", "supply disruption", "nguồn cung", "supply chain", "chuỗi cung ứng")):
                subtopic = "Reliable Sources / Supply Chain"
            else:
                subtopic = "Supplier Relationship / Innovation"
            out.append({**base, "Question": "Q20", "Subtopic": subtopic, "Explicitness": "Supplier/commodity candidate"})
    result = pd.DataFrame(out, columns=columns)
    if result.empty:
        return result
    return result.drop_duplicates(subset=["Question", "Subtopic", "URL", "Snippet"], keep="first").reset_index(drop=True)


def _official_topic_rows(*, ticker: str, page_title: str, url: str, text: str, source_method: str) -> list[dict[str, Any]]:
    """Extract contextual Chapter 4 evidence from a trusted first-party source.

    Keyword matching only surfaces candidate passages. It never interprets those passages as an
    analyst judgement. Q16 is deliberately restricted to passages containing a price term.
    """
    lines = _clean_lines(text)
    rows: list[dict[str, Any]] = []
    specs: tuple[tuple[str, str, tuple[str, ...], int], ...] = (
        ("Q15", "Q15_Q16", Q15_TERMS, 10),
        ("Q16", "Q15_Q16", Q16_PRICE_TERMS, 8),
        ("Q17", "Q17_Q18", Q17_TERMS, 10),
        ("Q18", "Q17_Q18", Q18_TERMS, 10),
        ("Q19", "Q19", Q19_TERMS, 10),
        ("Q20", "Q20", Q20_TERMS, 12),
    )
    for question, focus, keywords, max_rows in specs:
        seen: set[str] = set()
        for idx, line in enumerate(lines):
            if not _contains(line, keywords):
                continue
            snippet = _context(lines, idx, radius=1)
            if question == "Q18":
                # Historical/evolution evidence is stronger with a date or an explicit regime-change term.
                if not re.search(r"\b(?:19|20)\d{2}\b", snippet) and not _contains(snippet, ("thay đổi", "chuyển dịch", "hợp nhất", "consolidation", "công nghệ", "technology", "quy định", "regulation", "mở rộng", "expansion")):
                    continue
            key = _norm(snippet)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append({
                "_Focus": focus,
                "_SourceMethod": source_method,
                "Nhóm thông tin": f"Nguồn doanh nghiệp/IR | {question}",
                "Tiêu đề": f"{ticker} — {page_title} — {question} evidence {len(seen)}",
                "Nguồn/URL": url,
                "Tên miền": re.sub(r"^www\.", "", httpx.URL(url).host or "") if url else "",
                "Trích yếu": snippet,
                "Trạng thái": OFFICIAL_EVIDENCE_STATUS_PREFIX,
                "Gợi ý sử dụng": f"{source_method}; analyst mở nguồn gốc và xác minh trước khi dùng cho {question}.",
                "Truy vấn": "Official source direct extraction",
                "Điểm phù hợp": 70 if "PDF" in source_method else 65,
            })
            if len(seen) >= max_rows:
                break
    return rows


def _official_pages_for_ticker(ticker: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = list(CHAPTER2_OFFICIAL_PAGES.get(ticker, ()))
    for url in KNOWN_COMPANY_DOMAINS.get(ticker, []):
        rows.append(("Investor Relations / official company page", url))
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for label, url in rows:
        if not url or url in seen:
            continue
        seen.add(url)
        out.append((label, url))
    return out


def _fetch_official_rows(raw_dir: Path, ticker: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    audit: dict[str, Any] = {"html": [], "pdf": []}
    pdf_helper = SourceFirstChapter2EvidenceAgent(raw_dir)
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(6.0, connect=1.8), follow_redirects=True) as client:
        for label, url in _official_pages_for_ticker(ticker):
            try:
                response = client.get(url)
                response.raise_for_status()
                page_title, text = _main_text_from_html(response.text)
                extracted = _official_topic_rows(
                    ticker=ticker,
                    page_title=label or page_title or "Official page",
                    url=url,
                    text=text,
                    source_method="Official HTML direct extraction",
                )
                rows.extend(extracted)
                audit["html"].append({"url": url, "status": response.status_code, "rows": len(extracted)})
            except Exception as exc:
                audit["html"].append({"url": url, "error": str(exc)[:240], "rows": 0})

        for label, url in CHAPTER2_OFFICIAL_PDFS.get(ticker, ()):
            text, status = pdf_helper._official_pdf_text(ticker, label, url, client)
            extracted = _official_topic_rows(
                ticker=ticker,
                page_title=label,
                url=url,
                text=text,
                source_method="Official annual-report PDF direct extraction",
            ) if text else []
            rows.extend(extracted)
            audit["pdf"].append({"url": url, "status": status, "rows": len(extracted)})
    return rows, audit


def _cache_folder(raw_dir: str | Path, ticker: str) -> Path:
    folder = Path(raw_dir) / "chapter4_evidence" / str(ticker or "").upper().strip()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _save_chapter4_cache(raw_dir: str | Path, ticker: str, payload: dict[str, Any]) -> Path:
    path = _cache_folder(raw_dir, ticker) / f"evidence_{int(time.time())}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_cached_chapter4_evidence(raw_dir: str | Path, ticker: str, max_files: int = 3) -> pd.DataFrame:
    folder = _cache_folder(raw_dir, ticker)
    files = sorted(folder.glob("evidence_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:max_files]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload.get("raw_rows", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict) or not _is_evidence_row(item):
                continue
            key = (str(item.get("_Focus") or ""), str(item.get("Nguồn/URL") or ""), str(item.get("Trích yếu") or ""))
            if key in seen:
                continue
            seen.add(key)
            copied = dict(item)
            copied["_SourceMethod"] = str(copied.get("_SourceMethod") or "Cached prior evidence")
            rows.append(copied)
    return pd.DataFrame(rows)


class Chapter4EvidenceAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def search(self, ticker: str, company_name: str = "", industry_name: str = "", max_results_per_query: int = 4) -> Chapter4EvidenceResult:
        safe = str(ticker or "").upper().strip()
        frames: list[pd.DataFrame] = []
        raw_paths: list[str] = []
        audit: dict[str, Any] = {
            "ticker": safe,
            "company_name": company_name,
            "industry_name": industry_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "web": [],
            "official": {},
            "cache_fallback": False,
        }

        # 1) Focused web search — useful for independent/counter evidence.
        for focus in FOCUSES:
            result = _FocusedChapter4Agent(self.raw_dir, focus, industry_name).search(
                safe, company_name, max_results_per_query=max_results_per_query
            )
            frame = result.table.copy()
            frame["_Focus"] = focus
            frame["_SourceMethod"] = frame.get("_SourceMethod", "Search snippet")
            frames.append(frame)
            if result.raw_path:
                raw_paths.append(str(result.raw_path))
            audit["web"].append({"focus": focus, "rows": len(frame), "raw_path": str(result.raw_path or "")})

        # 2) Source-first direct extraction from first-party HTML/PDF sources.
        official_rows, official_audit = _fetch_official_rows(self.raw_dir, safe)
        audit["official"] = official_audit
        if official_rows:
            frames.append(pd.DataFrame(official_rows))

        raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not raw.empty:
            for col in ("_Focus", "Tiêu đề", "Nguồn/URL", "Trích yếu"):
                if col not in raw.columns:
                    raw[col] = ""
            raw = raw.drop_duplicates(subset=["_Focus", "Nguồn/URL", "Trích yếu"], keep="first").reset_index(drop=True)

        candidates = _candidate_rows(raw)

        # 3) If current network/source extraction produced no usable candidates, recover the most recent
        #    cached real evidence. Never fabricate substitute rows.
        if candidates.empty:
            cached = load_cached_chapter4_evidence(self.raw_dir, safe, max_files=3)
            cached_candidates = _candidate_rows(cached)
            if not cached_candidates.empty:
                raw = pd.concat([raw, cached], ignore_index=True) if not raw.empty else cached
                candidates = cached_candidates
                audit["cache_fallback"] = True

        payload = {
            **audit,
            "raw_rows": raw.to_dict(orient="records") if isinstance(raw, pd.DataFrame) and not raw.empty else [],
            "candidate_rows": candidates.to_dict(orient="records") if not candidates.empty else [],
            "coverage": candidate_coverage(candidates),
        }
        cache_path = _save_chapter4_cache(self.raw_dir, safe, payload)
        raw_paths.append(str(cache_path))

        official_count = int(candidates["Evidence Quality"].astype(str).str.startswith("A —").sum()) if not candidates.empty else 0
        mode = "cache fallback" if audit["cache_fallback"] else "fresh search/source extraction"
        note = (
            f"Phase 4C.1: {len(candidates)} candidate(s), {official_count} nguồn A; mode={mode}. "
            "Candidate/Direction/Explicitness vẫn phải được analyst xác minh."
        )
        return Chapter4EvidenceResult(
            candidates=candidates.reset_index(drop=True),
            raw_tables=raw.reset_index(drop=True) if isinstance(raw, pd.DataFrame) else pd.DataFrame(),
            raw_paths=raw_paths,
            note=note,
            source_audit=audit,
        )


def merge_candidates_into_evidence_matrix(record: dict[str, Any], candidates: pd.DataFrame, max_rows: int = 160) -> dict[str, Any]:
    """Append Candidate evidence rows while preserving all analyst assessments and evidence."""
    if not isinstance(record, dict) or not isinstance(candidates, pd.DataFrame) or candidates.empty:
        return record
    existing = record.get("evidence_matrix")
    existing_rows = existing if isinstance(existing, list) else []
    rows = list(existing_rows)
    seen = {
        (str(r.get("Question") or ""), str(r.get("Source URL / File") or ""), str(r.get("Evidence Text") or ""))
        for r in rows if isinstance(r, dict)
    }
    for _, item in candidates.head(max_rows).iterrows():
        claim = f"{item.get('Subtopic','')} — {item.get('Title','')}".strip(" —")
        key = (str(item.get("Question") or ""), str(item.get("URL") or ""), str(item.get("Snippet") or ""))
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "Question": str(item.get("Question") or ""),
            "Claim": claim,
            "Evidence Type": str(item.get("Evidence Quality") or ""),
            "Source Title": str(item.get("Title") or ""),
            "Source URL / File": str(item.get("URL") or ""),
            "Source Date": "",
            "Period": "",
            "Evidence Text": str(item.get("Snippet") or ""),
            "Direction": str(item.get("Direction") or "Neutral — Candidate"),
            "Status": "Candidate — Analyst verify",
            "Data Origin": "Chapter 4 Research Assistant Evidence Bridge Phase 4C.1",
            "Analyst Note": (
                f"{item.get('Explicitness','')} | Subtopic: {item.get('Subtopic','')} | "
                f"Source method: {item.get('Source Method','')}"
            ),
        })
    record["evidence_matrix"] = rows
    return record


def candidate_coverage(candidates: pd.DataFrame) -> dict[str, int]:
    if not isinstance(candidates, pd.DataFrame) or candidates.empty or "Question" not in candidates.columns:
        return {q: 0 for q in QUESTIONS}
    counts = candidates["Question"].value_counts().to_dict()
    return {q: int(counts.get(q, 0)) for q in QUESTIONS}


def evidence_quality_summary(candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for question in QUESTIONS:
        qdf = candidates[candidates["Question"].eq(question)].copy() if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Question" in candidates.columns else pd.DataFrame()
        total = len(qdf)
        a_count = int(qdf["Evidence Quality"].astype(str).str.startswith("A —").sum()) if total and "Evidence Quality" in qdf.columns else 0
        b_count = int(qdf["Evidence Quality"].astype(str).str.startswith("B —").sum()) if total and "Evidence Quality" in qdf.columns else 0
        supporting = int(qdf["Direction"].astype(str).str.startswith("Supporting").sum()) if total and "Direction" in qdf.columns else 0
        counter = int(qdf["Direction"].astype(str).str.startswith("Contradicting").sum()) if total and "Direction" in qdf.columns else 0
        explicit = 0
        if question == "Q16" and total and "Explicitness" in qdf.columns:
            explicit = int(qdf["Explicitness"].astype(str).str.startswith("Explicit price + customer/volume").sum())
        if total == 0:
            status = "Gap"
        elif question == "Q16" and explicit == 0:
            status = "Mỏng — chưa có price + customer/volume"
        elif a_count >= 1 and total >= 2:
            status = "Khá — có nguồn A"
        else:
            status = "Mỏng — cần bổ sung"
        rows.append({
            "Question": question,
            "Candidates": total,
            "Nguồn A": a_count,
            "Nguồn B": b_count,
            "Supporting": supporting,
            "Counter": counter,
            "Q16 Explicit": explicit if question == "Q16" else "—",
            "Coverage Status": status,
        })
    return pd.DataFrame(rows)


def research_gaps(candidates: pd.DataFrame) -> list[str]:
    summary = evidence_quality_summary(candidates)
    gaps: list[str] = []
    guidance = {
        "Q15": "cần nguồn chứng minh cơ chế lợi thế và bằng chứng về khả năng bị sao chép/xói mòn",
        "Q16": "cần bằng chứng tăng/giảm giá đi cùng phản ứng volume/khách hàng/retention/thị phần",
        "Q17": "cần thêm evidence economics ngành ngoài bảng ROIC định lượng",
        "Q18": "cần timeline ≥10 năm hoặc các mốc thay đổi cấu trúc/công nghệ/quy định/công suất",
        "Q19": "cần evidence về đối thủ, substitutes, cạnh tranh giá và/hoặc competitor failures",
        "Q20": "cần evidence về supplier concentration, nguồn nguyên liệu, reliability và commodity exposure",
    }
    for _, row in summary.iterrows():
        status = str(row.get("Coverage Status") or "")
        if status.startswith("Gap") or status.startswith("Mỏng"):
            question = str(row.get("Question") or "")
            gaps.append(f"{question}: {guidance.get(question, 'cần bổ sung evidence chất lượng cao')}. Hiện có {row.get('Candidates', 0)} candidate(s), nguồn A={row.get('Nguồn A', 0)}.")
    return gaps


def guardrails() -> dict[str, bool]:
    return {
        "auto_moat_conclusion": False,
        "auto_pricing_power_conclusion": False,
        "auto_industry_quality_conclusion": False,
        "auto_competition_intensity_conclusion": False,
        "auto_supplier_quality_conclusion": False,
        "auto_ideal_company_selection": False,
        "fabricate_interview": False,
        "fabricate_supplier_concentration": False,
        "infer_pricing_power_from_margin_only": False,
        "promote_navigation_link_to_evidence": False,
    }
