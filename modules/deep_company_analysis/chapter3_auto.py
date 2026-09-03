from __future__ import annotations

"""Research Assistant evidence bridge for Shearn Chapter 3.

The module is intentionally conservative: it can collect/source evidence and fill blank research
workspace fields, but it must not turn evidence into analyst judgements such as concentration class,
sales ease, customer dependency or disappearance impact.
"""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
import json
import re
import time
import unicodedata

import httpx
import pandas as pd

from adapters.module2_web_research import EvidenceResult, HEADERS
from modules.deep_company_analysis.chapter2_evidence import (
    CHAPTER2_OFFICIAL_PAGES,
    CHAPTER2_OFFICIAL_PDFS,
    SourceFirstChapter2EvidenceAgent,
    _main_text_from_html,
)


Q7_KEYWORDS = (
    "khách hàng", "khach hang", "customer", "client", "người dùng", "nguoi dung", "consumer",
    "đối tượng khách hàng", "doi tuong khach hang", "end user", "buyer", "purchaser", "b2b", "b2c",
)
Q8_KEYWORDS = (
    "khách hàng lớn", "khach hang lon", "khách hàng chính", "khach hang chinh", "major customer",
    "largest customer", "top customer", "customer concentration", "tập trung khách hàng", "tap trung khach hang",
    "phụ thuộc khách hàng", "phu thuoc khach hang", "accounted for", "chiếm", "chiem",
)
Q9_KEYWORDS = (
    "bán hàng", "ban hang", "sales", "sales force", "salesperson", "phân phối", "phan phoi", "distribution",
    "đại lý", "dai ly", "dealer", "tender", "đấu thầu", "dau thau", "demo", "trial", "promotion",
    "khuyến mại", "khuyen mai", "channel", "hợp đồng", "hop dong", "order", "đơn hàng", "don hang",
)
Q10_KEYWORDS = (
    "retention", "customer retention", "churn", "renewal", "gia hạn", "gia han", "duy trì khách hàng",
    "duy tri khach hang", "giữ chân", "giu chan", "loyalty", "trung thành", "trung thanh", "repeat customer",
    "khách hàng quay lại", "khach hang quay lai", "subscription", "membership", "active customers",
)
Q11_KEYWORDS = (
    "customer satisfaction", "satisfaction", "nps", "csat", "customer service", "dịch vụ khách hàng",
    "dich vu khach hang", "complaint", "khiếu nại", "khieu nai", "feedback", "phản hồi", "phan hoi",
    "survey", "khảo sát", "khao sat", "customer experience", "trải nghiệm khách hàng", "customer oriented",
    "customer-centric", "support", "customer support", "customer care", "chăm sóc khách hàng", "cham soc khach hang",
    "hotline", "tư vấn", "tu van", "hỗ trợ khách hàng", "ho tro khach hang",
)
Q12_KEYWORDS = (
    "nhu cầu", "nhu cau", "need", "pain", "problem", "vấn đề", "van de", "giải pháp", "giai phap",
    "solution", "ứng dụng", "ung dung", "application", "giúp", "giup", "reduce", "avoid", "compliance",
    "yêu cầu", "yeu cau", "quality requirement", "use case", "mục đích", "muc dich",
)
Q13_KEYWORDS = (
    "phụ thuộc", "phu thuoc", "depend", "dependency", "essential", "critical", "required", "bắt buộc", "bat buoc",
    "need to have", "discretionary", "substitute", "alternative", "thay thế", "thay the", "switching",
    "trì hoãn", "tri hoan", "mission critical", "indispensable",
)
Q14_KEYWORDS = (
    "substitute", "alternative", "replacement", "switching", "thay thế", "thay the", "gián đoạn", "gian doan",
    "shortage", "disruption", "single source", "qualified supplier", "nhà cung cấp khác", "nha cung cap khac",
    "nguồn thay thế", "nguon thay the", "replace", "backup supplier",
)

QUESTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Q7": Q7_KEYWORDS,
    "Q8": Q8_KEYWORDS,
    "Q9": Q9_KEYWORDS,
    "Q10": Q10_KEYWORDS,
    "Q11": Q11_KEYWORDS,
    "Q12": Q12_KEYWORDS,
    "Q13": Q13_KEYWORDS,
    "Q14": Q14_KEYWORDS,
}

