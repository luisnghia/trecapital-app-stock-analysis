from __future__ import annotations

"""Chapter 8 Phase 8O / V60 — gap-directed high-resolution OCR.

V59 proved that bounded OCR can recover real evidence from scanned official PDFs, but broad sampling
still spends most OCR time on pages unrelated to the remaining source-locked dimensions. V60 adds a
second, evidence-conservative pass:

1. run a cheap, document-wide sampled OCR pass;
2. score OCR pages only against the *currently open* Chapter 8 source-locked dimensions;
3. select a small number of high-value pages plus immediate neighbors;
4. re-OCR only those pages at higher resolution;
5. remap every OCR marker back to the original PDF page number;
6. return candidate text only. Nothing is promoted and no analyst conclusion is written.

Chapter 7 remains the manager identity SSOT and Trecapital canonical remains the financial SSOT.
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Any
import re
import unicodedata

import pandas as pd
from pypdf import PdfReader, PdfWriter

from modules.deep_company_analysis.chapter8_pdf_ocr import (
    PDFOCRResult,
    OCRPage,
    ocr_pdf_bytes,
)


DEFAULT_COARSE_DPI = 110
DEFAULT_COARSE_MAX_PAGES = 36
DEFAULT_COARSE_WORKERS = 4
DEFAULT_HIGHRES_DPI = 220
DEFAULT_HIGHRES_MAX_PAGES = 10
DEFAULT_HIGHRES_WORKERS = 4
DEFAULT_NEIGHBOR_RADIUS = 1

SCORE_COLUMNS = ["Page", "Score", "Matched Dimensions", "Matched Terms"]


@dataclass(frozen=True)
class GapDirectedOCRResult:
    combined: PDFOCRResult
    coarse: PDFOCRResult
    high_res: PDFOCRResult | None
    page_scores: pd.DataFrame
    selected_high_res_pages: tuple[int, ...]
    target_dimension_count: int
    note: str


def _safe(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _safe(value).casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _target_groups(targets: pd.DataFrame) -> list[tuple[str, tuple[str, ...]]]:
    if not isinstance(targets, pd.DataFrame) or targets.empty:
        return []
    groups: list[tuple[str, tuple[str, ...]]] = []
    for _, row in targets.iterrows():
        question = _safe(row.get("Question"))
        key = _safe(row.get("Dimension Key"))
        label = _safe(row.get("Dimension"))
        raw_terms = [part.strip() for part in _safe(row.get("Query Terms")).split("|") if part.strip()]
        if label:
            raw_terms.append(label)
        seen: set[str] = set()
        terms: list[str] = []
        for term in raw_terms:
            folded = _fold(term)
            if len(folded) < 3 or folded in seen:
                continue
            seen.add(folded)
            terms.append(folded)
        if terms:
            groups.append((f"{question}:{key}", tuple(terms)))
    return groups


def score_ocr_pages(coarse: PDFOCRResult, targets: pd.DataFrame) -> pd.DataFrame:
    """Rank coarse OCR pages by evidence relevance to currently open dimensions only."""
    groups = _target_groups(targets)
    rows: list[dict[str, Any]] = []
    for page in coarse.pages:
        text = _fold(page.text)
        score = 0
        matched_dimensions: list[str] = []
        matched_terms: list[str] = []
        if text:
            for dimension, terms in groups:
                group_score = 0
                group_hits: list[str] = []
                for term in terms:
                    if term in text:
                        group_score += 5 if " " in term else 3
                        group_hits.append(term)
                    else:
                        # Phrase OCR can be noisy. Long individual tokens are a weak fallback,
                        # but never sufficient to turn OCR text into approved evidence.
                        tokens = [tok for tok in re.findall(r"[a-z0-9]+", term) if len(tok) >= 6]
                        token_hits = sum(1 for token in tokens[:6] if token in text)
                        group_score += min(token_hits, 2)
                if group_score > 0:
                    score += group_score
                    matched_dimensions.append(dimension)
                    matched_terms.extend(group_hits[:3])
        rows.append({
            "Page": int(page.page_number),
            "Score": int(score),
            "Matched Dimensions": ", ".join(dict.fromkeys(matched_dimensions)),
            "Matched Terms": " | ".join(dict.fromkeys(matched_terms)),
        })
    frame = pd.DataFrame(rows, columns=SCORE_COLUMNS)
    if frame.empty:
        return frame
    return frame.sort_values(["Score", "Page"], ascending=[False, True], kind="stable").reset_index(drop=True)


def select_high_res_pages(
    page_scores: pd.DataFrame,
    page_count: int,
    *,
    max_pages: int = DEFAULT_HIGHRES_MAX_PAGES,
    neighbor_radius: int = DEFAULT_NEIGHBOR_RADIUS,
) -> tuple[int, ...]:
    """Pick positive-score pages plus close neighbors, bounded by ``max_pages``."""
    if not isinstance(page_scores, pd.DataFrame) or page_scores.empty:
        return ()
    count = max(0, int(page_count))
    limit = max(1, min(int(max_pages), 24))
    radius = max(0, min(int(neighbor_radius), 2))
    ranked = page_scores[pd.to_numeric(page_scores["Score"], errors="coerce").fillna(0) > 0]
    if ranked.empty or count <= 0:
        return ()

    selected: list[int] = []
    seen: set[int] = set()
    for _, row in ranked.iterrows():
        center = int(row["Page"])
        neighborhood = [center]
        for step in range(1, radius + 1):
            neighborhood.extend([center - step, center + step])
        for page in neighborhood:
            if page < 1 or page > count or page in seen:
                continue
            selected.append(page)
            seen.add(page)
            if len(selected) >= limit:
                return tuple(sorted(selected))
    return tuple(sorted(selected))


def _subset_pdf(data: bytes, pages: tuple[int, ...]) -> tuple[bytes, tuple[int, ...]]:
    reader = PdfReader(BytesIO(data))
    writer = PdfWriter()
    mapping: list[int] = []
    for original_page in pages:
        index = int(original_page) - 1
        if 0 <= index < len(reader.pages):
            writer.add_page(reader.pages[index])
            mapping.append(int(original_page))
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue(), tuple(mapping)


def _remap_marker_text(text: str, mapping: tuple[int, ...]) -> str:
    def repl(match: re.Match[str]) -> str:
        subset_page = int(match.group(1))
        if 1 <= subset_page <= len(mapping):
            return f"[[OCR_PAGE:{mapping[subset_page - 1]}]]"
        return match.group(0)
    return re.sub(r"\[\[OCR_PAGE:(\d+)\]\]", repl, str(text or ""))


def remap_subset_result(result: PDFOCRResult, mapping: tuple[int, ...], original_page_count: int) -> PDFOCRResult:
    pages: list[OCRPage] = []
    for page in result.pages:
        subset_page = int(page.page_number)
        original = mapping[subset_page - 1] if 1 <= subset_page <= len(mapping) else subset_page
        pages.append(OCRPage(original, page.text, page.status, page.duration_ms, page.image_bytes))
    return PDFOCRResult(
        text=_remap_marker_text(result.text, mapping),
        method=result.method,
        runtime_ok=result.runtime_ok,
        runtime_note=result.runtime_note,
        languages=result.languages,
        page_count=int(original_page_count),
        attempted_pages=result.attempted_pages,
        successful_pages=result.successful_pages,
        failed_pages=result.failed_pages,
        pages=tuple(pages),
    )


def _combine_results(coarse: PDFOCRResult, high_res: PDFOCRResult | None) -> PDFOCRResult:
    if high_res is None:
        return coarse
    high_pages = {page.page_number for page in high_res.pages if page.text}
    merged_pages = list(high_res.pages)
    merged_pages.extend(page for page in coarse.pages if page.page_number not in high_pages)
    merged_pages.sort(key=lambda item: item.page_number)
    attempted = {page.page_number for page in coarse.pages} | {page.page_number for page in high_res.pages}
    successful = {page.page_number for page in merged_pages if page.text}
    text = " ".join(part for part in (high_res.text, coarse.text) if _safe(part)).strip()
    note = f"{coarse.runtime_note}; V60 high-res selected={','.join(str(x) for x in sorted(high_pages)) or 'none'}"
    return PDFOCRResult(
        text=text,
        method=f"Phase 8O gap-directed OCR — coarse [{coarse.method}] + high-res [{high_res.method}]",
        runtime_ok=coarse.runtime_ok and high_res.runtime_ok,
        runtime_note=note,
        languages=coarse.languages,
        page_count=coarse.page_count,
        attempted_pages=len(attempted),
        successful_pages=len(successful),
        failed_pages=max(0, len(attempted) - len(successful)),
        pages=tuple(merged_pages),
    )


def gap_directed_high_res_ocr_pdf_bytes(
    data: bytes,
    *,
    targets: pd.DataFrame,
    languages: str = "vie+eng",
    dpi: int = DEFAULT_COARSE_DPI,
    max_pages: int = DEFAULT_COARSE_MAX_PAGES,
    workers: int = DEFAULT_COARSE_WORKERS,
    high_res_dpi: int = DEFAULT_HIGHRES_DPI,
    high_res_max_pages: int = DEFAULT_HIGHRES_MAX_PAGES,
    neighbor_radius: int = DEFAULT_NEIGHBOR_RADIUS,
) -> GapDirectedOCRResult:
    """Run a bounded coarse pass, then high-resolution OCR only where open gaps point."""
    target_count = int(len(targets)) if isinstance(targets, pd.DataFrame) else 0
    coarse = ocr_pdf_bytes(
        data,
        languages=languages,
        dpi=max(110, int(dpi)),
        max_pages=max(8, min(int(max_pages), 48)),
        workers=max(1, min(int(workers), 4)),
        psm=11,
        page_timeout_seconds=9,
        time_budget_seconds=180,
    )
    scores = score_ocr_pages(coarse, targets)
    selected = select_high_res_pages(
        scores,
        coarse.page_count,
        max_pages=high_res_max_pages,
        neighbor_radius=neighbor_radius,
    )
    if not selected:
        note = (
            f"V60 gap-directed OCR: {target_count} open dimension target(s); coarse OCR produced no "
            "positive target-page score, so no high-resolution pass was run."
        )
        return GapDirectedOCRResult(coarse, coarse, None, scores, (), target_count, note)

    subset, mapping = _subset_pdf(data, selected)
    high_raw = ocr_pdf_bytes(
        subset,
        languages=languages,
        dpi=max(180, min(int(high_res_dpi), 260)),
        max_pages=max(1, len(mapping)),
        workers=DEFAULT_HIGHRES_WORKERS,
        psm=6,
        page_timeout_seconds=18,
        time_budget_seconds=150,
    )
    high = remap_subset_result(high_raw, mapping, coarse.page_count)
    combined = _combine_results(coarse, high)
    note = (
        f"V60 gap-directed OCR: {target_count} open dimension target(s); coarse sampled {coarse.attempted_pages} "
        f"page(s), selected {len(selected)} original page(s) for {high_res_dpi}dpi high-resolution OCR; "
        f"combined pages with text={combined.successful_pages}. OCR remains candidate-only."
    )
    return GapDirectedOCRResult(combined, coarse, high, scores, selected, target_count, note)


__all__ = [
    "DEFAULT_COARSE_DPI",
    "DEFAULT_COARSE_MAX_PAGES",
    "DEFAULT_HIGHRES_DPI",
    "DEFAULT_HIGHRES_MAX_PAGES",
    "GapDirectedOCRResult",
    "SCORE_COLUMNS",
    "gap_directed_high_res_ocr_pdf_bytes",
    "remap_subset_result",
    "score_ocr_pages",
    "select_high_res_pages",
]
