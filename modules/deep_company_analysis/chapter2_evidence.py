from __future__ import annotations

"""Source-first evidence engine for Shearn Chapter 2.

The generic Module 2 web helper deliberately limits search-engine calls. Chapter 2 needs deeper
business understanding, so this adapter adds three things without introducing a parallel financial
source: (1) all Chapter 2 targeted queries, (2) official-company HTML evidence, and (3) cached
official annual-report PDF text when HTML/search snippets are insufficient.

Everything returned here is evidence candidate material. It is never an analyst conclusion.
"""

from io import BytesIO
from pathlib import Path
from typing import Any
import json
import re

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

from adapters.module2_web_research import EvidenceResult, HEADERS
from modules.deep_company_analysis import chapter2_auto as base


# Trecapital already maintains ticker-specific trusted IR roots. These deeper pages are an extension
# for Chapter 2 business-understanding evidence and can be expanded ticker-by-ticker over time.
CHAPTER2_OFFICIAL_PAGES: dict[str, tuple[tuple[str, str], ...]] = {
    "DGC": (
        ("Giới thiệu doanh nghiệp", "https://ducgiangchem.vn/gioi-thieu/"),
        ("Lịch sử phát triển", "https://ducgiangchem.vn/gioi-thieu/lich-su-phat-trien/"),
        ("Danh mục sản phẩm", "https://ducgiangchem.vn/san-pham-duc-giang/"),
        ("Báo cáo thường niên", "https://ducgiangchem.vn/category/quan-he-co-dong/bao-cao-thuong-nien/"),
    ),
}

CHAPTER2_OFFICIAL_PDFS: dict[str, tuple[tuple[str, str], ...]] = {
    "DGC": (
        (
            "Báo cáo thường niên 2025",
            "https://ducgiangchem.vn/wp-content/uploads/2026/04/20260407-DGC-CBTT-Bao-cao-thuong-nien-2025.pdf",
        ),
    ),
}


def _clean_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in str(text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" \t•-–—")
        if len(line) < 3:
            continue
        if out and line == out[-1]:
            continue
        out.append(line)
    return out


def _context(lines: list[str], index: int, radius: int = 1, limit: int = 650) -> str:
    start = max(0, index - radius)
    stop = min(len(lines), index + radius + 1)
    return " | ".join(lines[start:stop])[:limit]


def _country_currency_keywords() -> tuple[str, ...]:
    values: list[str] = list(base.Q6_KEYWORDS)
    for aliases in base.COUNTRY_ALIASES.values():
        values.extend(aliases)
    for aliases in base.CURRENCY_ALIASES.values():
        values.extend(aliases)
    return tuple(dict.fromkeys(values))


Q6_EXTENDED_KEYWORDS = _country_currency_keywords()


def _topic_rows(*, ticker: str, page_title: str, url: str, text: str, source_kind: str) -> list[dict[str, Any]]:
    lines = _clean_lines(text)
    rows: list[dict[str, Any]] = []
    specs = (
        ("Q3", base.Q3_KEYWORDS, 5),
        ("Q4", base.Q4_KEYWORDS, 4),
        ("Q5", base.Q5_KEYWORDS, 12),
        ("Q6", Q6_EXTENDED_KEYWORDS, 10),
    )
    for question, keywords, max_rows in specs:
        seen: set[str] = set()
        count = 0
        for idx, line in enumerate(lines):
            # Q5 timeline evidence is much safer when a year is present. Keep non-year Q5 snippets
            # only when they clearly describe history/M&A/capacity/project context.
            if question == "Q5" and not re.search(r"\b(?:19|20)\d{2}\b", line):
                if not base._contains_any(line, ("lịch sử", "lich su", "history", "mua lại", "mua lai", "sáp nhập", "sap nhap", "dự án", "du an", "công suất", "cong suat")):
                    continue
            if not base._contains_any(line, keywords):
                continue
            snippet = _context(lines, idx, radius=1)
            key = base._norm(snippet)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "Nhóm thông tin": f"Nguồn doanh nghiệp/IR | {question}",
                    "Tiêu đề": f"{ticker} — {page_title} — {question} evidence {count + 1}",
                    "Nguồn/URL": url,
                    "Tên miền": "ducgiangchem.vn" if "ducgiangchem.vn" in url else "",
                    "Trích yếu": snippet,
                    "Trạng thái": "Evidence trích từ nguồn chính thức",
                    "Gợi ý sử dụng": f"{source_kind}; mở nguồn gốc để analyst xác minh trước khi dùng trong {question}.",
                    "Truy vấn": "Official source direct fetch",
                    "Điểm phù hợp": 60,
                }
            )
            count += 1
            if count >= max_rows:
                break
    return rows


def _main_text_from_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    title = re.sub(r"\s+", " ", soup.title.get_text(" ", strip=True) if soup.title else "").strip()
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()
    container = (
        soup.find("article")
        or soup.find(class_=re.compile(r"entry-content|post-content|article-content|page-content", re.I))
        or soup.find("main")
        or soup.body
        or soup
    )
    return title, container.get_text("\n", strip=True)


