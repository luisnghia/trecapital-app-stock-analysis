from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def patch_chapter1_gate_history() -> None:
    name = "modules/deep_company_analysis/chapter1.py"
    s = read(name)
    old = '''    history = load_gate_history(ticker)\n    st.subheader(f"Gate History — {ticker}")\n    if hasattr(st, "html"):\n        st.html(_html_table(history))\n'''
    new = '''    history = load_gate_history(ticker)\n    st.subheader(f"Gate History — {ticker}")\n    if not history.empty:\n        history = interactive_sort_frame(history, key=f"ch1_gate_history_{ticker}")\n    if hasattr(st, "html"):\n        st.html(_html_table(history))\n'''
    assert old in s, "Chapter1 Gate History pattern changed"
    write(name, s.replace(old, new, 1))


def patch_monitoring_queue() -> None:
    name = "modules/deep_company_analysis/monitoring.py"
    s = read(name)
    imp = "from modules.deep_company_analysis.table_format import interactive_sort_frame\n"
    if imp not in s:
        marker = "import streamlit as st\n"
        assert marker in s
        s = s.replace(marker, marker + "\n" + imp, 1)
    old = '''    queue = load_review_queue(open_only=True)\n    display = queue.drop(columns=["ID", "Trạng thái"], errors="ignore")\n    if hasattr(st, "html"):\n'''
    new = '''    queue = load_review_queue(open_only=True)\n    display = queue.drop(columns=["ID", "Trạng thái"], errors="ignore")\n    if not display.empty:\n        display = interactive_sort_frame(display, key=f"dca_review_queue_table_{current_ticker}")\n    if hasattr(st, "html"):\n'''
    assert old in s, "Monitoring Review Queue pattern changed"
    write(name, s.replace(old, new, 1))


def patch_chapter5_custom_tables() -> None:
    name = "modules/deep_company_analysis/chapter5_page_support.py"
    s = read(name)
    old1 = '        st.html(_wrapped_html_table(lock_table, 420))\n'
    new1 = '        render_static_table(lock_table, height=420)\n'
    old2 = '        st.html(_wrapped_html_table(report.research_readiness, 360))\n'
    new2 = '        render_static_table(report.research_readiness, height=360)\n'
    assert old1 in s and old2 in s, "Chapter5 custom lock table patterns changed"
    s = s.replace(old1, new1, 1).replace(old2, new2, 1)
    write(name, s)


def patch_chapter6_preview_and_snapshots() -> None:
    name = "modules/deep_company_analysis/chapter6_page_support.py"
    s = read(name)
    old_preview = '''            st.html(financial_table_html(edited, columns))\n'''
    new_preview = '''            render_static_table(edited, height=min(360, 90 + 30 * len(edited)), sort_key=f"{key}_formatted_preview")\n'''
    assert old_preview in s, "Chapter6 formatted preview pattern changed"
    s = s.replace(old_preview, new_preview, 1)

    old_snapshot = '''    snapshots = list_snapshots(ticker, limit=8)\n    if snapshots:\n        with st.expander("🕘 Snapshot gần nhất", expanded=False):\n            rows_html = "".join(\n                "<tr>"\n                f"<td>{int(item['id'])}</td>"\n                f"<td>{escape(str(item['created_at']))}</td>"\n                f"<td>{escape(str(item['understanding_status']))}</td>"\n                "</tr>"\n                for item in snapshots\n            )\n            st.html(\n                "<div style='overflow-x:auto;width:100%'>"\n                "<table style='width:100%;table-layout:fixed;border-collapse:collapse;white-space:normal;overflow-wrap:anywhere'>"\n                "<thead><tr><th>Snapshot</th><th>Created</th><th>Research completion</th></tr></thead>"\n                f"<tbody>{rows_html}</tbody></table></div>"\n            )\n'''
    new_snapshot = '''    snapshots = list_snapshots(ticker, limit=8)\n    if snapshots:\n        with st.expander("🕘 Snapshot gần nhất", expanded=False):\n            snapshot_table = pd.DataFrame([\n                {\n                    "Snapshot": int(item["id"]),\n                    "Created": str(item["created_at"]),\n                    "Research completion": str(item["understanding_status"]),\n                }\n                for item in snapshots\n            ])\n            render_static_table(snapshot_table, height=min(330, 90 + 30 * len(snapshot_table)), sort_key=f"ch6_snapshots_{ticker}")\n'''
    assert old_snapshot in s, "Chapter6 snapshot HTML pattern changed"
    s = s.replace(old_snapshot, new_snapshot, 1)
    write(name, s)


def main() -> None:
    patch_chapter1_gate_history()
    patch_monitoring_queue()
    patch_chapter5_custom_tables()
    patch_chapter6_preview_and_snapshots()
    print("V32 remaining custom-table patches applied")


if __name__ == "__main__":
    main()
