from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.pdfgen import canvas

from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_official_file_ingestion import (
    OFFICIAL_ISSUER_OPTIONS,
    OfficialFileIngestionAgent,
    extract_official_file_text,
)
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS


def _pdf_bytes(text: str) -> bytes:
    stream = BytesIO()
    c = canvas.Canvas(stream)
    c.drawString(72, 760, text)
    c.save()
    return stream.getvalue()


def _empty_candidates() -> pd.DataFrame:
    return pd.DataFrame(columns=CANDIDATE_COLUMNS)


def test_v57_extracts_text_from_pdf_without_network() -> None:
    text, method = extract_official_file_text("DGC_report.pdf", _pdf_bytes("DGC dividend capital allocation and employee training"))
    assert "DGC" in text
    assert "dividend" in text.lower()
    assert "PDF" in method


def test_v57_accepts_confirmed_official_file_without_url_but_marks_provenance_pending(tmp_path: Path) -> None:
    result = OfficialFileIngestionAgent(tmp_path).ingest(
        "DGC",
        [{
            "name": "DGC_annual_report.txt",
            "bytes": b"DGC annual report dividend capital allocation employee training cost efficiency",
            "issuer": "Company/IR",
            "source_url": "",
            "official_confirmed": True,
        }],
        existing_candidates=_empty_candidates(),
    )
    assert result.attempts.iloc[0]["Status"] == "Accepted"
    assert result.attempts.iloc[0]["Ticker Match"] == "Yes"
    assert result.attempts.iloc[0]["Source Grade"].startswith("A?")
    assert result.raw_paths and Path(result.raw_paths[0]).exists()
    assert not result.new_candidates.empty
    assert result.new_candidates["Status"].eq("Candidate — analyst verify").all()
    assert result.new_candidates["Select"].eq(False).all()
    assert result.new_candidates["Source Grade"].str.startswith("A?").all()


def test_v57_verified_official_url_can_prove_source_provenance(tmp_path: Path) -> None:
    result = OfficialFileIngestionAgent(tmp_path).ingest(
        "DGC",
        [{
            "name": "DGC_disclosure.txt",
            "bytes": b"DGC dividend payment and capital allocation disclosure",
            "issuer": "HOSE/HSX",
            "source_url": "https://staticfile.hsx.vn/Uploads/UploadDocuments/DGC-disclosure.pdf",
            "official_confirmed": False,
        }],
        existing_candidates=_empty_candidates(),
    )
    assert result.attempts.iloc[0]["Status"] == "Accepted"
    assert result.attempts.iloc[0]["Official Provenance"] == "Verified official URL"
    assert result.attempts.iloc[0]["Source Grade"].startswith("A —")
    if not result.new_candidates.empty:
        assert result.new_candidates["Source Grade"].str.startswith("A —").all()


def test_v57_rejects_nonofficial_source_url_even_if_user_confirms(tmp_path: Path) -> None:
    result = OfficialFileIngestionAgent(tmp_path).ingest(
        "DGC",
        [{
            "name": "DGC_news.txt",
            "bytes": b"DGC dividend capital allocation",
            "issuer": "Company/IR",
            "source_url": "https://cafef.vn/dgc.htm",
            "official_confirmed": True,
        }],
        existing_candidates=_empty_candidates(),
    )
    assert result.attempts.iloc[0]["Status"] == "Rejected: source URL is not on official allow-list"
    assert result.new_candidates.empty


def test_v57_rejects_wrong_ticker_file(tmp_path: Path) -> None:
    result = OfficialFileIngestionAgent(tmp_path).ingest(
        "DGC",
        [{
            "name": "HPG_report.txt",
            "bytes": b"HPG annual report dividend and employee training",
            "issuer": "Company/IR",
            "source_url": "",
            "official_confirmed": True,
        }],
        existing_candidates=_empty_candidates(),
    )
    assert result.attempts.iloc[0]["Status"] == "Rejected: ticker mismatch"
    assert result.attempts.iloc[0]["Ticker Match"] == "No"
    assert result.new_candidates.empty


def test_v57_requires_confirmation_when_no_official_url(tmp_path: Path) -> None:
    result = OfficialFileIngestionAgent(tmp_path).ingest(
        "DGC",
        [{
            "name": "DGC_report.txt",
            "bytes": b"DGC dividend capital allocation",
            "issuer": "Company/IR",
            "source_url": "",
            "official_confirmed": False,
        }],
        existing_candidates=_empty_candidates(),
    )
    assert result.attempts.iloc[0]["Status"] == "Rejected: official provenance not confirmed"


def test_v57_issuer_contract_is_bounded() -> None:
    assert OFFICIAL_ISSUER_OPTIONS == ("Company/IR", "HOSE/HSX", "HNX", "SSC")


def test_v57_preserves_chapter8_source_locks() -> None:
    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q47_share_count_is_proof"] is False