class SourceFirstChapter2EvidenceAgent(base.Chapter2EvidenceAgent):
    """Chapter 2 evidence search that prioritizes source content over search-result placeholders."""

    def _fetch_official_html_rows(self, ticker: str, client: httpx.Client) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        rows: list[dict[str, Any]] = []
        audit: list[dict[str, str]] = []
        for label, url in CHAPTER2_OFFICIAL_PAGES.get(ticker, ()):
            try:
                response = client.get(url, timeout=5.0)
                response.raise_for_status()
                page_title, text = _main_text_from_html(response.text)
                extracted = _topic_rows(
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

    def _pdf_cache_paths(self, ticker: str, label: str) -> tuple[Path, Path]:
        folder = Path(self.raw_dir) / "chapter2_official" / ticker
        folder.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_")[:80] or "annual_report"
        return folder / f"{safe}.pdf", folder / f"{safe}.txt"

    def _official_pdf_text(self, ticker: str, label: str, url: str, client: httpx.Client) -> tuple[str, str]:
        pdf_path, text_path = self._pdf_cache_paths(ticker, label)
        if text_path.exists() and text_path.stat().st_size > 1000:
            return text_path.read_text(encoding="utf-8", errors="ignore"), "cached-text"
        try:
            if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                content = pdf_path.read_bytes()
            else:
                response = client.get(url, timeout=20.0)
                response.raise_for_status()
                content = response.content
                if len(content) > 25 * 1024 * 1024:
                    return "", "pdf-too-large"
                pdf_path.write_bytes(content)
            reader = PdfReader(BytesIO(content))
            pages: list[str] = []
            for page in reader.pages[:180]:
                try:
                    page_text = page.extract_text() or ""
                except Exception:
                    page_text = ""
                if page_text.strip():
                    pages.append(page_text)
                if sum(len(x) for x in pages) > 2_500_000:
                    break
            text = "\n".join(pages)
            if text.strip():
                text_path.write_text(text, encoding="utf-8")
            return text, f"parsed-{len(pages)}-pages"
        except Exception as exc:
            return "", f"pdf-error:{str(exc)[:180]}"

    def _fetch_official_pdf_rows(self, ticker: str, client: httpx.Client) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        rows: list[dict[str, Any]] = []
        audit: list[dict[str, str]] = []
        for label, url in CHAPTER2_OFFICIAL_PDFS.get(ticker, ()):
            text, status = self._official_pdf_text(ticker, label, url, client)
            extracted = _topic_rows(
                ticker=ticker,
                page_title=label,
                url=url,
                text=text,
                source_kind="PDF/BCTN chính thức của doanh nghiệp",
            ) if text else []
            rows.extend(extracted)
            audit.append({"url": url, "status": status, "rows": str(len(extracted))})
        return rows, audit

    def _search_remaining_queries(self, ticker: str, company_name: str, client: httpx.Client, max_results_per_query: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        audit: list[dict[str, Any]] = []
        queries = self._build_queries(ticker, company_name)
        # super().search() already executes the first two due the generic module's latency guardrail.
        for query in queries[2:]:
            found, payload = self._search_duckduckgo(client, query, max_results_per_query)
            if not found:
                found_bing, bing_payload = self._search_bing(client, query, max_results_per_query)
                payload["fallback_bing"] = bing_payload
                found = found_bing
            rows.extend(found)
            audit.append(payload)
        return rows, audit

    def search(self, ticker: str, company_name: str = "", max_results_per_query: int = 5) -> EvidenceResult:  # type: ignore[override]
        safe = str(ticker or "").upper().strip()
        company_name = re.sub(r"\s+", " ", str(company_name or "")).strip()
        base_result = super().search(safe, company_name, max_results_per_query=max_results_per_query)
        rows = base_result.table.to_dict(orient="records") if isinstance(base_result.table, pd.DataFrame) else []
        audit: dict[str, Any] = {
            "ticker": safe,
            "company_name": company_name,
            "mode": "Chapter 2 source-first evidence",
            "base_raw_path": str(base_result.raw_path or ""),
            "remaining_queries": [],
            "official_html": [],
            "official_pdf": [],
        }

        with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(3.0, connect=1.2), follow_redirects=True) as client:
            extra_rows, query_audit = self._search_remaining_queries(safe, company_name, client, max_results_per_query)
            rows.extend(extra_rows)
            audit["remaining_queries"] = query_audit

            html_rows, html_audit = self._fetch_official_html_rows(safe, client)
            rows.extend(html_rows)
            audit["official_html"] = html_audit

            interim = pd.DataFrame(rows)
            sections = base.classify_evidence(interim) if not interim.empty else {"Q6": pd.DataFrame()}
            # Parse the official annual report only when Q6 is still weak. This avoids a large PDF
            # download on every refresh while giving Chapter 2 a source-first fallback for geography/FX.
            q6 = sections.get("Q6", pd.DataFrame())
            q6_quality = 0 if not isinstance(q6, pd.DataFrame) else len(q6)
            if q6_quality < 2 and CHAPTER2_OFFICIAL_PDFS.get(safe):
                pdf_rows, pdf_audit = self._fetch_official_pdf_rows(safe, client)
                rows.extend(pdf_rows)
                audit["official_pdf"] = pdf_audit

        final = pd.DataFrame(rows)
        if not final.empty:
            for col in ("Tiêu đề", "Nguồn/URL"):
                if col not in final.columns:
                    final[col] = ""
            final = final.drop_duplicates(subset=["Tiêu đề", "Nguồn/URL"], keep="first").reset_index(drop=True)
            if "Điểm phù hợp" in final.columns:
                final["Điểm phù hợp"] = pd.to_numeric(final["Điểm phù hợp"], errors="coerce").fillna(0)
                final = final.sort_values("Điểm phù hợp", ascending=False).reset_index(drop=True)

        # Save the *final* evidence table as well, not only search-engine query payloads. This fixes
        # offline reruns: load_cached_evidence() can recover official/direct evidence after restart.
        audit["chapter2_final_rows"] = final.to_dict(orient="records") if not final.empty else []
        audit_path = self._save_raw(safe, audit)
        note = f"Chapter 2 source-first evidence: {len(final)} rows; cache: {audit_path}"
        return EvidenceResult(final, audit_path, note)
