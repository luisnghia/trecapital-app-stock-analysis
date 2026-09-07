from __future__ import annotations

"""Chapter 8 Phase 8N — OCR-capable official file ingestion.

This extends the V57 file-ingestion contract without changing V57 behavior. OCR is attempted only
when ordinary PDF extraction yields no text and the caller enables it. Every OCR-derived row remains
``Candidate — analyst verify`` and carries page markers; nothing is auto-promoted.
"""

from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from modules.deep_company_analysis.chapter8_gap_engine import build_dimension_coverage, enhanced_research_gaps
from modules.deep_company_analysis.chapter8_official_deep_retrieval import (
    build_official_deep_targets,
    documents_to_gap_candidates,
)
from modules.deep_company_analysis.chapter8_official_file_ingestion import (
    ALLOWED_FILE_EXTENSIONS,
    FILE_ATTEMPT_COLUMNS as V57_FILE_ATTEMPT_COLUMNS,
    OFFICIAL_ISSUER_OPTIONS,
    OfficialFileIngestionResult,
    _merge_candidates,
    _normalize_file_item,
    _open_count,
    _safe,
    _safe_filename,
    _ticker_match,
    extract_official_file_text,
)
from modules.deep_company_analysis.chapter8_official_source_adapters import is_official_url
from modules.deep_company_analysis.chapter8_pdf_ocr import (
    DEFAULT_OCR_DPI,
    DEFAULT_OCR_LANGUAGES,
    DEFAULT_OCR_MAX_PAGES,
    DEFAULT_OCR_WORKERS,
    PDFOCRResult,
    ocr_page_numbers_from_text,
    ocr_pdf_bytes,
)
from modules.deep_company_analysis.chapter8_research import evidence_quality_summary


FILE_ATTEMPT_COLUMNS = list(V57_FILE_ATTEMPT_COLUMNS)
for column in ("OCR Pages", "OCR Language", "OCR Runtime"):
    if column not in FILE_ATTEMPT_COLUMNS:
        insert_at = FILE_ATTEMPT_COLUMNS.index("SHA256") if "SHA256" in FILE_ATTEMPT_COLUMNS else len(FILE_ATTEMPT_COLUMNS)
        FILE_ATTEMPT_COLUMNS.insert(insert_at, column)


def _ocr_pages_label(result: PDFOCRResult | None) -> str:
    return "" if result is None else f"{result.successful_pages}/{result.attempted_pages}"


def _candidate_ocr_pages(value: Any) -> str:
    pages = ocr_page_numbers_from_text(str(value or ""))
    return ",".join(str(page) for page in pages)