TRUSTED_GROUP_TOKENS = (
    "nguon doanh nghiep", "nguon cong bo", "bctn", "bctc", "bao cao thuong nien", "bao cao tai chinh",
    "official", "investor relations", "ir", "pdf",
)

# Chapter 3 needs direct customer-facing sources in addition to IR/BCTN. These are evidence sources only;
# they never become analyst conclusions automatically. The DGC Mall pages are first-party customer-facing
# material and are useful primarily for Q9/Q11, while the IR/BCTN layer remains the source for financial
# disclosure and major-customer facts.
CHAPTER3_EXTRA_OFFICIAL_PAGES: dict[str, tuple[tuple[str, str], ...]] = {
    "DGC": (
        ("DGC Mall — Liên hệ / Customer support", "https://dgcmall.vn/lien-he"),
        (
            "DGC Mall — Chương trình khách hàng / consumer promotion",
            "https://dgcmall.vn/chuong-trinh-khuyen-mai-tet-co-duc-giang-trung-vang-nhu-y",
        ),
    ),
}

PLACEHOLDER_EVIDENCE_TOKENS = (
    "nguon uu tien de kiem tra",
    "mo link de doi chieu",
    "nguon tham khao de analyst mo",
)


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip()


def _contains(text: str, keywords: Iterable[str]) -> bool:
    normalized = _norm(text)
    return any(_norm(keyword) in normalized for keyword in keywords)


def _clean_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in str(text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" \t•-–—")
        if len(line) < 4 or (out and line == out[-1]):
            continue
        out.append(line)
    return out


def _context(lines: list[str], idx: int, radius: int = 1, limit: int = 700) -> str:
    return " | ".join(lines[max(0, idx-radius): min(len(lines), idx+radius+1)])[:limit]


def _customer_topic_rows(*, ticker: str, page_title: str, url: str, text: str, source_kind: str) -> list[dict[str, Any]]:
    lines = _clean_lines(text)
    rows: list[dict[str, Any]] = []
    for question, keywords in QUESTION_KEYWORDS.items():
        seen: set[str] = set()
        max_rows = 8 if question in {"Q7", "Q12"} else 6
        for idx, line in enumerate(lines):
            if not _contains(line, keywords):
                continue
            snippet = _context(lines, idx)
            key = _norm(snippet)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append({
                "Nhóm thông tin": f"Nguồn doanh nghiệp/IR | {question}",
                "Tiêu đề": f"{ticker} — {page_title} — {question} evidence {len(seen)}",
                "Nguồn/URL": url,
                "Tên miền": re.sub(r"^www\.", "", httpx.URL(url).host or "") if url else "",
                "Trích yếu": snippet,
                "Trạng thái": "Evidence trích từ nguồn chính thức",
                "Gợi ý sử dụng": f"{source_kind}; analyst mở nguồn gốc trước khi kết luận {question}.",
                "Truy vấn": "Official source direct fetch",
                "Điểm phù hợp": 60,
            })
            if len(seen) >= max_rows:
                break
    return rows


