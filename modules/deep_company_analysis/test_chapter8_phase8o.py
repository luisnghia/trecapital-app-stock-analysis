from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from reportlab.pdfgen import canvas

from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_gap_directed_ocr_v60 import (
    gap_directed_high_res_ocr_pdf_bytes,
    remap_subset_result,
    score_ocr_pages,
    select_high_res_pages,
)
from modules.deep_company_analysis.chapter8_pdf_ocr import OCRPage, PDFOCRResult
from modules.deep_company_analysis.chapter8_research_v60 import Chapter8ResearchAgent


def _pdf(pages: int = 12) -> bytes:
    stream = BytesIO()
    c = canvas.Canvas(stream)
    for _ in range(pages):
        c.showPage()
    c.save()
    return stream.getvalue()


def _targets() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Question": "Q43",
            "Dimension Key": "training",
            "Dimension": "Employee training",
            "Query Terms": "employee training | đào tạo nhân viên | retention | culture",
        },
        {
            "Question": "Q47",
            "Dimension Key": "authorization",
            "Dimension": "Authorization / program",
            "Query Terms": "buyback | share repurchase | mua lại cổ phiếu | cổ phiếu quỹ",
        },
    ])


def _coarse() -> PDFOCRResult:
    pages = (
        OCRPage(2, "DGC production output and sales", "OCR text extracted", 10, 100),
        OCRPage(5, "DGC đào tạo nhân viên employee training retention culture", "OCR text extracted", 10, 100),
        OCRPage(9, "DGC share repurchase buyback authorization mua lại cổ phiếu", "OCR text extracted", 10, 100),
        OCRPage(12, "DGC dividend distribution", "OCR text extracted", 10, 100),
    )
    return PDFOCRResult(
        text=" ".join(f"[[OCR_PAGE:{p.page_number}]] {p.text}" for p in pages),
        method="coarse",
        runtime_ok=True,
        runtime_note="ready",
        languages="vie+eng",
        page_count=12,
        attempted_pages=4,
        successful_pages=4,
        failed_pages=0,
        pages=pages,
    )


def test_v60_scores_only_gap_relevant_pages() -> None:
    frame = score_ocr_pages(_coarse(), _targets())
    assert int(frame.iloc[0]["Score"]) > 0
    assert int(frame.iloc[0]["Page"]) in {5, 9}
    irrelevant = frame[frame["Page"].eq(2)].iloc[0]
    assert int(irrelevant["Score"]) == 0


def test_v60_selects_positive_pages_and_neighbors_bounded() -> None:
    frame = score_ocr_pages(_coarse(), _targets())
    selected = select_high_res_pages(frame, 12, max_pages=6, neighbor_radius=1)
    assert 5 in selected and 9 in selected
    assert len(selected) <= 6
    assert all(1 <= page <= 12 for page in selected)


def test_v60_remaps_subset_page_markers_to_original_pdf() -> None:
    raw = PDFOCRResult(
        text="[[OCR_PAGE:1]] employee training [[OCR_PAGE:2]] share repurchase",
        method="high",
        runtime_ok=True,
        runtime_note="ready",
        languages="vie+eng",
        page_count=2,
        attempted_pages=2,
        successful_pages=2,
        failed_pages=0,
        pages=(
            OCRPage(1, "employee training", "OCR text extracted", 10, 100),
            OCRPage(2, "share repurchase", "OCR text extracted", 10, 100),
        ),
    )
    mapped = remap_subset_result(raw, (5, 9), 12)
    assert "[[OCR_PAGE:5]]" in mapped.text
    assert "[[OCR_PAGE:9]]" in mapped.text
    assert [page.page_number for page in mapped.pages] == [5, 9]
    assert mapped.page_count == 12


def test_v60_two_stage_engine_high_res_is_gap_directed() -> None:
    coarse = _coarse()
    high = PDFOCRResult(
        text="[[OCR_PAGE:1]] employee training retention [[OCR_PAGE:2]] buyback authorization",
        method="high 220dpi",
        runtime_ok=True,
        runtime_note="ready",
        languages="vie+eng",
        page_count=2,
        attempted_pages=2,
        successful_pages=2,
        failed_pages=0,
        pages=(
            OCRPage(1, "employee training retention", "OCR text extracted", 10, 100),
            OCRPage(2, "buyback authorization", "OCR text extracted", 10, 100),
        ),
    )
    with patch("modules.deep_company_analysis.chapter8_gap_directed_ocr_v60.ocr_pdf_bytes", side_effect=[coarse, high]):
        result = gap_directed_high_res_ocr_pdf_bytes(
            _pdf(12),
            targets=_targets(),
            high_res_max_pages=2,
            neighbor_radius=0,
        )
    assert result.high_res is not None
    assert set(result.selected_high_res_pages).issubset({5, 9})
    assert "Phase 8O gap-directed OCR" in result.combined.method
    assert "OCR_PAGE:5" in result.combined.text or "OCR_PAGE:9" in result.combined.text


def test_v60_research_wrapper_uses_gap_directed_agent(tmp_path: Path) -> None:
    agent = Chapter8ResearchAgent(tmp_path)
    with patch("modules.deep_company_analysis.chapter8_research_v60.OfficialFileIngestionAgentV60.ingest", return_value="sentinel") as mocked:
        out = agent.ingest_official_files("DGC", [], existing_candidates=pd.DataFrame())
    assert out == "sentinel"
    assert mocked.call_args.kwargs["enable_ocr"] is True
    assert mocked.call_args.kwargs["high_res_dpi"] == 220


def test_v60_preserves_source_locks_and_analyst_boundary() -> None:
    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q47_share_count_is_proof"] is False
