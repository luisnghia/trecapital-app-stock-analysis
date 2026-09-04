from __future__ import annotations

"""Registered direct sources for Chapter 4 Phase 4C.2.

The generic engine remains ticker-agnostic. This registry lets Trecapital add trusted, directly
fetchable company/independent research sources for acceptance stocks and gradually expand coverage.
Rows remain candidate evidence only.
"""

from io import BytesIO
from pathlib import Path
from typing import Any
import re

import httpx
import pandas as pd
from pypdf import PdfReader

from adapters.module2_web_research import HEADERS
from modules.deep_company_analysis.chapter2_evidence import _main_text_from_html
from modules.deep_company_analysis.chapter4_evidence import OFFICIAL_EVIDENCE_STATUS_PREFIX, _clean_lines, _context, _norm


REGISTERED_HTML_SOURCES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "DGC": (
        (
            "A — Company/Official disclosure",
            "DGC — 6T2025 lợi nhuận tăng nhờ cải thiện giá bán",
            "https://ducgiangchem.vn/dgc-but-toc-6-thang-dau-nam-2025-loi-nhuan-tang-gan-30-nho-cai-thien-gia-ban/",
        ),
        (
            "B — Independent research",
            "Vietcap — DGC AGM 2025",
            "https://www.vietcap.com.vn/trung-tam-phan-tich/dgc-nhu-cau-photpho-tiep-tuc-cai-thien-du-an-xut-clo-dung-tien-do-du-an-boxit-tang-toc-bao-cao-dhcd",
        ),
        (
            "B — Independent research",
            "VNDIRECT — DGC Thiên thời, địa lợi",
            "https://www.vndirect.com.vn/dgc-thien-thoi-dia-loi-cap-nhatv2/",
        ),
    ),
}

REGISTERED_PDF_SOURCES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "DGC": (
        (
            "B — Independent research",
            "MBS — DGC Stock Report 12/06/2025",
            "https://www.mbs.com.vn/files/uploads/2025/06/DGC_BCPT_20250612_EN_1.pdf",
        ),
    ),
}

PRICE_TERMS = (
    "giá bán", "giá bán trung bình", "giá bán bình quân", "average selling price", "selling price", "asp",
    "tăng giá", "price increase", "price", "pricing",
)
Q19_TERMS = (
    "đối thủ", "competitor", "competition", "cạnh tranh", "thị phần", "market share", "công suất", "capacity",
    "substitute", "thay thế", "trung quốc", "china", "nhập khẩu", "import", "price war", "chiến tranh giá",
    "dẫn đầu", "leader", "rút lui", "exit", "thất bại", "failed", "failure", "phá sản", "bankrupt",
)


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    normalized = _norm(text)
    return any(_norm(term) in normalized for term in terms)


def _cache_path(raw_dir: str | Path, ticker: str, label: str) -> Path:
    folder = Path(raw_dir) / "chapter4_c2_registered" / ticker
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_")[:90] or "source"
    return folder / f"{safe}.txt"


def _pdf_text(raw_dir: str | Path, ticker: str, label: str, url: str, client: httpx.Client) -> tuple[str, str]:
    cache = _cache_path(raw_dir, ticker, label)
    if cache.exists() and cache.stat().st_size > 800:
        return cache.read_text(encoding="utf-8", errors="ignore"), "cached-text"
    try:
        response = client.get(url, timeout=20.0)
        response.raise_for_status()
        content = response.content
        if len(content) > 30 * 1024 * 1024:
            return "", "pdf-too-large"
        reader = PdfReader(BytesIO(content))
        pages: list[str] = []
        chars = 0
        for page in reader.pages[:160]:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                pages.append(text)
                chars += len(text)
            if chars > 2_000_000:
                break
        full = "\n".join(pages)
        if full.strip():
            cache.write_text(full, encoding="utf-8")
        return full, f"parsed-{len(pages)}-pages"
    except Exception as exc:
        return "", f"pdf-error:{str(exc)[:180]}"


def _extract_rows(
    *,
    ticker: str,
    label: str,
    url: str,
    text: str,
    source_group: str,
    source_method: str,
    purpose: str,
) -> list[dict[str, Any]]:
    terms = PRICE_TERMS if purpose == "Q16" else Q19_TERMS
    lines = _clean_lines(text)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    radius = 3 if purpose == "Q16" else 2
    max_rows = 18 if purpose == "Q16" else 24
    for idx, line in enumerate(lines):
        if not _contains(line, terms):
            continue
        snippet = _context(lines, idx, radius=radius, limit=1500)
        key = _norm(snippet)
        if not key or key in seen:
            continue
        seen.add(key)
        is_official = source_group.startswith("A —")
        rows.append({
            "Nhóm thông tin": source_group,
            "Tiêu đề": f"{ticker} — {label} — {purpose} registered evidence {len(seen)}",
            "Nguồn/URL": url,
            "Tên miền": re.sub(r"^www\.", "", httpx.URL(url).host or "") if url else "",
            "Trích yếu": snippet,
            "Trạng thái": OFFICIAL_EVIDENCE_STATUS_PREFIX if is_official else "Tìm thấy",
            "Gợi ý sử dụng": f"Registered {source_group}; analyst mở nguồn gốc để xác minh {purpose}.",
            "Truy vấn": "Registered direct source",
            "Điểm phù hợp": 90 if is_official else 82,
            "_SourceMethod": source_method,
        })
        if len(seen) >= max_rows:
            break
    return rows


def _fetch_registered(raw_dir: str | Path, ticker: str, purpose: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    safe = str(ticker or "").upper().strip()
    rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(8.0, connect=2.0), follow_redirects=True) as client:
        for group, label, url in REGISTERED_HTML_SOURCES.get(safe, ()):
            try:
                response = client.get(url)
                response.raise_for_status()
                _title, text = _main_text_from_html(response.text)
                extracted = _extract_rows(
                    ticker=safe,
                    label=label,
                    url=url,
                    text=text,
                    source_group=group,
                    source_method=f"Registered {'official' if group.startswith('A —') else 'independent'} HTML direct extraction",
                    purpose=purpose,
                )
                rows.extend(extracted)
                audit.append({"url": url, "status": response.status_code, "purpose": purpose, "rows": len(extracted)})
            except Exception as exc:
                audit.append({"url": url, "purpose": purpose, "error": str(exc)[:200], "rows": 0})

        for group, label, url in REGISTERED_PDF_SOURCES.get(safe, ()):
            text, status = _pdf_text(raw_dir, safe, label, url, client)
            extracted = _extract_rows(
                ticker=safe,
                label=label,
                url=url,
                text=text,
                source_group=group,
                source_method=f"Registered {'official' if group.startswith('A —') else 'independent'} PDF direct extraction",
                purpose=purpose,
            ) if text else []
            rows.extend(extracted)
            audit.append({"url": url, "status": status, "purpose": purpose, "rows": len(extracted)})

    if not rows:
        return pd.DataFrame(), audit
    frame = pd.DataFrame(rows)
    return frame.drop_duplicates(subset=["Nguồn/URL", "Trích yếu"], keep="first").reset_index(drop=True), audit


def fetch_registered_pricing_raw(raw_dir: str | Path, ticker: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    return _fetch_registered(raw_dir, ticker, "Q16")


def fetch_registered_q19_raw(raw_dir: str | Path, ticker: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    return _fetch_registered(raw_dir, ticker, "Q19")
