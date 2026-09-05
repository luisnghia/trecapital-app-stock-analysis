from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "modules" / "deep_company_analysis" / "chapter7_research.py"
UI = ROOT / "modules" / "deep_company_analysis" / "chapter7_research_ui.py"
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")
    old = '''    seeds = list(KNOWN_COMPANY_DOMAINS.get(safe, []))\n    if not seeds:\n'''
    new = '''    seeds = list(KNOWN_COMPANY_DOMAINS.get(safe, []))\n    # Vietnamese listed-company IR sites frequently expose a short friendly /quan-he-co-dong/\n    # URL while the actual current disclosures live under WordPress category paths. Add common\n    # category seeds generically; they are still same-domain official sources and remain candidates.\n    expanded_seeds = list(seeds)\n    for seed in list(seeds):\n        parsed = urlparse(seed)\n        if "quan-he-co-dong" not in parsed.path.casefold():\n            continue\n        root = f"{parsed.scheme}://{parsed.netloc}/"\n        expanded_seeds.extend([\n            root + "category/quan-he-co-dong/",\n            root + "category/quan-he-co-dong/bao-cao-thuong-nien/",\n            root + "category/quan-he-co-dong/bao-cao-tai-chinh/",\n            root + "category/quan-he-co-dong/thong-bao/",\n        ])\n    seeds = list(dict.fromkeys(expanded_seeds))\n    if not seeds:\n'''
    text = replace_once(text, old, new, "common IR category seeds")
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
    addition = '''\n\ndef official_documents_to_candidates(\n    documents: list[dict[str, Any]],\n    ticker: str,\n    managers: list[str] | None = None,\n) -> pd.DataFrame:\n    """Convert directly crawled company documents into factual Q33-Q38 evidence candidates.\n\n    This is evidence extraction only. It never confirms a manager identity or produces a management\n    classification/conclusion. Q37/Q38 require their own explicit focus terms; a manager name alone\n    is not enough to manufacture compensation/insider evidence.\n    """\n    manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]\n    rows: list[dict[str, Any]] = []\n    for document in documents:\n        text = _safe_text(document.get("text"))\n        if not text:\n            continue\n        url = _safe_text(document.get("url"))\n        title = _safe_text(document.get("title")) or url\n        method = _safe_text(document.get("method")) or "Official source extraction"\n        low = text.casefold()\n        for question in QUESTION_ORDER:\n            focus_hit = any(term.casefold() in low for term in FOCUS_TERMS[question])\n            if not focus_hit:\n                continue\n            windows = _relevant_windows(text, question, manager_names, max_windows=3)\n            for idx, snippet in enumerate(windows):\n                snippet_low = snippet.casefold()\n                if question in {"Q37", "Q38"} and not any(term.casefold() in snippet_low for term in FOCUS_TERMS[question]):\n                    continue\n                manager = _manager_from_text(snippet, manager_names)\n                cid = _candidate_id(question, manager, url, snippet, "official-discovery", idx)\n                rows.append({\n                    "Select": False,\n                    "Candidate ID": cid,\n                    "Question": question,\n                    "Manager": manager,\n                    "Subtopic": _subtopic(question, snippet),\n                    "Direction": direction_cue(question, snippet),\n                    "Source Grade": "A — Company/Official disclosure",\n                    "Explicitness": "Extracted official source text — analyst verify",\n                    "Source Title": title[:240],\n                    "Source URL / File": url,\n                    "Source Date": "",\n                    "As-of Date": _year_candidate(f"{title} {url} {snippet}"),\n                    "Evidence Text / Reference": snippet[:900],\n                    "Source Method": f"Phase 7C official management discovery — {method}",\n                    "Data Origin": "Direct company/official source text — analyst verification required",\n                    "Status": "Candidate — analyst verify",\n                })\n    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)\n    if frame.empty:\n        return frame\n    return frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)\n\n\nclass Chapter7ResearchAgent:\n'''
    text = replace_once(text, marker, addition, "official document evidence converter")

    old = '''        pieces: list[pd.DataFrame] = []\n        raw_paths: list[str] = []\n        notes: list[str] = []\n        manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]\n        for focus in QUESTION_ORDER:\n'''
    new = '''        pieces: list[pd.DataFrame] = []\n        raw_paths: list[str] = []\n        notes: list[str] = []\n        manager_names = [_safe_text(x) for x in (managers or []) if _safe_text(x)]\n        manager_candidates = pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)\n\n        # V37.1: discover candidate senior-manager identities from official company/IR sources before\n        # generic evidence search when analyst profile is empty. Targets remain unconfirmed.\n        if not manager_names:\n            try:\n                discovery = discover_management_candidates(ticker, company_name, max_documents=10, max_targets=5)\n                manager_candidates = discovery.managers.copy()\n                manager_names = list(discovery.target_names)\n                direct_candidates = official_documents_to_candidates(discovery.documents, ticker, manager_names)\n                if not direct_candidates.empty:\n                    pieces.append(direct_candidates)\n                notes.append("Management target discovery: " + discovery.note)\n            except Exception as exc:\n                notes.append(f"Management target discovery failed safely: {exc}")\n\n        for focus in QUESTION_ORDER:\n'''
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
    old_keys = '''    candidates_key = f"ch7c_candidates_{safe}"\n    note_key = f"ch7c_note_{safe}"\n    raw_key = f"ch7c_raw_{safe}"\n'''
    new_keys = '''    candidates_key = f"ch7c_candidates_{safe}"\n    discovered_key = f"ch7c_discovered_managers_{safe}"\n    note_key = f"ch7c_note_{safe}"\n    raw_key = f"ch7c_raw_{safe}"\n'''
    text = replace_once(text, old_keys, new_keys, "discovered managers session key")
    old_store = '''        st.session_state[candidates_key] = result.candidates.to_dict("records")\n        st.session_state[note_key] = result.note\n        st.session_state[raw_key] = result.raw_paths\n\n    candidates = _candidate_frame(st.session_state.get(candidates_key))\n'''
    new_store = '''        st.session_state[candidates_key] = result.candidates.to_dict("records")\n        discovered = result.manager_candidates if isinstance(result.manager_candidates, pd.DataFrame) else pd.DataFrame()\n        st.session_state[discovered_key] = discovered.to_dict("records")\n        st.session_state[note_key] = result.note\n        st.session_state[raw_key] = result.raw_paths\n\n    candidates = _candidate_frame(st.session_state.get(candidates_key))\n    discovered = pd.DataFrame(st.session_state.get(discovered_key) or [])\n    research_managers = list(managers)\n    if not research_managers and not discovered.empty and "Manager" in discovered.columns:\n        research_managers = list(dict.fromkeys(" ".join(str(x).split()) for x in discovered["Manager"].tolist() if str(x).strip()))[:5]\n\n    if not discovered.empty:\n        st.markdown("### Candidate management targets — auto-discovered")\n        render_static_table(discovered, height=min(360, 120 + 30 * len(discovered)), sort_key=f"ch7c_discovered_{safe}")\n        st.info("Các tên/chức vụ trên chỉ là research targets từ nguồn chính thức. App không tự ghi vào Management Profile và không tự xác nhận Q33/Q36.")\n\n'''
    text = replace_once(text, old_store, new_store, "store/display discovered managers")
    text = text.replace(
        "deep = deep_extract_candidates(candidates, selected_ids, managers=managers)",
        "deep = deep_extract_candidates(candidates, selected_ids, managers=research_managers)",
    )
    UI.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_research()
    patch_ui()
    print("Chapter 7 V37.1 management discovery hotfix applied")


if __name__ == "__main__":
    main()
