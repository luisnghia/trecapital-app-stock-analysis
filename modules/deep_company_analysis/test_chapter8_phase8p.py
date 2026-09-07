from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from reportlab.pdfgen import canvas

from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_official_deep_retrieval import build_official_deep_targets
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS
from modules.deep_company_analysis.chapter8_research_v61 import Chapter8ResearchAgent
from modules.deep_company_analysis.chapter8_section_directed_retrieval_v61 import (
    SectionDirectedRetrievalAgentV61,
    build_section_plan,
    discover_section_directed_sources,
    download_section_documents,
    filter_targets_to_keys,
)


def _all_targets() -> pd.DataFrame:
    return build_official_deep_targets(pd.DataFrame(columns=CANDIDATE_COLUMNS), max_targets=64)


def _pdf(text: str = "", pages: int = 1) -> bytes:
    stream = BytesIO()
    c = canvas.Canvas(stream)
    for idx in range(pages):
        if text:
            c.drawString(72, 750, f"DGC {text} page {idx + 1}")
        c.showPage()
    c.save()
    return stream.getvalue()


class _Resp:
    def __init__(self, url: str, *, text: str = "", data: bytes = b"", content_type: str = "text/html"):
        self.url = url
        self.text = text
        self._data = data
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        yield self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Client:
    def __init__(self, mapping):
        self.mapping = mapping

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, **kwargs):
        if url not in self.mapping:
            raise RuntimeError(f"missing fake URL {url}")
        return self.mapping[url]

    def stream(self, method, url, **kwargs):
        return self.get(url, **kwargs)


def test_v61_section_plan_is_driven_by_open_question_targets() -> None:
    targets = _all_targets()
    chosen = filter_targets_to_keys(targets, {("Q43", "training"), ("Q46", "shearn_action_5")})
    plan = build_section_plan(chosen)
    assert set(plan["Section"]) == {"People / culture / hiring", "Capital allocation / buyback"}
    assert int(plan["Open Target Count"].sum()) == 2


def test_v61_target_filter_does_not_add_unrequested_dimensions() -> None:
    targets = _all_targets()
    keys = {("Q39", "customers"), ("Q45", "cost_reduction")}
    filtered = filter_targets_to_keys(targets, keys)
    actual = set(zip(filtered["Question"].astype(str), filtered["Dimension Key"].astype(str)))
    assert actual.issubset(keys)
    assert actual


def test_v61_discovers_official_pdf_via_section_archive_and_landing_page() -> None:
    seed = "https://ducgiangchem.vn/category/quan-he-co-dong/bao-cao-thuong-nien/"
    landing = "https://ducgiangchem.vn/bao-cao-thuong-nien-nam-2023/"
    pdf = "https://ducgiangchem.vn/wp-content/uploads/2024/03/20240319-DGC-Bao-cao-thuong-nien-nam-2023.pdf"
    archive_html = f'<a href="{landing}">BÁO CÁO THƯỜNG NIÊN NĂM 2023</a>'
    landing_html = f'<html><title>DGC BÁO CÁO THƯỜNG NIÊN 2023</title><body>nhân sự đào tạo chiến lược <a href="{pdf}">20240319 DGC báo cáo thường niên 2023</a><a href="https://evil.example/x.pdf">bad</a></body></html>'
    mapping = {
        seed: _Resp(seed, text=archive_html),
        landing: _Resp(landing, text=landing_html),
    }
    targets = filter_targets_to_keys(_all_targets(), {("Q43", "training")})
    with patch("modules.deep_company_analysis.chapter8_section_directed_retrieval_v61.httpx.Client", return_value=_Client(mapping)):
        out = discover_section_directed_sources(
            "DGC", targets, seed_urls=[seed], max_index_pages=1, max_landing_pages=4, max_documents=4, year_floor=2023
        )
    assert not out.empty
    assert pdf in set(out["Document URL"])
    assert out["Official URL"].eq("Yes").all()
    assert not out["Document URL"].str.contains("evil.example", regex=False).any()


def test_v61_download_prefers_text_layer_and_bounds_scanned_ocr() -> None:
    text_url = "https://ducgiangchem.vn/wp-content/uploads/2025/03/text.pdf"
    scan1 = "https://ducgiangchem.vn/wp-content/uploads/2025/03/scan1.pdf"
    scan2 = "https://ducgiangchem.vn/wp-content/uploads/2025/03/scan2.pdf"
    discovery = pd.DataFrame([
        {"Section": "People / culture / hiring", "Title": "text", "Year": 2024, "Landing Page": "https://ducgiangchem.vn/a/", "Document URL": text_url, "Score": 10, "Official URL": "Yes", "Discovery Method": "test"},
        {"Section": "Cost discipline", "Title": "scan1", "Year": 2024, "Landing Page": "https://ducgiangchem.vn/b/", "Document URL": scan1, "Score": 9, "Official URL": "Yes", "Discovery Method": "test"},
        {"Section": "Capital allocation / buyback", "Title": "scan2", "Year": 2024, "Landing Page": "https://ducgiangchem.vn/c/", "Document URL": scan2, "Score": 8, "Official URL": "Yes", "Discovery Method": "test"},
    ])
    mapping = {
        text_url: _Resp(text_url, data=_pdf("employee training strategy"), content_type="application/pdf"),
        scan1: _Resp(scan1, data=_pdf(""), content_type="application/pdf"),
        scan2: _Resp(scan2, data=_pdf(""), content_type="application/pdf"),
    }
    with patch("modules.deep_company_analysis.chapter8_section_directed_retrieval_v61.httpx.Client", return_value=_Client(mapping)):
        files, attempts = download_section_documents("DGC", discovery, max_files=3, max_scanned_ocr_docs=1)
    assert len(files) == 2
    selected = {item["source_url"] for item in files}
    assert text_url in selected
    assert len(selected & {scan1, scan2}) == 1
    assert attempts["Status"].astype(str).str.contains("deferred", case=False).sum() == 1


def test_v61_research_wrapper_exposes_section_agent(tmp_path: Path) -> None:
    agent = Chapter8ResearchAgent(tmp_path)
    with patch("modules.deep_company_analysis.chapter8_research_v61.SectionDirectedRetrievalAgentV61.run", return_value="sentinel") as mocked:
        out = agent.retrieve_section_directed_official_documents("DGC", existing_candidates=pd.DataFrame())
    assert out == "sentinel"
    assert mocked.call_args.kwargs["max_documents"] == 12
    assert mocked.call_args.kwargs["max_scanned_ocr_docs"] == 2


def test_v61_preserves_source_locks_and_no_auto_decision_contract() -> None:
    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q47_share_count_is_proof"] is False
