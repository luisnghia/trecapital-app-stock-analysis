from __future__ import annotations

"""V102 composition wrapper: V101 checklist report + canonical 10Y/TTM evidence.

The V101 generator remains the single checklist presentation implementation. This wrapper
opens its DOCX bytes and appends V102 financial evidence by reference; no Q01-Q59 wording,
answer state, financial state, valuation, or Research Gate state is duplicated or persisted.
"""

from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from docx import Document

from modules.deep_company_analysis.docx_layout_v105 import harden_document_layout
from modules.deep_company_analysis.investment_checklist_report import build_investment_checklist_report_docx
from modules.deep_company_analysis.financial_report_v102 import render_financial_evidence

REPORT_VERSION = "V102"


def build_investment_checklist_report_v102_docx(*, canonical_financial_df: pd.DataFrame, years: int = 10, **v101_kwargs: Any) -> bytes:
    base = build_investment_checklist_report_docx(**v101_kwargs)
    document = Document(BytesIO(base))
    render_financial_evidence(document, canonical_financial_df, years=years)
    props = document.core_properties
    props.comments = (props.comments or "") + " V102 appends read-only 10Y + TTM canonical financial evidence and quantitative charts."
    harden_document_layout(document)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def write_investment_checklist_report_v102_docx(path: str | Path, **kwargs: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_investment_checklist_report_v102_docx(**kwargs))
    return target


__all__ = ["REPORT_VERSION", "build_investment_checklist_report_v102_docx", "write_investment_checklist_report_v102_docx"]
