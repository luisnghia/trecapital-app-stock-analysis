from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected source block not found: {path}\n{old[:160]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_page_support() -> None:
    path = ROOT / "modules" / "deep_company_analysis" / "chapter2_page_support.py"
    replace_once(
        path,
        "from modules.deep_company_analysis.chapter2_auto import (\n    Chapter2EvidenceAgent,\n    build_chapter2_assistant_draft,\n    load_cached_evidence,\n    merge_assistant_draft,\n)\n",
        "from modules.deep_company_analysis.chapter2_auto import (\n    build_chapter2_assistant_draft,\n    load_cached_evidence,\n    merge_assistant_draft,\n)\nfrom modules.deep_company_analysis.chapter2_evidence import SourceFirstChapter2EvidenceAgent\n",
    )
    replace_once(
        path,
        "evidence_result = Chapter2EvidenceAgent(m1.RAW_DIR).search(safe, company_name, max_results_per_query=5)",
        "evidence_result = SourceFirstChapter2EvidenceAgent(m1.RAW_DIR).search(safe, company_name, max_results_per_query=5)",
    )


def patch_e2e() -> None:
    path = ROOT / "tools" / "dgc_chapter2_e2e.py"
    replace_once(
        path,
        "from modules.deep_company_analysis.chapter2_auto import (\n    Chapter2EvidenceAgent,\n    build_chapter2_assistant_draft,\n    classify_evidence,\n)\n",
        "from modules.deep_company_analysis.chapter2_auto import (\n    build_chapter2_assistant_draft,\n    classify_evidence,\n)\nfrom modules.deep_company_analysis.chapter2_evidence import SourceFirstChapter2EvidenceAgent\n",
    )
    replace_once(
        path,
        "evidence_result = Chapter2EvidenceAgent(raw_dir).search(ticker, company_name, max_results_per_query=6)",
        "evidence_result = SourceFirstChapter2EvidenceAgent(raw_dir).search(ticker, company_name, max_results_per_query=6)",
    )
    # Keep a compact evidence sample in the audit so live E2E failures can be diagnosed without
    # opening private temporary cache files from the runner.
    replace_once(
        path,
        '"evidence_by_question": {key: int(len(value)) if isinstance(value, pd.DataFrame) else 0 for key, value in sections.items()},\n            "coverage": coverage,',
        '"evidence_by_question": {key: int(len(value)) if isinstance(value, pd.DataFrame) else 0 for key, value in sections.items()},\n            "evidence_sample": evidence[[c for c in ("Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu") if c in evidence.columns]].head(12).to_dict(orient="records") if not evidence.empty else [],\n            "coverage": coverage,',
    )


def patch_q6_exposure_type() -> None:
    chapter2 = ROOT / "modules" / "deep_company_analysis" / "chapter2.py"
    replace_once(
        chapter2,
        'FOREIGN_COLUMNS = [\n    "Country / Region",\n    "Entry year",',
        'FOREIGN_COLUMNS = [\n    "Country / Region",\n    "Exposure type",\n    "Entry year",',
    )
    replace_once(
        chapter2,
        'st.markdown("### Q6. Doanh nghiệp hoạt động ở thị trường nước ngoài nào và rủi ro là gì?")\n    no_foreign =',
        'st.markdown("### Q6. Doanh nghiệp hoạt động ở thị trường nước ngoài nào và rủi ro là gì?")\n    st.caption("Phân biệt rõ **thị trường xuất khẩu** với **hiện diện/hoạt động trực tiếp ở nước ngoài** (công ty con, nhà máy, văn phòng...). Không suy diễn export market thành foreign operation.")\n    no_foreign =',
    )

    auto = ROOT / "modules" / "deep_company_analysis" / "chapter2_auto.py"
    replace_once(
        auto,
        '        geographies = _find_geographies(text)\n        share = _explicit_revenue_share(text) if len(geographies) == 1 else ""\n        entry_year = _entry_year(text) if len(geographies) == 1 else ""\n        for geography in geographies:',
        '        geographies = _find_geographies(text)\n        share = _explicit_revenue_share(text) if len(geographies) == 1 else ""\n        entry_year = _entry_year(text) if len(geographies) == 1 else ""\n        normalized = _norm(text)\n        if any(token in normalized for token in ("xuat khau", "export")):\n            exposure_type = "Thị trường xuất khẩu"\n        elif any(token in normalized for token in ("cong ty con", "subsidiary", "nha may", "factory", "plant", "van phong", "office")):\n            exposure_type = "Hiện diện/hoạt động trực tiếp"\n        else:\n            exposure_type = "Thị trường nước ngoài — cần xác minh loại exposure"\n        for geography in geographies:',
    )
    replace_once(
        auto,
        '                "Country / Region": geography,\n                "Entry year": entry_year,',
        '                "Country / Region": geography,\n                "Exposure type": exposure_type,\n                "Entry year": entry_year,',
    )


def main() -> None:
    patch_page_support()
    patch_e2e()
    patch_q6_exposure_type()
    print("Chapter 2 source-first integration patch applied.")


if __name__ == "__main__":
    main()
