from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "modules" / "deep_company_analysis" / "chapter7_research.py"
UI = ROOT / "modules" / "deep_company_analysis" / "chapter7_research_ui.py"
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from urllib.parse import urljoin, urlparse, quote_plus\n",
        "from urllib.parse import urljoin, urlparse, quote_plus, urldefrag\n",
        "URL fragment normalizer import",
    )

    old_pattern = '''PERSON_NAME_PATTERN = re.compile(
    r"(?<![A-Za-zÀ-ỹĐđ])(?:Ông|Bà|Mr\\.?|Ms\\.?)\\s+"
    r"([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\\.-]+"
    r"(?:\\s+[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\\.-]+){1,5})",
    flags=re.IGNORECASE,
)'''
    new_pattern = '''PERSON_NAME_PATTERN = re.compile(
    r"(?<![A-Za-zÀ-ỹĐđ])(?i:Ông|Bà|Mr\\.?|Ms\\.?)\\s+"
    r"([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\\.-]+"
    r"(?:\\s+[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\\.-]+){1,5})"
)'''
    text = replace_once(text, old_pattern, new_pattern, "capitalization-sensitive person parser")

    old_noise = '    "ông", "bà", "mr", "ms", "ủy", "uỷ", "ban", "kiểm", "soát",\n}'
    new_noise = '    "ông", "bà", "mr", "ms", "ủy", "uỷ", "ban", "kiểm", "soát", "giữ", "chức", "vụ", "được", "đảm", "sinh",\n}'
    text = replace_once(text, old_noise, new_noise, "action-word name filter")

    old_report = '''REPORT_PRIORITY_TERMS = (
    "báo cáo thường niên", "bao cao thuong nien", "annual report", "bctn",
    "báo cáo quản trị", "bao cao quan tri", "corporate governance",
)'''
    new_report = '''REPORT_PRIORITY_TERMS = (
    "báo cáo thường niên", "bao cao thuong nien", "annual report", "bctn",
    "báo cáo quản trị", "bao cao quan tri", "tình hình quản trị", "tinh hinh quan tri", "corporate governance",
    "báo cáo tài chính", "bao cao tai chinh", "financial statement", "financial report", "bctc",
    "quý 4", "quy 4", "quarter 4", "kiểm toán", "kiem toan", "audited",
)'''
    text = replace_once(text, old_report, new_report, "current governance/financial-report priority")

    old_search = '    terms = ("nhân sự", "tổng giám đốc", "chủ tịch", "báo cáo thường niên", "báo cáo quản trị")\n'
    new_search = '    terms = ("nhân sự", "tổng giám đốc", "chủ tịch HĐQT", "hội đồng quản trị", "ban tổng giám đốc", "báo cáo thường niên", "báo cáo quản trị", "tình hình quản trị", "báo cáo tài chính quý 4", "thông tin về doanh nghiệp")\n'
    text = replace_once(text, old_search, new_search, "official-site search coverage")

    old_bases = '''        bases = [
            root + "category/quan-he-co-dong/",
            root + "category/quan-he-co-dong/bao-cao-thuong-nien/",
            root + "category/quan-he-co-dong/bao-cao-tai-chinh/",
            root + "category/quan-he-co-dong/thong-bao/",
        ]
        expanded_seeds.extend(bases)
        # Personnel changes often move off page 1 quickly. Crawl only a shallow recent history.
        for page in range(2, 7):
            expanded_seeds.append(root + f"category/quan-he-co-dong/thong-bao/page/{page}/")
        for page in range(2, 4):
            expanded_seeds.append(root + f"category/quan-he-co-dong/bao-cao-thuong-nien/page/{page}/")
'''
    new_bases = '''        bases = [
            root + "category/quan-he-co-dong/",
            root + "category/quan-he-co-dong/bao-cao-thuong-nien/",
            root + "category/quan-he-co-dong/bao-cao-quan-tri/",
            root + "category/quan-he-co-dong/bao-cao-tai-chinh/",
            root + "category/quan-he-co-dong/thong-bao/",
        ]
        expanded_seeds.extend(bases)
        # Personnel changes often move off page 1 quickly. Crawl only a shallow recent history.
        for page in range(2, 7):
            expanded_seeds.append(root + f"category/quan-he-co-dong/thong-bao/page/{page}/")
        for page in range(2, 4):
            expanded_seeds.append(root + f"category/quan-he-co-dong/bao-cao-thuong-nien/page/{page}/")
            expanded_seeds.append(root + f"category/quan-he-co-dong/bao-cao-quan-tri/page/{page}/")
        # Some IR themes paginate the top-level shareholder archive with a query parameter rather than /page/N/.
        for page in range(1, 4):
            expanded_seeds.append(root + f"category/quan-he-co-dong/?page_number_0={page}")
'''
    text = replace_once(text, old_bases, new_bases, "governance and archive pagination seeds")

    old_href = '        href = urljoin(final_url, anchor.get("href", ""))\n'
    new_href = '        href = urldefrag(urljoin(final_url, anchor.get("href", "")))[0]\n'
    text = replace_once(text, old_href, new_href, "defragment crawled links")

    old_fetches = '    max_fetches = max(60, max_documents * 10)\n'
    new_fetches = '    max_fetches = max(80, max_documents * 12)\n'
    text = replace_once(text, old_fetches, new_fetches, "crawl ceiling")

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_research() -> None:
    text = RESEARCH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS, WebEvidenceAgent\n",
        "from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS, WebEvidenceAgent\n"
        "from modules.deep_company_analysis.chapter7_management_discovery import (\n"
        "    MANAGER_CANDIDATE_COLUMNS,\n"
        "    discover_management_candidates,\n"
        ")\n",
        "management discovery import",
    )
    text = replace_once(
        text,
        "@dataclass\nclass Chapter7ResearchResult:\n    candidates: pd.DataFrame\n    raw_paths: list[str]\n    note: str\n",
        "@dataclass\nclass Chapter7ResearchResult:\n    candidates: pd.DataFrame\n    raw_paths: list[str]\n    note: str\n    manager_candidates: pd.DataFrame | None = None\n",
        "research result manager candidates",
    )
    text = replace_once(
        text,
        '        manager = self.managers[0] if self.managers else ""\n        vi, en = QUERY_TERMS[self.focus]\n        manager_vi = f\' "{manager}"\' if manager else ""\n        return [\n            f\'"{ticker}" "{name}"{manager_vi} {vi}\',\n            f\'"{ticker}" "{name}"{manager_vi} {en}\',\n        ]\n',
        '        manager_clause = " ".join(f\'"{manager}"\' for manager in self.managers[:3])\n        vi, en = QUERY_TERMS[self.focus]\n        manager_part = f" {manager_clause}" if manager_clause else ""\n        return [\n            f\'"{ticker}" "{name}"{manager_part} {vi}\',\n            f\'"{ticker}" "{name}"{manager_part} {en}\',\n        ]\n',
        "multi-manager query scope",
    )

    marker = "\n\nclass Chapter7ResearchAgent:\n"
    addition = '''

def official_documents_to_candidates(
    documents: list[dict[str, Any]],
    ticker: str,
    managers: list[str] | None = None,
) -> pd.DataFrame:
    """Convert directly crawled company documents into factual Q33-Q38 evidence candidates.

    This is evidence extraction only. It never confirms a manager identity or produces a management
    classification/conclusion. Q37/Q38 require their own explicit focus terms; a manager name alone
    is not enough to manufacture compensation/insider evidence.
    """
    manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]
    rows: list[dict[str, Any]] = []
    for document in documents:
        text = _safe_text(document.get("text"))
        if not text:
            continue
        url = _safe_text(document.get("url"))
        title = _safe_text(document.get("title")) or url
        method = _safe_text(document.get("method")) or "Official source extraction"
        low = text.casefold()
        for question in QUESTION_ORDER:
            focus_hit = any(term.casefold() in low for term in FOCUS_TERMS[question])
            if not focus_hit:
                continue
            windows = _relevant_windows(text, question, manager_names, max_windows=3)
            for idx, snippet in enumerate(windows):
                snippet_low = snippet.casefold()
                if question in {"Q37", "Q38"} and not any(term.casefold() in snippet_low for term in FOCUS_TERMS[question]):
                    continue
                manager = _manager_from_text(snippet, manager_names)
                cid = _candidate_id(question, manager, url, snippet, "official-discovery", idx)
                rows.append({
                    "Select": False,
                    "Candidate ID": cid,
                    "Question": question,
                    "Manager": manager,
                    "Subtopic": _subtopic(question, snippet),
                    "Direction": direction_cue(question, snippet),
                    "Source Grade": "A — Company/Official disclosure",
                    "Explicitness": "Extracted official source text — analyst verify",
                    "Source Title": title[:240],
                    "Source URL / File": url,
                    "Source Date": "",
                    "As-of Date": _year_candidate(f"{title} {url} {snippet}"),
                    "Evidence Text / Reference": snippet[:900],
                    "Source Method": f"Phase 7C official management discovery — {method}",
                    "Data Origin": "Direct company/official source text — analyst verification required",
                    "Status": "Candidate — analyst verify",
                })
    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)


class Chapter7ResearchAgent:
'''
    text = replace_once(text, marker, addition, "official document evidence converter")

    old = '''        pieces: list[pd.DataFrame] = []
        raw_paths: list[str] = []
        notes: list[str] = []
        manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]
        for focus in QUESTION_ORDER:
'''
    new = '''        pieces: list[pd.DataFrame] = []
        raw_paths: list[str] = []
        notes: list[str] = []
        manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]
        manager_candidates = pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)

        # V37.1: discover candidate senior-manager identities from official company/IR sources before
        # generic evidence search when analyst profile is empty. Targets remain unconfirmed.
        if not manager_names:
            try:
                discovery = discover_management_candidates(ticker, company_name, max_documents=24, max_targets=5)
                manager_candidates = discovery.managers.copy()
                manager_names = list(discovery.target_names)
                direct_candidates = official_documents_to_candidates(discovery.documents, ticker, manager_names)
                if not direct_candidates.empty:
                    pieces.append(direct_candidates)
                notes.append("Management target discovery: " + discovery.note)
            except Exception as exc:
                notes.append(f"Management target discovery failed safely: {exc}")

        for focus in QUESTION_ORDER:
'''
    text = replace_once(text, old, new, "search manager discovery")
    text = replace_once(
        text,
        '        return Chapter7ResearchResult(frame, raw_paths, " | ".join(notes))\n',
        '        return Chapter7ResearchResult(frame, raw_paths, " | ".join(notes), manager_candidates)\n',
        "search result manager candidates",
    )
    RESEARCH.write_text(text, encoding="utf-8")


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '        st.warning("Management Profile đang trống. Research vẫn chạy theo ticker/doanh nghiệp, nhưng Q36 top-5 chronology sẽ bị gắn identity gap.")\n',
        '        st.warning("Management Profile đang trống. Hệ thống sẽ thử auto-discover candidate manager targets từ nguồn doanh nghiệp/IR chính thức trước khi research; các identity này vẫn cần analyst xác nhận.")\n',
        "empty profile discovery warning",
    )
    old_keys = '''    candidates_key = f"ch7c_candidates_{safe}"
    note_key = f"ch7c_note_{safe}"
    raw_key = f"ch7c_raw_{safe}"
'''
    new_keys = '''    candidates_key = f"ch7c_candidates_{safe}"
    discovered_key = f"ch7c_discovered_managers_{safe}"
    note_key = f"ch7c_note_{safe}"
    raw_key = f"ch7c_raw_{safe}"
'''
    text = replace_once(text, old_keys, new_keys, "discovered managers session key")
    old_store = '''        st.session_state[candidates_key] = result.candidates.to_dict("records")
        st.session_state[note_key] = result.note
        st.session_state[raw_key] = result.raw_paths

    candidates = _candidate_frame(st.session_state.get(candidates_key))
'''
    new_store = '''        st.session_state[candidates_key] = result.candidates.to_dict("records")
        discovered = result.manager_candidates if isinstance(result.manager_candidates, pd.DataFrame) else pd.DataFrame()
        st.session_state[discovered_key] = discovered.to_dict("records")
        st.session_state[note_key] = result.note
        st.session_state[raw_key] = result.raw_paths

    candidates = _candidate_frame(st.session_state.get(candidates_key))
    discovered = pd.DataFrame(st.session_state.get(discovered_key) or [])
    research_managers = list(managers)
    if not research_managers and not discovered.empty and "Manager" in discovered.columns:
        research_managers = list(dict.fromkeys(" ".join(str(x).split()) for x in discovered["Manager"].tolist() if str(x).strip()))[:5]

    if not discovered.empty:
        st.markdown("### Candidate management targets — auto-discovered")
        render_static_table(discovered, height=min(360, 120 + 30 * len(discovered)), sort_key=f"ch7c_discovered_{safe}")
        st.info("Các tên/chức vụ trên chỉ là research targets từ nguồn chính thức. App không tự ghi vào Management Profile và không tự xác nhận Q33/Q36.")

'''
    text = replace_once(text, old_store, new_store, "store/display discovered managers")
    text = text.replace(
        "deep = deep_extract_candidates(candidates, selected_ids, managers=managers)",
        "deep = deep_extract_candidates(candidates, selected_ids, managers=research_managers)",
    )
    UI.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_action_words_are_not_captured_as_manager_name_v37_1_round3():"
    if sentinel in text:
        return
    text += '''


def test_action_words_are_not_captured_as_manager_name_v37_1_round3():
    docs = [{
        "title": "Official personnel disclosure 2025",
        "url": "https://example.com/official-personnel",
        "text": "Nghị quyết bổ nhiệm ông Lưu Bách Đạt giữ chức vụ Tổng Giám đốc. Nghị quyết bổ nhiệm ông Đào Hữu Duy Anh giữ chức vụ Phó Chủ tịch HĐQT.",
        "method": "HTML text extraction",
    }]
    frame = extract_management_candidates_from_documents(docs)
    names = set(frame["Manager"].astype(str))
    assert "Lưu Bách Đạt" in names
    assert "Đào Hữu Duy Anh" in names
    assert not any("giữ" in name.casefold() or "chức" in name.casefold() for name in names)


def test_official_roster_extracts_chairman_ceo_and_third_manager_v37_1_round3():
    docs = [{
        "title": "Official financial statement 2025",
        "url": "https://example.com/official-financial-statement.pdf",
        "text": "Ông Đào Hữu Huyền — Chủ tịch HĐQT\\nÔng Lưu Bách Đạt — Tổng Giám đốc\\nÔng Phạm Văn Hùng — Phó Tổng Giám đốc",
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    assert {"Đào Hữu Huyền", "Lưu Bách Đạt", "Phạm Văn Hùng"}.issubset(set(frame["Manager"].astype(str)))
    roles = set(frame["Role Normalized"].astype(str))
    assert "Chairman" in roles
    assert "CEO" in roles
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_research()
    patch_ui()
    patch_tests()
    print("Chapter 7 V37.1 management discovery hotfix Round 4 applied")


if __name__ == "__main__":
    main()
