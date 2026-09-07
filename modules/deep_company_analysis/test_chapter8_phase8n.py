from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from reportlab.pdfgen import canvas

from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_official_file_ingestion_v59 import OfficialFileIngestionAgentV59
from modules.deep_company_analysis.chapter8_pdf_ocr import OCRPage, PDFOCRResult, ocr_page_numbers_from_text
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS
from modules.deep_company_analysis.chapter8_research_v59 import Chapter8ResearchAgent


def _blank_pdf() -> bytes:
    stream = BytesIO()
    c = canvas.Canvas(stream)
    c.showPage()
    c.save()
    return stream.getvalue()


def _empty_candidates() -> pd.DataFrame:
    return pd.DataFrame(columns=CANDIDATE_COLUMNS)


def _fake_ocr() -> PDFOCRResult:
    text = (
        "[[OCR_PAGE:2]] DGC employee training retention culture management cost reduction. "
        "[[OCR_PAGE:3]] DGC dividend capital allocation share repurchase buyback authorization."
    )
    return PDFOCRResult(
        text=text,
        method="Tesseract OCR vie+eng via pdftoppm 170dpi (2/2 page(s) with text)",
        runtime_ok=True,
        runtime_note="pdftoppm+tesseract ready; languages=vie+eng",
        languages="vie+eng",
        page_count=2,
        attempted_pages=2,
        successful_pages=2,
        failed_pages=0,
        pages=(
            OCRPage(2, "DGC employee training retention culture management cost reduction", "OCR text extracted", 100, 1234),
            OCRPage(3, "DGC dividend capital allocation share repurchase buyback authorization", "OCR text extracted", 100, 1234),
        ),
    )


def test_v59_page_marker_contract() -> None:
    assert ocr_page_numbers_from_text("a [[OCR_PAGE:12]] b [[OCR_PAGE:2]] c [[OCR_PAGE:12]]") == (2, 12)


def test_v59_ocr_fallback_accepts_scanned_official_pdf_without_autopromotion(tmp_path: Path) -> None:
    with patch("modules.deep_company_analysis.chapter8_official_file_ingestion_v59.ocr_pdf_bytes", return_value=_fake_ocr()):
        result = OfficialFileIngestionAgentV59(tmp_path).ingest(
            "DGC",
            [{
                "name": "DGC_scan.pdf",
                "bytes": _blank_pdf(),
                "issuer": "Company/IR",
                "source_url": "https://ducgiangchem.vn/wp-content/uploads/DGC_scan.pdf",
                "official_confirmed": True,
            }],
            existing_candidates=_empty_candidates(),
            enable_ocr=True,
        )
    attempt = result.attempts.iloc[0]
    assert attempt["Status"] == "Accepted"
    assert attempt["OCR Pages"] == "2/2"
    assert attempt["OCR Language"] == "vie+eng"
    assert int(attempt["Text chars"]) > 0
    if not result.new_candidates.empty:
        assert result.new_candidates["Status"].eq("Candidate — analyst verify").all()
        assert result.new_candidates["Select"].eq(False).all()
        assert result.new_candidates["Source Method"].str.contains("Phase 8N OCR", regex=False).all()
        assert result.new_candidates["Evidence Text / Reference"].str.contains("OCR_PAGE", regex=False).all()


def test_v59_ocr_unavailable_stays_explicit_gap(tmp_path: Path) -> None:
    unavailable = PDFOCRResult("", "OCR unavailable", False, "missing binary: tesseract", "vie+eng", 1, 1, 0, 1, ())
    with patch("modules.deep_company_analysis.chapter8_official_file_ingestion_v59.ocr_pdf_bytes", return_value=unavailable):
        result = OfficialFileIngestionAgentV59(tmp_path).ingest(
            "DGC",
            [{
                "name": "DGC_scan.pdf",
                "bytes": _blank_pdf(),
                "issuer": "Company/IR",
                "source_url": "https://ducgiangchem.vn/wp-content/uploads/DGC_scan.pdf",
                "official_confirmed": True,
            }],
            existing_candidates=_empty_candidates(),
            enable_ocr=True,
        )
    assert "no extractable text after OCR" in result.attempts.iloc[0]["Status"]
    assert result.new_candidates.empty


def test_v59_research_wrapper_enables_ocr_by_default(tmp_path: Path) -> None:
    agent = Chapter8ResearchAgent(tmp_path)
    with patch("modules.deep_company_analysis.chapter8_research_v59.OfficialFileIngestionAgentV59.ingest", return_value="sentinel") as mocked:
        out = agent.ingest_official_files("DGC", [], existing_candidates=_empty_candidates())
    assert out == "sentinel"
    assert mocked.call_args.kwargs["enable_ocr"] is True
    assert mocked.call_args.kwargs["ocr_languages"] == "vie+eng"


def test_v59_preserves_chapter8_source_and_analyst_boundaries() -> None:
    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q47_share_count_is_proof"] is False