class Chapter3EvidenceAgent(SourceFirstChapter2EvidenceAgent):
    """Customer-perspective evidence agent with official-source-first fallback."""

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:  # type: ignore[override]
        name = self._clean_company_name(company_name) or company_name or ticker
        return [
            f'"{ticker}" "{name}" khách hàng OR customer OR client OR "đối tượng khách hàng"',
            f'"{ticker}" "{name}" "khách hàng lớn" OR "major customer" OR "customer concentration" OR "chiếm doanh thu"',
            f'"{ticker}" "{name}" bán hàng OR phân phối OR đại lý OR đấu thầu OR sales OR distribution OR dealer',
            f'"{ticker}" "{name}" retention OR churn OR renewal OR loyalty OR "giữ chân khách hàng" OR "khách hàng trung thành"',
            f'"{ticker}" "{name}" "customer satisfaction" OR complaint OR feedback OR "dịch vụ khách hàng" OR "chăm sóc khách hàng"',
            f'"{ticker}" "{name}" nhu cầu OR vấn đề OR giải pháp OR application OR "use case" OR substitute OR switching',
            f'"{ticker}" "{name}" "phải thu khách hàng" OR "trade receivables" OR "accounts receivable" OR "major customers"',
            f'"{ticker}" "{name}" "qualified supplier" OR "thay thế nhà cung cấp" OR "nguồn cung gián đoạn" OR "switching supplier"',
        ]

    def _fetch_official_html_rows(self, ticker: str, client: httpx.Client):  # type: ignore[override]
        rows: list[dict[str, Any]] = []
        audit: list[dict[str, str]] = []
        official_pages = CHAPTER2_OFFICIAL_PAGES.get(ticker, ()) + CHAPTER3_EXTRA_OFFICIAL_PAGES.get(ticker, ())
        for label, url in official_pages:
            try:
                response = client.get(url, timeout=5.0)
                response.raise_for_status()
                page_title, text = _main_text_from_html(response.text)
                extracted = _customer_topic_rows(
                    ticker=ticker,
                    page_title=label or page_title or "Official page",
                    url=url,
                    text=text,
                    source_kind="HTML chính thức của doanh nghiệp",
                )
                rows.extend(extracted)
                audit.append({"url": url, "status": str(response.status_code), "rows": str(len(extracted))})
            except Exception as exc:
                audit.append({"url": url, "error": str(exc)[:240]})
        return rows, audit

    def _fetch_official_pdf_rows(self, ticker: str, client: httpx.Client):  # type: ignore[override]
        rows: list[dict[str, Any]] = []
        audit: list[dict[str, str]] = []
        for label, url in CHAPTER2_OFFICIAL_PDFS.get(ticker, ()):
            text, status = self._official_pdf_text(ticker, label, url, client)
            extracted = _customer_topic_rows(
                ticker=ticker,
                page_title=label,
                url=url,
                text=text,
                source_kind="PDF/BCTN chính thức của doanh nghiệp",
            ) if text else []
            rows.extend(extracted)
            audit.append({"url": url, "status": status, "rows": str(len(extracted))})
        return rows, audit

    def search(self, ticker: str, company_name: str = "", max_results_per_query: int = 5) -> EvidenceResult:  # type: ignore[override]
        result = super().search(ticker, company_name, max_results_per_query=max_results_per_query)
        safe = str(ticker or "").upper().strip()
        folder = Path(self.raw_dir) / "chapter3_customer_evidence" / safe
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"evidence_{int(time.time())}.json"
        payload = {
            "ticker": safe,
            "company_name": company_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "rows": result.table.to_dict(orient="records") if isinstance(result.table, pd.DataFrame) else [],
            "upstream_raw_path": str(result.raw_path or ""),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return EvidenceResult(result.table, path, f"Chapter 3 customer evidence: {len(result.table)} rows; cache: {path}")


def load_cached_chapter3_evidence(raw_dir: str | Path, ticker: str, max_files: int = 3) -> pd.DataFrame:
    folder = Path(raw_dir) / "chapter3_customer_evidence" / str(ticker or "").upper().strip()
    if not folder.exists():
        return pd.DataFrame()
    files = sorted(folder.glob("evidence_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:max_files]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload.get("rows", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("Tiêu đề") or ""),
                str(item.get("Nguồn/URL") or ""),
                str(item.get("Trích yếu") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
    return pd.DataFrame(rows)


def classify_evidence(evidence_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sections: dict[str, list[dict[str, Any]]] = {q: [] for q in QUESTION_KEYWORDS}
    if not isinstance(evidence_df, pd.DataFrame) or evidence_df.empty:
        return {q: pd.DataFrame() for q in QUESTION_KEYWORDS}
    for _, row in evidence_df.iterrows():
        data = row.to_dict()
        group = str(data.get("Nhóm thông tin") or "")
        text = " ".join(str(data.get(k) or "") for k in ("Nhóm thông tin", "Tiêu đề", "Trích yếu"))
        explicit = re.findall(r"\bQ(?:7|8|9|10|11|12|13|14)\b", group.upper())
        for question, keywords in QUESTION_KEYWORDS.items():
            if question in explicit or _contains(text, keywords):
                sections[question].append(data)
    out: dict[str, pd.DataFrame] = {}
    for question, rows in sections.items():
        if not rows:
            out[question] = pd.DataFrame()
            continue
        df = pd.DataFrame(rows)
        for col in ("Tiêu đề", "Nguồn/URL"):
            if col not in df.columns:
                df[col] = ""
        out[question] = df.drop_duplicates(subset=["Tiêu đề", "Nguồn/URL"], keep="first")
    return out


def _trusted_row(row: Any) -> bool:
    group = _norm(row.get("Nhóm thông tin") if hasattr(row, "get") else "")
    score = 0.0
    try:
        score = float(row.get("Điểm phù hợp") or 0)
    except Exception:
        pass
    return any(token in group for token in TRUSTED_GROUP_TOKENS) or score >= 30


def _substantive_row(row: Any) -> bool:
    if not hasattr(row, "get"):
        return False
    text = _norm(" ".join(str(row.get(key) or "") for key in ("Tiêu đề", "Trích yếu", "Gợi ý sử dụng")))
    if not text or len(text) < 40:
        return False
    if any(token in text for token in PLACEHOLDER_EVIDENCE_TOKENS):
        return False
    return True


def _substantive_trusted(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    mask = []
    for _, row in df.iterrows():
        mask.append(_trusted_row(row) and _substantive_row(row))
    return df.loc[mask].copy() if any(mask) else pd.DataFrame(columns=df.columns)


def evidence_quality_coverage(evidence_df: pd.DataFrame) -> dict[str, Any]:
    """Measure usable evidence, not mere search-result row count.

    Q8 requires an explicit major-customer percentage candidate and Q10 requires an explicit
    retention/churn/renewal metric. Other questions require at least one substantive trusted row.
    This prevents placeholders, export-share statements and generic links from inflating coverage.
    """
    sections = classify_evidence(evidence_df)
    trusted = {q: _substantive_trusted(df) for q, df in sections.items()}
    concentration = extract_concentration_candidates(trusted.get("Q8", pd.DataFrame()))
    retention = extract_retention_metrics(trusted.get("Q10", pd.DataFrame()))
    eligible = {
        "Q7 Core Customer evidence": not trusted.get("Q7", pd.DataFrame()).empty,
        "Q8 Concentration evidence": bool(concentration),
        "Q9 Sales-friction evidence": not trusted.get("Q9", pd.DataFrame()).empty,
        "Q10 Retention evidence": bool(retention),
        "Q11 Customer-orientation evidence": not trusted.get("Q11", pd.DataFrame()).empty,
        "Q12 Customer-pain evidence": not trusted.get("Q12", pd.DataFrame()).empty,
        "Q13 Dependency evidence": not trusted.get("Q13", pd.DataFrame()).empty,
        "Q14 Replacement/disappearance evidence": not trusted.get("Q14", pd.DataFrame()).empty,
    }
    filled = sum(bool(v) for v in eligible.values())
    return {
        "eligible_fields": eligible,
        "filled": filled,
        "total": len(eligible),
        "coverage_pct": round(filled / len(eligible) * 100.0, 1) if eligible else 0.0,
        "trusted_substantive_rows": {q: int(len(df)) for q, df in trusted.items()},
    }


def research_gap_suggestions(quality: dict[str, Any]) -> list[str]:
    eligible = quality.get("eligible_fields", {}) if isinstance(quality, dict) else {}
    mapping = {
        "Q7 Core Customer evidence": "Q7 — Xác minh core customer bằng customer-side/fieldwork; Revenue Relevance và Profit Relevance chỉ điền khi có disclosure/evidence.",
        "Q8 Concentration evidence": "Q8 — Tìm major-customer disclosure có % doanh thu và kỳ so sánh; không dùng tỷ trọng xuất khẩu/segment/geography thay cho customer concentration.",
        "Q9 Sales-friction evidence": "Q9 — Xác minh sales cycle, qualification/tender, discount/promotion dependency và repeat-purchase friction từ sales/channel/customer evidence.",
        "Q10 Retention evidence": "Q10 — Tìm explicit retention/churn/renewal metric; nếu doanh nghiệp không công bố thì analyst giữ Not disclosed/Unknown thay vì tạo proxy giả.",
        "Q11 Customer-orientation evidence": "Q11 — Tìm satisfaction/complaint/service evidence, management proximity và customer-side validation; không dùng marketing claim làm kết luận.",
        "Q12 Customer-pain evidence": "Q12 — Xác minh pain/need bằng customer-side evidence hoặc phỏng vấn; mô tả từ góc nhìn khách hàng.",
        "Q13 Dependency evidence": "Q13 — Tìm bằng chứng về mức phụ thuộc, khả năng trì hoãn và substitutes; analyst tự chọn continuum của Shearn.",
        "Q14 Replacement/disappearance evidence": "Q14 — Cần evidence về alternative, time-to-replace, switching burden và operational disruption; analyst tự đánh giá impact.",
    }
    return [message for key, message in mapping.items() if not bool(eligible.get(key))]


def _evidence_draft(df: pd.DataFrame, heading: str, max_items: int = 4, *, trusted_only: bool = False) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    lines = [f"Research Assistant evidence draft — {heading}; analyst cần mở nguồn và tự kết luận:"]
    used = 0
    for _, row in df.iterrows():
        if trusted_only and not _trusted_row(row):
            continue
        title = re.sub(r"\s+", " ", str(row.get("Tiêu đề") or "")).strip()
        snippet = re.sub(r"\s+", " ", str(row.get("Trích yếu") or "")).strip()
        url = str(row.get("Nguồn/URL") or "").strip()
        body = snippet[:360] if snippet else title
        lines.append(f"- {title or 'Evidence'}: {body}" + (f" | Nguồn: {url}" if url else ""))
        used += 1
        if used >= max_items:
            break
    return "\n".join(lines) if used else ""


def _pct(text: str, labels: tuple[str, ...]) -> str:
    normalized = _norm(text)
    label_expr = "|".join(re.escape(_norm(label)) for label in labels)
    patterns = (
        rf"(?:{label_expr})[^%]{{0,80}}?(\d{{1,3}}(?:[.,]\d+)?)\s*%",
        rf"(\d{{1,3}}(?:[.,]\d+)?)\s*%[^.]{{0,80}}?(?:{label_expr})",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            try:
                value = float(match.group(1).replace(",", "."))
                if 0 <= value <= 100:
                    return f"{value:.1f}%"
            except Exception:
                pass
    return ""


def extract_retention_metrics(q10_df: pd.DataFrame) -> dict[str, str]:
    if not isinstance(q10_df, pd.DataFrame) or q10_df.empty:
        return {}
    for _, row in q10_df.iterrows():
        if not _trusted_row(row):
            continue
        text = f"{row.get('Tiêu đề','')} {row.get('Trích yếu','')}"
        retention = _pct(text, ("customer retention rate", "retention rate", "ty le duy tri khach hang", "ty le giu chan"))
        churn = _pct(text, ("customer churn rate", "churn rate", "ty le churn", "ty le roi bo"))
        renewal = _pct(text, ("renewal rate", "ty le gia han"))
        if retention or churn or renewal:
            return {
                "retention_rate": retention or renewal,
                "churn_rate": churn,
                "source": str(row.get("Nguồn/URL") or ""),
                "title": str(row.get("Tiêu đề") or ""),
            }
    return {}


def extract_concentration_candidates(q8_df: pd.DataFrame, max_rows: int = 8) -> list[dict[str, str]]:
    if not isinstance(q8_df, pd.DataFrame) or q8_df.empty:
        return []
    out: list[dict[str, str]] = []
    for _, row in q8_df.iterrows():
        if not _trusted_row(row):
            continue
        title = str(row.get("Tiêu đề") or "").strip()
        snippet = re.sub(r"\s+", " ", str(row.get("Trích yếu") or "")).strip()
        text = f"{title} {snippet}"
        share = _pct(text, ("customer", "client", "khach hang", "doanh thu", "revenue", "sales"))
        normalized = _norm(text)
        explicit_concentration = _contains(normalized, Q8_KEYWORDS)
        if not explicit_concentration or not share:
            continue
        out.append({
            "Customer / Group": "Cần analyst xác định tên khách hàng từ nguồn",
            "Revenue share %": share.replace("%", ""),
            "Period": "",
            "Trend": "",
            "Bargaining power": "",
            "Dependency / loss impact": "",
            "Evidence": (str(row.get("Nguồn/URL") or "") + (" | " if row.get("Nguồn/URL") else "") + title)[:600],
        })
        if len(out) >= max_rows:
            break
    return out


def build_chapter3_assistant_draft(evidence_df: pd.DataFrame | None = None, *, source_label: str = "Trecapital customer evidence") -> dict[str, Any]:
    evidence_df = evidence_df if isinstance(evidence_df, pd.DataFrame) else pd.DataFrame()
    sections = classify_evidence(evidence_df)
    retention = extract_retention_metrics(sections["Q10"])
    concentration = extract_concentration_candidates(sections["Q8"])
    quality = evidence_quality_coverage(evidence_df)
    gaps = research_gap_suggestions(quality)
    return {
        "provenance": {
            "source_label": source_label,
            "evidence_count": int(len(evidence_df)),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "Research Assistant evidence draft; analyst-controlled; no overwrite",
            "quality_coverage": quality,
        },
        "research_gap_suggestions": gaps,
        "q7": {"core_customer_summary": _evidence_draft(sections["Q7"], "Q7 Core Customer"), "evidence": sections["Q7"].to_dict(orient="records") if not sections["Q7"].empty else []},
        "q8": {"concentration_summary": _evidence_draft(sections["Q8"], "Q8 Customer Concentration", trusted_only=True), "concentration_table": concentration, "evidence": sections["Q8"].to_dict(orient="records") if not sections["Q8"].empty else []},
        "q9": {"sales_friction_summary": _evidence_draft(sections["Q9"], "Q9 Sales Friction"), "evidence": sections["Q9"].to_dict(orient="records") if not sections["Q9"].empty else []},
        "q10": {"retention_summary": _evidence_draft(sections["Q10"], "Q10 Retention", trusted_only=True), "retention_metrics": retention, "evidence": sections["Q10"].to_dict(orient="records") if not sections["Q10"].empty else []},
        "q11": {"customer_orientation_summary": _evidence_draft(sections["Q11"], "Q11 Customer Orientation"), "evidence": sections["Q11"].to_dict(orient="records") if not sections["Q11"].empty else []},
        "q12": {"pain_summary": _evidence_draft(sections["Q12"], "Q12 Customer Pain / Need"), "evidence": sections["Q12"].to_dict(orient="records") if not sections["Q12"].empty else []},
        "q13": {"dependency_reason": _evidence_draft(sections["Q13"], "Q13 Dependency Evidence"), "evidence": sections["Q13"].to_dict(orient="records") if not sections["Q13"].empty else []},
        "q14": {"evidence_draft": _evidence_draft(sections["Q14"], "Q14 Disappearance / Replacement Evidence"), "evidence": sections["Q14"].to_dict(orient="records") if not sections["Q14"].empty else []},
    }


def merge_assistant_draft(record: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    """Fill blank evidence/research fields only; never overwrite analyst classifications or conclusions."""
    merged = deepcopy(record)
    merged.pop("_exists", None)
    for question in ("q7", "q8", "q9", "q10", "q11", "q12", "q13", "q14"):
        merged.setdefault(question, {})

    mapping = (
        ("q7", "core_customer_summary"),
        ("q8", "concentration_summary"),
        ("q9", "sales_friction_summary"),
        ("q10", "retention_summary"),
        ("q11", "customer_orientation_summary"),
        ("q12", "pain_summary"),
        ("q13", "dependency_reason"),
    )
    for question, field in mapping:
        if not str(merged[question].get(field, "") or "").strip():
            merged[question][field] = str(draft.get(question, {}).get(field, "") or "")

    q8_table = draft.get("q8", {}).get("concentration_table") if isinstance(draft, dict) else None
    if not merged["q8"].get("concentration_table") and q8_table:
        merged["q8"]["concentration_table"] = deepcopy(q8_table)

    retention = draft.get("q10", {}).get("retention_metrics", {}) if isinstance(draft, dict) else {}
    if retention:
        if not str(merged["q10"].get("retention_rate", "") or "").strip() and retention.get("retention_rate"):
            merged["q10"]["retention_rate"] = retention["retention_rate"]
        if not str(merged["q10"].get("churn_rate", "") or "").strip() and retention.get("churn_rate"):
            merged["q10"]["churn_rate"] = retention["churn_rate"]
        if str(merged["q10"].get("retention_assessability") or "Unknown") == "Unknown":
            merged["q10"]["retention_assessability"] = "Disclosed metric"
        source = " | ".join(x for x in (retention.get("source", ""), retention.get("title", "")) if x)
        if source and not str(merged["q10"].get("evidence", "") or "").strip():
            merged["q10"]["evidence"] = source

    q14_evidence = str(draft.get("q14", {}).get("evidence_draft", "") or "")
    if q14_evidence and not str(merged["q14"].get("evidence", "") or "").strip():
        merged["q14"]["evidence"] = q14_evidence

    # Explicit guardrails: these analyst judgement fields are never auto-changed.
    # q8 concentration_status, q9 sales_ease_status, q13 dependency_class,
    # q14 impact_level and q14 disappearance_conclusion remain untouched.
    merged["assistant_provenance"] = deepcopy(draft.get("provenance", {})) if isinstance(draft, dict) else {}
    merged["assistant_draft_applied_at"] = datetime.now().isoformat(timespec="seconds")
    return merged
