from __future__ import annotations

"""Quality hotfix for Chapter 4 Phase 4C after first integration acceptance."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEER = ROOT / "modules" / "deep_company_analysis" / "chapter4_peer_auto.py"
EVIDENCE = ROOT / "modules" / "deep_company_analysis" / "chapter4_evidence.py"
SUPPORT = ROOT / "modules" / "deep_company_analysis" / "chapter4_page_support.py"
TEST_EVIDENCE = ROOT / "modules" / "deep_company_analysis" / "test_chapter4_evidence.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Hotfix marker not found: {label}")
    return text.replace(old, new, 1)


def patch_peer() -> None:
    text = PEER.read_text(encoding="utf-8")
    text = text.replace("from dataclasses import dataclass\n", "from dataclasses import dataclass\nfrom concurrent.futures import ThreadPoolExecutor, as_completed\n", 1) if "ThreadPoolExecutor" not in text else text
    text = text.replace("DEFAULT_MAX_PEERS = 25", "DEFAULT_MAX_PEERS = 60")
    marker = '''def peer_refresh_plan(discovery: IndustryPeerDiscovery, target_first: bool = True) -> list[str]:\n'''
    helper = '''def refresh_peer_canonical_universe(\n    tickers: list[str],\n    max_workers: int = 3,\n) -> list[tuple[str, bool, tuple[Path, Path, Path] | None, str]]:\n    """Refresh a real peer universe concurrently through the canonical pipeline.\n\n    Concurrency is deliberately small to reduce total waiting time without hammering public sources.\n    Results keep input order.  A failed peer stays failed/Unknown; there is no substitute data.\n    """\n    ordered: list[str] = []\n    for item in tickers:\n        safe = _safe_ticker(item)\n        if safe and safe not in ordered:\n            ordered.append(safe)\n    if not ordered:\n        return []\n    workers = max(1, min(int(max_workers or 1), 4, len(ordered)))\n    indexed: dict[str, tuple[bool, tuple[Path, Path, Path] | None, str]] = {}\n    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ch4-peer") as pool:\n        futures = {pool.submit(refresh_peer_canonical_bundle, ticker): ticker for ticker in ordered}\n        for future in as_completed(futures):\n            ticker = futures[future]\n            try:\n                indexed[ticker] = future.result()\n            except Exception as exc:\n                indexed[ticker] = (False, None, f"{ticker}: cập nhật canonical data lỗi: {exc}")\n    return [(ticker, *indexed.get(ticker, (False, None, f"{ticker}: không có kết quả."))) for ticker in ordered]\n\n\n'''
    text = replace_once(text, marker, helper + marker, "parallel peer refresh")
    PEER.write_text(text, encoding="utf-8")


def patch_evidence() -> None:
    text = EVIDENCE.read_text(encoding="utf-8")
    text = text.replace(
        'f\'"{ticker}" "{name}" lợi thế cạnh tranh thương hiệu bằng sáng chế giấy phép switching cost quy mô nguồn nguyên liệu\'',
        'f\'"{ticker}" "{name}" lợi thế cạnh tranh thương hiệu bằng sáng chế giấy phép switching cost quy mô nguồn nguyên liệu suy yếu rủi ro thay thế erosion\'',
    )
    text = text.replace(
        'f\'"{ticker}" "{name}" tăng giá giá bán sản lượng khách hàng retention churn pricing power\'',
        'f\'"{ticker}" "{name}" tăng giá giá bán sản lượng khách hàng retention churn mất khách pricing power pass-through\'',
    )
    old = '''    for _, row in raw_df.iterrows():\n        data = row.to_dict()\n        text = _norm(f"{data.get('Tiêu đề','')} {data.get('Trích yếu','')} {data.get('Truy vấn','')}")\n'''
    new = '''    for _, row in raw_df.iterrows():\n        data = row.to_dict()\n        # Direct-source placeholder links from WebEvidenceAgent are useful navigation, but they are\n        # not evidence.  Only actual search findings may enter the Chapter 4 Evidence Matrix.\n        if str(data.get("Trạng thái") or "").strip() != "Tìm thấy":\n            continue\n        text = _norm(f"{data.get('Tiêu đề','')} {data.get('Trích yếu','')} {data.get('Truy vấn','')}")\n'''
    text = replace_once(text, old, new, "exclude source-link placeholders")
    EVIDENCE.write_text(text, encoding="utf-8")


def patch_support() -> None:
    text = SUPPORT.read_text(encoding="utf-8")
    old_import = '''    peer_refresh_plan,\n    refresh_peer_canonical_bundle,\n)\n'''
    new_import = '''    peer_refresh_plan,\n    refresh_peer_canonical_bundle,\n    refresh_peer_canonical_universe,\n)\n'''
    text = replace_once(text, old_import, new_import, "parallel helper import")
    old_loop = '''            progress = st.progress(0.0, text="Đang cập nhật canonical BCTC cho peer cùng ngành...")\n            notes: list[str] = []\n            ok_count = 0\n            for idx, peer in enumerate(peers):\n                ok, _paths, note = refresh_peer_canonical_bundle(peer)\n                notes.append(note)\n                ok_count += int(ok)\n                progress.progress((idx + 1) / max(len(peers), 1), text=f"{peer}: {'OK' if ok else 'thiếu dữ liệu'}")\n            _snapshot_cached.clear()\n'''
    new_loop = '''            progress = st.progress(0.02, text=f"Đang cập nhật canonical BCTC cho {len(peers)} mã cùng ngành (tối đa 3 luồng)...")\n            refresh_results = refresh_peer_canonical_universe(peers, max_workers=3)\n            notes = [note for _peer, _ok, _paths, note in refresh_results]\n            ok_count = sum(1 for _peer, ok, _paths, _note in refresh_results if ok)\n            progress.progress(0.92, text="Đang dựng ROIC/CCC/margins và đồng bộ bảng Q17/Q19...")\n            _snapshot_cached.clear()\n'''
    text = replace_once(text, old_loop, new_loop, "parallel peer universe refresh")
    SUPPORT.write_text(text, encoding="utf-8")


def patch_test() -> None:
    text = TEST_EVIDENCE.read_text(encoding="utf-8")
    old = '''        "Truy vấn": "query",\n    }])\n'''
    new = '''        "Truy vấn": "query",\n        "Trạng thái": "Tìm thấy",\n    }])\n'''
    text = replace_once(text, old, new, "test actual finding status")
    extra = '''\n\ndef test_direct_source_navigation_link_is_not_promoted_to_evidence():\n    df = _raw("Q15_Q16", "DGC - trang IR", "Nguồn ưu tiên để kiểm tra lợi thế cạnh tranh.")\n    df.loc[:, "Trạng thái"] = "Link nguồn ưu tiên"\n    assert _candidate_rows(df).empty\n'''
    if "test_direct_source_navigation_link_is_not_promoted_to_evidence" not in text:
        text += extra
    TEST_EVIDENCE.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_peer()
    patch_evidence()
    patch_support()
    patch_test()
    print("Applied Chapter 4 Phase 4C quality hotfix: full DGC industry universe cap, parallel canonical refresh, and evidence-placeholder guardrail.")
