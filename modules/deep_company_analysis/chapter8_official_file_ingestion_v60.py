from __future__ import annotations

"""Chapter 8 Phase 8O / V60 official-file ingestion wrapper.

The V59 ingestion contract is preserved. V60 only replaces the OCR callable with a two-stage,
gap-directed high-resolution engine and exposes non-decision diagnostics for QA/UI inspection.
"""

from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from modules.deep_company_analysis.chapter8_gap_directed_ocr_v60 import (
    DEFAULT_COARSE_DPI,
    DEFAULT_COARSE_MAX_PAGES,
    DEFAULT_HIGHRES_DPI,
    DEFAULT_HIGHRES_MAX_PAGES,
    gap_directed_high_res_ocr_pdf_bytes,
)
from modules.deep_company_analysis.chapter8_official_deep_retrieval import build_official_deep_targets
from modules.deep_company_analysis.chapter8_official_file_ingestion_v59 import OfficialFileIngestionAgentV59


DIAGNOSTIC_COLUMNS = [
    "File Sequence",
    "Target Dimensions",
    "Coarse Attempted Pages",
    "Coarse Pages With Text",
    "High-res Selected Pages",
    "High-res Pages With Text",
    "Combined Pages With Text",
    "Combined Text chars",
    "Note",
]


class OfficialFileIngestionAgentV60:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.last_diagnostics = pd.DataFrame(columns=DIAGNOSTIC_COLUMNS)

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
        ocr_languages: str = "vie+eng",
        coarse_dpi: int = DEFAULT_COARSE_DPI,
        coarse_max_pages: int = DEFAULT_COARSE_MAX_PAGES,
        coarse_workers: int = 4,
        high_res_dpi: int = DEFAULT_HIGHRES_DPI,
        high_res_max_pages: int = DEFAULT_HIGHRES_MAX_PAGES,
        neighbor_radius: int = 1,
    ):
        targets = build_official_deep_targets(existing_candidates, max_targets=max_targets)
        diagnostics: list[dict[str, Any]] = []

        def engine(data: bytes, **kwargs):
            result = gap_directed_high_res_ocr_pdf_bytes(
                data,
                targets=targets,
                languages=str(kwargs.get("languages") or ocr_languages),
                dpi=coarse_dpi,
                max_pages=coarse_max_pages,
                workers=coarse_workers,
                high_res_dpi=high_res_dpi,
                high_res_max_pages=high_res_max_pages,
                neighbor_radius=neighbor_radius,
            )
            diagnostics.append({
                "File Sequence": len(diagnostics) + 1,
                "Target Dimensions": int(result.target_dimension_count),
                "Coarse Attempted Pages": int(result.coarse.attempted_pages),
                "Coarse Pages With Text": int(result.coarse.successful_pages),
                "High-res Selected Pages": ",".join(str(x) for x in result.selected_high_res_pages),
                "High-res Pages With Text": int(result.high_res.successful_pages if result.high_res else 0),
                "Combined Pages With Text": int(result.combined.successful_pages),
                "Combined Text chars": int(len(result.combined.text)),
                "Note": result.note,
            })
            return result.combined

        result = OfficialFileIngestionAgentV59(self.raw_dir / "phase8o_v60").ingest(
            ticker,
            files,
            existing_candidates=existing_candidates,
            manager_reference=manager_reference,
            max_targets=max_targets,
            max_files=max_files,
            enable_ocr=enable_ocr,
            ocr_languages=ocr_languages,
            ocr_dpi=coarse_dpi,
            ocr_max_pages=coarse_max_pages,
            ocr_workers=coarse_workers,
            ocr_engine=engine,
        )
        self.last_diagnostics = pd.DataFrame(diagnostics, columns=DIAGNOSTIC_COLUMNS)

        for frame in (result.new_candidates, result.merged_candidates):
            if isinstance(frame, pd.DataFrame) and not frame.empty and "Source Method" in frame.columns:
                frame["Source Method"] = frame["Source Method"].astype(str).str.replace(
                    "Phase 8N OCR official file ingestion",
                    "Phase 8O gap-directed high-resolution OCR official file ingestion",
                    regex=False,
                )
                if "Data Origin" in frame.columns:
                    mask = frame["Source Method"].str.contains("Phase 8O", na=False, regex=False)
                    frame.loc[mask, "Data Origin"] = "Gap-directed OCR-derived text from official PDF — analyst verification required"
        result.note = (
            f"Phase 8O gap-directed high-resolution OCR: {len(targets)} open source-locked target(s); "
            f"{len(self.last_diagnostics)} scanned PDF OCR pass(es). {result.note}"
        )
        return result


__all__ = ["DIAGNOSTIC_COLUMNS", "OfficialFileIngestionAgentV60"]
