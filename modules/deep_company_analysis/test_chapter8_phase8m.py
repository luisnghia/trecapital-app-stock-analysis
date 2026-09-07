from modules.deep_company_analysis.chapter8_official_source_adapters import is_official_url
from modules.deep_company_analysis.chapter8_real_official_sources import (
    DGC_REAL_OFFICIAL_SOURCES,
    load_v54_dgc_coverage,
    v54_historical_open_keys,
)


def test_phase8m_real_manifest_is_official_and_dgc_specific():
    assert len(DGC_REAL_OFFICIAL_SOURCES) >= 4
    assert {source.ticker for source in DGC_REAL_OFFICIAL_SOURCES} == {"DGC"}
    assert {source.document_type for source in DGC_REAL_OFFICIAL_SOURCES} >= {
        "Annual Report",
        "Corporate Governance Report",
        "AGM Minutes/Resolution",
    }
    for source in DGC_REAL_OFFICIAL_SOURCES:
        assert source.landing_page.startswith("https://ducgiangchem.vn/")
        assert source.document_url.startswith("https://ducgiangchem.vn/")
        assert source.document_url.lower().endswith(".pdf")
        assert is_official_url(source.document_url, "DGC")
        assert "DGC" in source.document_url.upper()


def test_phase8m_v54_historical_baseline_locks_exact_40_open_source_dimensions():
    frame = load_v54_dgc_coverage()
    assert len(frame) == 49
    assert int(frame["Source Locked"].eq("Yes").sum()) == 48
    assert len(v54_historical_open_keys()) == 40
    covered = frame[frame["Coverage Status"].eq("Candidate coverage — analyst verify")]
    assert len(covered[covered["Source Locked"].eq("Yes")]) == 8


def test_phase8m_manifest_never_encodes_investment_judgment():
    forbidden = {"BUY", "SELL", "HOLD", "MOS", "management score"}
    blob = " ".join(
        f"{source.title} {source.document_type} {source.landing_page} {source.document_url}"
        for source in DGC_REAL_OFFICIAL_SOURCES
    )
    for token in forbidden:
        assert token.lower() not in blob.lower()
