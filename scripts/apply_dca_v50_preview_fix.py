from __future__ import annotations

"""Remove nested-expander risk from V50 editable-table heatmap preview."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "modules" / "deep_company_analysis" / "table_format.py"

OLD = '''    committed = _coerce_frame(st.session_state.get(rows_key)).reset_index(drop=True)
    if any(infer_numeric_kind(str(column)) != "text" for column in committed.columns) and not committed.empty:
        with st.expander("🌡️ Xem format số liệu / heatmap", expanded=False):
            render_static_table(committed, use_container_width=True, hide_index=True)
    return committed
'''

NEW = '''    committed = _coerce_frame(st.session_state.get(rows_key)).reset_index(drop=True)
    # Some chapter editors already live inside an expander. Streamlit 1.40.x forbids
    # nested expanders, so show the formatted heatmap preview only after an explicit
    # table commit and render it directly in the current container.
    if (
        submitted
        and any(infer_numeric_kind(str(column)) != "text" for column in committed.columns)
        and not committed.empty
    ):
        st.caption("🌡️ Format số liệu / heatmap sau khi áp dụng thay đổi")
        render_static_table(committed, use_container_width=True, hide_index=True)
    return committed
'''


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("V50 heatmap preview compatibility already applied.")
        return
    if OLD not in text:
        raise RuntimeError("V50 heatmap preview anchor not found")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("V50 heatmap preview compatibility applied.")


if __name__ == "__main__":
    main()
