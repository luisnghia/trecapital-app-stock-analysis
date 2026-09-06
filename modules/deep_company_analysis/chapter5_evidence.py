from __future__ import annotations

"""Phase 5C — source-first Research Assistant for Shearn Chapter 5 (Q21–Q26).

This module is intentionally conservative. It finds and normalizes *candidate evidence* for the
analyst workspace. It never writes an analyst conclusion, never sets a risk rating, never labels a
balance sheet strong/weak, never converts ROIC into an investment-quality/compounder conclusion,
and never emits BUY/HOLD/SELL or changes a Research Gate.

Financial numbers remain owned by the Trecapital canonical data layer (Phase 5B). Phase 5C adds
source evidence and research gaps around those numbers; it does not create a parallel financial
source.
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

from adapters.module2_web_research import HEADERS, WebEvidenceAgent
from modules.deep_company_analysis.chapter2_evidence import (
    CHAPTER2_OFFICIAL_PAGES,
    CHAPTER2_OFFICIAL_PDFS,
    SourceFirstChapter2EvidenceAgent,
    _main_text_from_html,
)
from modules.deep_company_analysis.chapter5_source_audit import (
    annotate_search_frame,
    failed_source_attempts,
    official_search_domain,
    prioritize_candidates,
    registered_source_catalog,
    summarize_search_raw_log,
)

# Chapter 5 keeps the shared Chapter-2 trusted source registry, but adds resilient DGC fallbacks
# for operating-health research. The 2025 annual-report PDF endpoint can intermittently return an
# HTML/WAF body to non-browser clients; these additional first-party sources prevent one endpoint
# from becoming a single point of failure without introducing a parallel financial source.
CHAPTER5_OFFICIAL_PAGES = {**CHAPTER2_OFFICIAL_PAGES}
CHAPTER5_OFFICIAL_PAGES["DGC"] = tuple(CHAPTER2_OFFICIAL_PAGES.get("DGC", ())) + (
    ("ĐHĐCĐ thường niên 2025", "https://ducgiangchem.vn/9329-2/"),
    ("Báo cáo thường niên 2025 — trang công bố", "https://ducgiangchem.vn/bao-cao-thuong-nien-nam-2025/"),
)

CHAPTER5_OFFICIAL_PDFS = {**CHAPTER2_OFFICIAL_PDFS}
CHAPTER5_OFFICIAL_PDFS["DGC"] = tuple(CHAPTER2_OFFICIAL_PDFS.get("DGC", ())) + (
    (
        "Tài liệu ĐHĐCĐ 2025 — kế hoạch SXKD và đầu tư",
        "https://ducgiangchem.vn/wp-content/uploads/2025/03/20250303-DGC-CBTT-NQ-HDQT-thong-qua-tai-lieu-hop-DHDCD-thuong-nien-2025.pdf",
    ),
    (
        "Báo cáo thường niên 2024 — fallback lịch sử gần nhất",
        "https://ducgiangchem.vn/wp-content/uploads/2025/03/20250314-DGC-Bao-cao-thuong-nien-Annual-Report-2024.pdf",
    ),
)

QUESTIONS = ("Q21", "Q22", "Q23", "Q24", "Q25", "Q26")
FOCUSES = ("Q21_Q22", "Q23", "Q24", "Q25", "Q26")
OFFICIAL_STATUS = "Evidence trích từ nguồn chính thức"


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
        if len(line) < 5:
            continue
        if out and line == out[-1]:
            continue
        out.append(line)
    return out


def _context(lines: list[str], idx: int, radius: int = 1, limit: int = 950) -> str:
    return " | ".join(lines[max(0, idx - radius): min(len(lines), idx + radius + 1)])[:limit]


Q21_TERMS = (
    "sản lượng", "production", "sales volume", "volume", "giá bán", "selling price", "asp",
    "công suất", "capacity", "utilization", "hiệu suất", "chi phí", "unit cost", "cost per",
    "biên lợi nhuận", "margin", "product mix", "cơ cấu sản phẩm", "segment mix", "thị phần",
    "market share", "nguyên liệu", "raw material", "đơn hàng", "backlog", "khách hàng", "customer",
)
Q22_METRIC_TERMS = (
    "sản lượng", "production volume", "sales volume", "volume", "công suất", "capacity",
    "utilization", "hiệu suất", "unit cost", "chi phí/tấn", "cost per ton", "average selling price",
    "asp", "same-store", "traffic", "users", "subscribers", "khách hàng", "stores", "backlog",
    "order book", "market share", "thị phần", "yield", "output", "ton", "tấn",
)
Q22_CAUSE_TERMS = (
    "do ", "do đó", "nguyên nhân", "chủ yếu do", "ảnh hưởng bởi", "because", "due to", "driven by",
    "resulted from", "primarily", "caused by", "impact of", "nhờ", "sụt giảm do", "tăng do",
)
Q23_TERMS = (
    "rủi ro", "risk", "dư thừa công suất", "overcapacity", "commodit", "nhà cung cấp", "supplier",
    "công nghệ", "technology", "quy định", "regulation", "pháp luật", "law", "lỗi thời", "obsolescence",
    "patent", "bằng sáng chế", "đối thủ", "competitor", "brand erosion", "suy yếu thương hiệu",
    "phụ thuộc khách hàng", "customer concentration", "r&d", "nghiên cứu", "m&a", "acquisition",
    "pipeline", "gián đoạn", "disruption", "environmental", "môi trường", "an toàn", "safety",
)
Q24_TERMS = (
    "lạm phát", "inflation", "giá nguyên liệu", "raw material price", "input cost", "chi phí đầu vào",
    "giá điện", "electricity price", "năng lượng", "energy", "freight", "vận tải", "wage", "tiền lương",
    "tăng giá", "price increase", "pass-through", "pass through", "chuyển giá", "replacement cost",
    "chi phí thay thế", "lãi suất", "interest rate", "floating rate", "fixed rate",
)
Q25_TERMS = (
    "nợ vay", "debt", "loan", "borrowings", "maturity", "đáo hạn", "fixed rate", "floating rate",
    "lãi suất cố định", "lãi suất thả nổi", "secured", "unsecured", "thế chấp", "tài sản bảo đảm",
    "recourse", "non-recourse", "covenant", "cam kết", "headroom", "refinancing", "tái cấp vốn",
    "guarantee", "bảo lãnh", "lease", "thuê", "off-balance", "ngoài bảng cân đối", "pension",
    "liquidity", "thanh khoản", "credit facility", "hạn mức tín dụng",
)
Q26_TERMS = (
    "roic", "return on invested capital", "lợi nhuận trên vốn đầu tư", "tái đầu tư", "reinvest",
    "capex", "capital expenditure", "dự án", "project", "mở rộng", "expansion", "công suất", "capacity",
    "nhà máy", "plant", "organic growth", "tăng trưởng hữu cơ", "acquisition", "m&a", "runway",
    "incremental return", "project return", "irr", "npv", "thời gian hoàn vốn", "payback",
)
Q26_PROJECT_ECON_TERMS = (
    "irr", "npv", "project return", "return on investment", "incremental earnings", "lợi nhuận tăng thêm",
    "doanh thu tăng thêm", "incremental revenue", "payback", "thời gian hoàn vốn", "vốn đầu tư",
    "investment amount", "tổng mức đầu tư",
)

NEGATIVE_TERMS = (
    "suy giảm", "giảm", "áp lực", "rủi ro", "thiếu hụt", "gián đoạn", "vi phạm", "breach", "default",
    "deteriorat", "declin", "pressure", "disruption", "shortage", "loss", "failed", "thất bại",
    "overcapacity", "dư thừa", "erosion", "obsolete", "lỗi thời", "refinancing risk",
)
POSITIVE_TERMS = (
    "tăng", "cải thiện", "improv", "growth", "ổn định", "stable", "giảm nợ", "deleverag",
    "headroom", "thanh khoản tốt", "strong liquidity", "tiết giảm", "cost saving", "expansion completed",
)

FOCUS_SITE_TERMS = {
    "Q21_Q22": "sản lượng công suất giá bán operating metrics annual report",
    "Q23": "rủi ro risk môi trường an toàn annual report",
    "Q24": "lạm phát nguyên liệu điện năng input cost annual report",
    "Q25": "nợ vay maturity covenant liquidity financial statements",
    "Q26": "ROIC capex dự án mở rộng investment annual report",
}


class _FocusedChapter5Agent(WebEvidenceAgent):
    def __init__(self, raw_dir: str | Path, focus: str):
        super().__init__(raw_dir)
        self.focus = focus

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:  # type: ignore[override]
        name = self._clean_company_name(company_name) or company_name or ticker
        if self.focus == "Q21_Q22":
            broad = [
                f'"{ticker}" "{name}" sản lượng công suất utilization giá bán ASP unit cost market share operating metrics',
                f'"{ticker}" "{name}" sản lượng tăng giảm nguyên nhân due to driven by capacity price volume',
            ]
        elif self.focus == "Q23":
            broad = [
                f'"{ticker}" "{name}" rủi ro risk công suất công nghệ quy định nhà cung cấp đối thủ khách hàng',
                f'"{ticker}" "{name}" sự cố gián đoạn vi phạm môi trường an toàn litigation regulation risk',
            ]
        elif self.focus == "Q24":
            broad = [
                f'"{ticker}" "{name}" lạm phát giá nguyên liệu điện năng lượng vận tải tiền lương pass-through',
                f'"{ticker}" "{name}" tăng giá input cost inflation interest rate fixed floating debt',
            ]
        elif self.focus == "Q25":
            broad = [
                f'"{ticker}" "{name}" nợ vay đáo hạn maturity covenant secured recourse refinancing liquidity',
                f'"{ticker}" "{name}" bảo lãnh lease off balance sheet commitments credit facility covenant',
            ]
        else:
            broad = [
                f'"{ticker}" "{name}" ROIC tái đầu tư capex dự án mở rộng công suất total investment project return',
                f'"{ticker}" "{name}" organic growth M&A reinvestment runway IRR NPV payback incremental earnings',
            ]

        # WebEvidenceAgent intentionally executes only the first two queries. Put a registered
        # first-party domain query first, while retaining one broad discovery query for counter-evidence.
        domain = official_search_domain(ticker)
        if domain:
            official_query = f'site:{domain} "{ticker}" "{name}" {FOCUS_SITE_TERMS.get(self.focus, "annual report")}'
            return [official_query, broad[0]]
        # If no company domain is registered, retain the two broad queries rather than pretending
        # a generic exchange landing page is company-specific evidence.
        return broad


@dataclass
class Chapter5EvidenceResult:
    candidates: pd.DataFrame
    raw_tables: pd.DataFrame
    raw_paths: list[str]
    note: str
    source_audit: dict[str, Any]


def _source_quality(row: dict[str, Any]) -> str:
    text = _norm(f"{row.get('Nhóm thông tin','')} {row.get('Trạng thái','')} {row.get('_SourceMethod','')}")
    if any(token in text for token in ("nguon doanh nghiep", "nguon cong bo", "official", "bctn", "bctc", "pdf chinh thuc", "ir direct")):
        return "A — Company/Official disclosure"
    if "du lieu/tin tai chinh" in text or "independent" in text:
        return "B — Independent financial source"
    return "C — Secondary/context source"


def _direction(text: str) -> str:
    normalized = _norm(text)
    if any(_norm(term) in normalized for term in NEGATIVE_TERMS):
        return "Contradicting — Candidate"
    if any(_norm(term) in normalized for term in POSITIVE_TERMS):
        return "Supporting — Candidate"
    return "Neutral — Candidate"


def _is_evidence_row(row: dict[str, Any]) -> bool:
    status = str(row.get("Trạng thái") or "").strip()
    return status == "Tìm thấy" or status.startswith(OFFICIAL_STATUS)


def _question_matches(text: str, focus: str) -> list[tuple[str, str, str]]:
    """Return (question, subtopic, explicitness). No conclusion is encoded here."""
    matches: list[tuple[str, str, str]] = []
    if focus == "Q21_Q22":
        if _contains(text, Q21_TERMS):
            matches.append(("Q21", "Fundamental / economic-driver candidate", "Candidate driver only — analyst decides materiality"))
        if _contains(text, Q22_METRIC_TERMS):
            explicit = (
                "Metric + reason-of-change language candidate — verify explicit causality in source"
                if _contains(text, Q22_CAUSE_TERMS)
                else "Operating metric candidate — reason for change not established"
            )
            matches.append(("Q22", "Operating KPI / metric candidate", explicit))
    elif focus == "Q23" and _contains(text, Q23_TERMS):
        matches.append(("Q23", "Risk / mitigation / historical-case candidate", "Evidence candidate only — no Frequency/Severity inference"))
    elif focus == "Q24" and _contains(text, Q24_TERMS):
        matches.append(("Q24", "Inflation transmission / pass-through candidate", "Evidence candidate only — no resilience conclusion"))
    elif focus == "Q25" and _contains(text, Q25_TERMS):
        strict = []
        normalized = _norm(text)
        for label, terms in (
            ("maturity", ("maturity", "dao han")),
            ("covenant", ("covenant", "cam ket")),
            ("off-BS", ("off-balance", "ngoai bang can doi", "guarantee", "bao lanh", "lease", "thue")),
            ("refinancing/liquidity", ("refinancing", "tai cap von", "liquidity", "thanh khoan")),
        ):
            if any(term in normalized for term in terms):
                strict.append(label)
        explicit = "Disclosure candidate: " + ", ".join(strict) if strict else "Debt/balance-sheet candidate — terms require source verification"
        matches.append(("Q25", "Debt / liquidity / covenant / off-BS candidate", explicit))
    elif focus == "Q26" and _contains(text, Q26_TERMS):
        explicit = (
            "Project-economics candidate — analyst must verify invested capital AND attributable earnings/return"
            if _contains(text, Q26_PROJECT_ECON_TERMS)
            else "Reinvestment/runway candidate — insufficient by itself for incremental ROIC"
        )
        matches.append(("Q26", "ROIC / reinvestment / runway candidate", explicit))
    return matches


def candidate_rows(raw_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness",
        "Title", "URL", "Snippet", "Source Group", "Query", "Focus", "Source Method",
    ]
    if not isinstance(raw_df, pd.DataFrame) or raw_df.empty:
        return pd.DataFrame(columns=columns)
    out: list[dict[str, Any]] = []
    for _, row in raw_df.iterrows():
        data = row.to_dict()
        if not _is_evidence_row(data):
            continue
        focus = str(data.get("_Focus") or "")
        text = f"{data.get('Tiêu đề','')} {data.get('Trích yếu','')}"
        for question, subtopic, explicitness in _question_matches(text, focus):
            out.append({
                "Question": question,
                "Subtopic": subtopic,
                "Direction": _direction(text),
                "Evidence Quality": _source_quality(data),
                "Explicitness": explicitness,
                "Title": str(data.get("Tiêu đề") or ""),
                "URL": str(data.get("Nguồn/URL") or ""),
                "Snippet": str(data.get("Trích yếu") or "")[:950],
                "Source Group": str(data.get("Nhóm thông tin") or ""),
                "Query": str(data.get("Truy vấn") or ""),
                "Focus": focus,
                "Source Method": str(data.get("_SourceMethod") or ("Search snippet" if str(data.get("Trạng thái") or "") == "Tìm thấy" else "Official direct extraction")),
            })
    if not out:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(out, columns=columns)
    return df.drop_duplicates(subset=["Question", "URL", "Snippet"], keep="first").reset_index(drop=True)


def _official_topic_rows(ticker: str, title: str, url: str, text: str, method: str) -> list[dict[str, Any]]:
    lines = _clean_lines(text)
    specs = (
        ("Q21_Q22", Q21_TERMS + Q22_METRIC_TERMS, 12),
        ("Q23", Q23_TERMS, 12),
        ("Q24", Q24_TERMS, 10),
        ("Q25", Q25_TERMS, 12),
        ("Q26", Q26_TERMS, 12),
    )
    rows: list[dict[str, Any]] = []
    for focus, terms, max_rows in specs:
        seen: set[str] = set()
        count = 0
        for idx, line in enumerate(lines):
            if not _contains(line, terms):
                continue
            snippet = _context(lines, idx, radius=1)
            key = _norm(snippet)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append({
                "Nhóm thông tin": "Nguồn doanh nghiệp/IR",
                "Tiêu đề": f"{ticker} — {title} — {focus} evidence {count + 1}",
                "Nguồn/URL": url,
                "Tên miền": "ducgiangchem.vn" if "ducgiangchem.vn" in url else "",
                "Trích yếu": snippet,
                "Trạng thái": OFFICIAL_STATUS,
                "Gợi ý sử dụng": "Mở nguồn gốc và analyst xác minh trước khi dùng.",
                "Truy vấn": "Official source direct extraction",
                "Điểm phù hợp": 60,
                "_Focus": focus,
                "_SourceMethod": method,
            })
            count += 1
            if count >= max_rows:
                break
    return rows


def _fetch_official_rows(raw_dir: Path, ticker: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    helper = SourceFirstChapter2EvidenceAgent(raw_dir)
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(8.0, connect=2.0), follow_redirects=True) as client:
        for label, url in CHAPTER5_OFFICIAL_PAGES.get(ticker, ()):
            attempt: dict[str, Any] = {
                "channel": "official",
                "focus": "Q21–Q26",
                "kind": "Official HTML",
                "label": label,
                "url": url,
                "success": False,
                "status": "",
                "rows": 0,
                "error": "",
            }
            try:
                resp = client.get(url)
                resp.raise_for_status()
                page_title, text = _main_text_from_html(resp.text)
                extracted = _official_topic_rows(ticker, label or page_title or "Official page", url, text, "Official HTML direct extraction")
                rows.extend(extracted)
                attempt.update({"success": True, "status": f"HTTP {resp.status_code}", "rows": len(extracted)})
                if not extracted:
                    attempt["error"] = "Retrieved successfully but no Q21–Q26 topic row was extracted"
            except Exception as exc:
                attempt.update({"status": "Retrieval failed", "error": str(exc)[:400]})
            audit.append(attempt)

        for label, url in CHAPTER5_OFFICIAL_PDFS.get(ticker, ()):
            attempt = {
                "channel": "official",
                "focus": "Q21–Q26",
                "kind": "Official PDF",
                "label": label,
                "url": url,
                "success": False,
                "status": "",
                "rows": 0,
                "error": "",
            }
            try:
                text, status = helper._official_pdf_text(ticker, label, url, client)
                extracted = _official_topic_rows(ticker, label, url, text, "Official PDF/BCTN direct extraction") if text else []
                rows.extend(extracted)
                attempt.update({"success": bool(text), "status": str(status or ""), "rows": len(extracted)})
                if not text:
                    attempt["error"] = str(status or "PDF returned no extractable text")[:400]
                elif not extracted:
                    attempt["error"] = "PDF text retrieved but no Q21–Q26 topic row was extracted"
            except Exception as exc:
                attempt.update({"status": "Retrieval failed", "error": str(exc)[:400]})
            audit.append(attempt)
    return rows, audit


def _cache_path(raw_dir: Path, ticker: str) -> Path:
    folder = raw_dir / "chapter5_evidence" / ticker
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"chapter5_phase5c_{int(time.time())}.json"


def _latest_cached_candidates(raw_dir: Path, ticker: str) -> pd.DataFrame:
    folder = raw_dir / "chapter5_evidence" / ticker
    if not folder.exists():
        return pd.DataFrame()
    for path in sorted(folder.glob("chapter5_phase5c_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("candidate_rows") or []
            if rows:
                return pd.DataFrame(rows)
        except Exception:
            continue
    return pd.DataFrame()


class Chapter5EvidenceAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def search(self, ticker: str, company_name: str = "", max_results_per_query: int = 4) -> Chapter5EvidenceResult:
        safe = "".join(ch for ch in str(ticker or "").upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]
        frames: list[pd.DataFrame] = []
        raw_paths: list[str] = []
        source_catalog = registered_source_catalog(safe, CHAPTER5_OFFICIAL_PAGES, CHAPTER5_OFFICIAL_PDFS)
        audit: dict[str, Any] = {
            "ticker": safe,
            "company_name": str(company_name or ""),
            "created_at": datetime.now().isoformat(),
            "source_catalog": source_catalog.to_dict(orient="records") if not source_catalog.empty else [],
            "search": [],
            "official": [],
            "attempts": [],
            "failed_sources": [],
            "cache_fallback": False,
        }
        for focus in FOCUSES:
            result = _FocusedChapter5Agent(self.raw_dir, focus).search(safe, company_name, max_results_per_query=max_results_per_query)
            frame = annotate_search_frame(result.table.copy(), safe)
            frame["_Focus"] = focus
            if "_SourceMethod" not in frame.columns:
                frame["_SourceMethod"] = "Search snippet"
            frames.append(frame)
            if result.raw_path:
                raw_paths.append(str(result.raw_path))
            attempt = summarize_search_raw_log(result.raw_path or "", focus)
            audit["attempts"].append(attempt)
            audit["search"].append({
                "focus": focus,
                "rows": len(frame),
                "raw_path": str(result.raw_path or ""),
                "success": bool(attempt.get("success")),
                "status": str(attempt.get("status") or ""),
                "error": str(attempt.get("error") or ""),
            })

        official_rows, official_audit = _fetch_official_rows(self.raw_dir, safe)
        audit["official"] = official_audit
        audit["attempts"].extend(official_audit)
        if official_rows:
            frames.append(pd.DataFrame(official_rows))

        raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not raw.empty:
            for col in ("_Focus", "Nguồn/URL", "Trích yếu"):
                if col not in raw.columns:
                    raw[col] = ""
            raw = raw.drop_duplicates(subset=["_Focus", "Nguồn/URL", "Trích yếu"], keep="first").reset_index(drop=True)
        candidates = prioritize_candidates(candidate_rows(raw))

        if candidates.empty:
            cached = _latest_cached_candidates(self.raw_dir, safe)
            if not cached.empty:
                candidates = prioritize_candidates(cached.copy())
                audit["cache_fallback"] = True

        failed = failed_source_attempts(audit)
        audit["failed_sources"] = failed.to_dict(orient="records") if not failed.empty else []
        audit["attempt_summary"] = {
            "total": len(audit["attempts"]),
            "successful": int(sum(bool(item.get("success")) for item in audit["attempts"] if isinstance(item, dict))),
            "failed": int(len(failed)),
            "registered_sources": int(len(source_catalog)),
        }

        path = _cache_path(self.raw_dir, safe)
        payload = {
            **audit,
            "coverage": candidate_coverage(candidates),
            "candidate_rows": candidates.to_dict(orient="records") if not candidates.empty else [],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        raw_paths.append(str(path))

        a_count = int(candidates["Evidence Quality"].astype(str).str.startswith("A —").sum()) if not candidates.empty else 0
        mode = "cache fallback" if audit["cache_fallback"] else "fresh source-first research"
        note = (
            f"Phase 5C: {len(candidates)} candidate evidence row(s), nguồn A={a_count}; mode={mode}; "
            f"source attempts={audit['attempt_summary']['total']}, failed={audit['attempt_summary']['failed']}. "
            "Mọi row vẫn là Candidate — analyst phải xác minh trước khi dùng để kết luận Q21–Q26."
        )
        return Chapter5EvidenceResult(candidates.reset_index(drop=True), raw.reset_index(drop=True), raw_paths, note, audit)


def candidate_coverage(candidates: pd.DataFrame) -> dict[str, int]:
    if not isinstance(candidates, pd.DataFrame) or candidates.empty or "Question" not in candidates.columns:
        return {q: 0 for q in QUESTIONS}
    counts = candidates["Question"].value_counts().to_dict()
    return {q: int(counts.get(q, 0)) for q in QUESTIONS}


def evidence_quality_summary(candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for q in QUESTIONS:
        qdf = candidates[candidates["Question"].eq(q)].copy() if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Question" in candidates.columns else pd.DataFrame()
        total = len(qdf)
        source_a = int(qdf["Evidence Quality"].astype(str).str.startswith("A —").sum()) if total else 0
        source_b = int(qdf["Evidence Quality"].astype(str).str.startswith("B —").sum()) if total else 0
        support = int(qdf["Direction"].astype(str).str.startswith("Supporting").sum()) if total else 0
        counter = int(qdf["Direction"].astype(str).str.startswith("Contradicting").sum()) if total else 0
        if total == 0:
            status = "Gap"
        elif source_a >= 1 and total >= 2:
            status = "Khá — có nguồn A"
        else:
            status = "Mỏng — cần xác minh/bổ sung"
        rows.append({"Question": q, "Candidates": total, "Nguồn A": source_a, "Nguồn B": source_b, "Supporting": support, "Counter": counter, "Coverage Status": status})
    return pd.DataFrame(rows)


def research_gaps(candidates: pd.DataFrame, quant_context: dict[str, Any] | None = None) -> list[dict[str, str]]:
    summary = evidence_quality_summary(candidates)
    guidance = {
        "Q21": "Xác minh driver thực sự tạo giá trị và bằng chứng suy yếu/cải thiện; không chỉ nhìn Revenue/EPS.",
        "Q22": "Cần KPI hoạt động đặc thù ngành, định nghĩa so sánh được và nguyên nhân biến động 3–5 năm có nguồn.",
        "Q23": "Cần historical company evidence/peer case/mitigation cho các risk còn material; không suy Severity từ số bài báo.",
        "Q24": "Cần evidence về input-cost inflation, pass-through lag, volume/customer impact, replacement-capital và debt-rate channel.",
        "Q25": "Cần disclosure về maturity, fixed/floating, recourse, covenant/headroom, refinancing và off-BS commitments nếu có.",
        "Q26": "Cần evidence về reinvestment project/runway và economics dự án; không suy compounder chỉ từ ROIC hiện tại.",
    }
    gaps: list[dict[str, str]] = []
    for _, row in summary.iterrows():
        q = str(row.get("Question") or "")
        status = str(row.get("Coverage Status") or "")
        if status.startswith("Gap") or status.startswith("Mỏng"):
            gaps.append({
                "Question": q,
                "Research Gap": guidance[q],
                "Materiality": "Review",
                "Next Action": f"Bổ sung/đối chiếu nguồn A; hiện có {row.get('Candidates', 0)} candidate(s), nguồn A={row.get('Nguồn A', 0)}.",
                "Status": "Open — Candidate",
                "Analyst Note": "Research Assistant suggestion; analyst decides priority/closure.",
            })
    if quant_context:
        if quant_context.get("q22_context") is not None:
            q22 = next((r for r in gaps if r["Question"] == "Q22"), None)
            if q22:
                q22["Next Action"] += " Phase 5B đã có quantitative context; vẫn cần causal/operating disclosure để giải thích biến động."
        if quant_context.get("canonical_roic_latest") is not None:
            q26 = next((r for r in gaps if r["Question"] == "Q26"), None)
            if q26:
                q26["Next Action"] += " Canonical ROIC có sẵn nhưng không thay thế evidence về reinvestment/runway."
    return gaps


def merge_candidates_into_record(record: dict[str, Any], candidates: pd.DataFrame, gaps: list[dict[str, str]] | None = None, max_rows: int = 180) -> dict[str, Any]:
    """Append candidate evidence/gaps only. Analyst fields are deliberately untouched."""
    if not isinstance(record, dict):
        return record
    evidence = list(record.get("evidence_matrix") or []) if isinstance(record.get("evidence_matrix"), list) else []
    seen = {
        (str(r.get("Question") or ""), str(r.get("Source URL / File") or ""), str(r.get("Evidence Text") or ""))
        for r in evidence if isinstance(r, dict)
    }
    if isinstance(candidates, pd.DataFrame) and not candidates.empty:
        for _, item in candidates.head(max_rows).iterrows():
            key = (str(item.get("Question") or ""), str(item.get("URL") or ""), str(item.get("Snippet") or ""))
            if key in seen:
                continue
            seen.add(key)
            evidence.append({
                "Question": str(item.get("Question") or ""),
                "Claim": f"{item.get('Subtopic','')} — {item.get('Title','')}".strip(" —"),
                "Evidence Type": str(item.get("Evidence Quality") or ""),
                "Source Title": str(item.get("Title") or ""),
                "Source URL / File": str(item.get("URL") or ""),
                "Source Date": "",
                "Period": "",
                "Evidence Text": str(item.get("Snippet") or ""),
                "Direction": str(item.get("Direction") or "Neutral — Candidate"),
                "Status": "Candidate — Analyst verify",
                "Data Origin": "Chapter 5 Research Assistant Phase 5C",
                "Analyst Note": f"{item.get('Explicitness','')} | Source method: {item.get('Source Method','')}",
            })
    record["evidence_matrix"] = evidence

    existing_gaps = list(record.get("research_gaps_table") or []) if isinstance(record.get("research_gaps_table"), list) else []
    gap_seen = {(str(r.get("Question") or ""), str(r.get("Research Gap") or "")) for r in existing_gaps if isinstance(r, dict)}
    for gap in gaps or []:
        key = (str(gap.get("Question") or ""), str(gap.get("Research Gap") or ""))
        if key in gap_seen:
            continue
        gap_seen.add(key)
        existing_gaps.append(dict(gap))
    record["research_gaps_table"] = existing_gaps
    return record


def guardrails() -> dict[str, bool]:
    return {
        "overwrite_analyst_assessment": False,
        "auto_fundamental_conclusion": False,
        "auto_metric_criticality": False,
        "fabricate_metric_causality": False,
        "auto_risk_frequency": False,
        "auto_risk_severity": False,
        "media_attention_is_risk_magnitude": False,
        "missing_evidence_is_low_risk": False,
        "auto_inflation_resilience": False,
        "auto_balance_sheet_strong_weak": False,
        "fabricate_covenant": False,
        "fabricate_off_bs_obligation": False,
        "assume_all_cash_is_excess": False,
        "auto_roic_quality": False,
        "auto_compounder_conclusion": False,
        "fabricate_incremental_roic": False,
        "auto_research_gate_change": False,
        "auto_buy_hold_sell": False,
    }