class OfficialFileIngestionAgentV59:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def ingest(
        self,
        ticker: str,
        files: Iterable[Mapping[str, Any] | Any],
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        max_targets: int = 48,
        max_files: int = 12,
        enable_ocr: bool = True,
        ocr_languages: str = DEFAULT_OCR_LANGUAGES,
        ocr_dpi: int = DEFAULT_OCR_DPI,
        ocr_max_pages: int = DEFAULT_OCR_MAX_PAGES,
        ocr_workers: int = DEFAULT_OCR_WORKERS,
    ) -> OfficialFileIngestionResult:
        symbol = _safe(ticker).upper()
        before = build_dimension_coverage(existing_candidates)
        targets = build_official_deep_targets(existing_candidates, max_targets=max_targets)
        attempts: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        raw_paths: list[str] = []
        metadata_by_ref: dict[str, dict[str, Any]] = {}
        items = [_normalize_file_item(item) for item in list(files or [])[: max(1, min(int(max_files), 30))]]
        ocr_attempted_files = 0
        ocr_successful_files = 0

        for item in items:
            name = _safe_filename(item.get("name"))
            data = item.get("bytes", b"")
            if isinstance(data, bytearray):
                data = bytes(data)
            if not isinstance(data, bytes):
                data = b""
            suffix = Path(name).suffix.lower()
            issuer = _safe(item.get("issuer"))
            source_url = _safe(item.get("source_url"))
            confirmed = bool(item.get("official_confirmed"))
            digest = sha256(data).hexdigest() if data else ""
            verified_url = bool(source_url and is_official_url(source_url, symbol))
            provenance = "Verified official URL" if verified_url else "Analyst-confirmed uploaded official file" if confirmed else "Unverified"
            source_grade = "A — Official URL + uploaded file" if verified_url else "A? — Uploaded official file; provenance analyst verify"
            base_attempt: dict[str, Any] = {
                "File": name,
                "Document Type": suffix.lstrip(".").upper(),
                "Issuer": issuer,
                "Source URL": source_url,
                "Official Provenance": provenance,
                "Ticker Match": "No",
                "Status": "",
                "Text chars": 0,
                "OCR Pages": "",
                "OCR Language": "",
                "OCR Runtime": "",
                "SHA256": digest,
                "Stored Path": "",
                "Method": "",
                "Source Grade": source_grade,
            }
            if suffix not in ALLOWED_FILE_EXTENSIONS:
                attempts.append({**base_attempt, "Status": "Rejected: unsupported file type"})
                continue
            if not data:
                attempts.append({**base_attempt, "Status": "Rejected: empty file"})
                continue
            if source_url and not verified_url:
                attempts.append({**base_attempt, "Status": "Rejected: source URL is not on official allow-list"})
                continue
            if not verified_url and (not confirmed or issuer not in OFFICIAL_ISSUER_OPTIONS):
                attempts.append({**base_attempt, "Status": "Rejected: official provenance not confirmed"})
                continue

            text, method = extract_official_file_text(name, data)
            ocr_result: PDFOCRResult | None = None
            if not text and suffix == ".pdf" and enable_ocr:
                ocr_attempted_files += 1
                ocr_result = ocr_pdf_bytes(
                    data,
                    languages=ocr_languages,
                    dpi=ocr_dpi,
                    max_pages=ocr_max_pages,
                    workers=ocr_workers,
                )
                base_attempt["OCR Pages"] = _ocr_pages_label(ocr_result)
                base_attempt["OCR Language"] = ocr_result.languages
                base_attempt["OCR Runtime"] = ocr_result.runtime_note
                if ocr_result.text:
                    text = ocr_result.text
                    method = ocr_result.method
                    ocr_successful_files += 1
                else:
                    method = f"{method}; OCR fallback: {ocr_result.method}"

            base_attempt["Method"] = method
            base_attempt["Text chars"] = len(text)
            if not text:
                if suffix == ".pdf" and enable_ocr:
                    reason = _safe(ocr_result.runtime_note if ocr_result else "OCR produced no text")
                    attempts.append({**base_attempt, "Status": f"Rejected: no extractable text after OCR ({reason})"})
                else:
                    attempts.append({**base_attempt, "Status": "Rejected: no extractable text (OCR disabled)"})
                continue

            ticker_ok = _ticker_match(f"{name} {text[:80_000]}", symbol)
            base_attempt["Ticker Match"] = "Yes" if ticker_ok else "No"
            if not ticker_ok:
                attempts.append({**base_attempt, "Status": "Rejected: ticker mismatch"})
                continue

            ticker_dir = self.raw_dir / symbol
            ticker_dir.mkdir(parents=True, exist_ok=True)
            stored = ticker_dir / f"{digest[:16]}_{name}"
            if not stored.exists():
                stored.write_bytes(data)
            raw_paths.append(str(stored))
            source_ref = source_url if verified_url else str(stored)
            base_attempt["Stored Path"] = str(stored)
            attempts.append({**base_attempt, "Status": "Accepted"})
            documents.append({
                "url": source_ref,
                "title": _safe(item.get("title")) or name,
                "text": text,
                "method": method,
                "depth": 0,
            })
            metadata_by_ref[source_ref] = {
                "grade": source_grade,
                "origin": "Uploaded official file with allow-listed official URL" if verified_url else "Uploaded official file — analyst provenance verification required",
                "method": method,
                "file": name,
                "ocr": ocr_result,
            }

        new_candidates = documents_to_gap_candidates(documents, symbol, targets, manager_reference)
        if not new_candidates.empty:
            for idx, row in new_candidates.iterrows():
                ref = _safe(row.get("Source URL / File"))
                meta = metadata_by_ref.get(ref, {})
                ocr_result = meta.get("ocr")
                pages = _candidate_ocr_pages(row.get("Evidence Text / Reference")) if isinstance(ocr_result, PDFOCRResult) else ""
                new_candidates.at[idx, "Source Grade"] = meta.get("grade", "A? — Uploaded official file; provenance analyst verify")
                if isinstance(ocr_result, PDFOCRResult):
                    page_note = f" — OCR page(s)={pages}" if pages else " — OCR page marker unavailable"
                    new_candidates.at[idx, "Explicitness"] = "OCR text from official PDF — analyst verify"
                    new_candidates.at[idx, "Source Method"] = f"Phase 8N OCR official file ingestion{page_note} — {meta.get('method', '')}"
                    new_candidates.at[idx, "Data Origin"] = "OCR-derived text from official PDF — analyst verification required"
                else:
                    new_candidates.at[idx, "Explicitness"] = "Uploaded official document text — analyst verify"
                    new_candidates.at[idx, "Source Method"] = f"Phase 8L official file ingestion — {meta.get('method', 'local extraction')}"
                    new_candidates.at[idx, "Data Origin"] = meta.get("origin", "Uploaded official file — analyst verification required")
                new_candidates.at[idx, "Status"] = "Candidate — analyst verify"
                new_candidates.at[idx, "Select"] = False

        merged, added = _merge_candidates(existing_candidates, new_candidates)
        after = build_dimension_coverage(merged)
        gaps = enhanced_research_gaps(merged, manager_reference)
        quality = evidence_quality_summary(merged)
        documents_df = pd.DataFrame([
            {
                "File": meta.get("file", ""),
                "Source Reference": ref,
                "Source Grade": meta.get("grade", ""),
                "Text chars": len(_safe(doc.get("text"))),
                "Method": meta.get("method", ""),
                "OCR Pages": _ocr_pages_label(meta.get("ocr")) if isinstance(meta.get("ocr"), PDFOCRResult) else "",
                "OCR Language": meta.get("ocr").languages if isinstance(meta.get("ocr"), PDFOCRResult) else "",
            }
            for doc in documents
            for ref, meta in [(doc.get("url", ""), metadata_by_ref.get(str(doc.get("url", "")), {}))]
        ])
        attempts_df = pd.DataFrame(attempts, columns=FILE_ATTEMPT_COLUMNS)
        note = (
            f"Phase 8N official file ingestion: received {len(items)} file(s), accepted {len(documents)} ticker-matched document(s), "
            f"added {added} unique candidate(s); source-locked open dimensions {_open_count(before)} -> {_open_count(after)}. "
            f"OCR enabled={bool(enable_ocr)}, attempted files={ocr_attempted_files}, successful OCR files={ocr_successful_files}. "
            "Every extracted row remains Candidate — analyst verify; no evidence is auto-promoted."
        )
        return OfficialFileIngestionResult(
            targets=targets,
            attempts=attempts_df,
            documents=documents_df,
            new_candidates=new_candidates,
            merged_candidates=merged,
            before_coverage=before,
            after_coverage=after,
            remaining_gaps=gaps,
            quality=quality,
            raw_paths=raw_paths,
            note=note,
        )


__all__ = ["FILE_ATTEMPT_COLUMNS", "OfficialFileIngestionAgentV59"]
