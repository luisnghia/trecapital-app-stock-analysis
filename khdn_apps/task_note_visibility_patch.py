"""Show the task note/instructions consistently on every task detail/action screen.

The production app is reconstructed from compressed source, so this transformer is
applied after the reason-category transformer. It deliberately changes presentation
only: workflow state, permissions, scoring and timestamps are untouched.
"""


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"Task-note visibility patch cannot find source fragment: {label}")
    return source.replace(old, new, 1)


def patch_source(source: str) -> str:
    # 1) One central renderer: every selected task that already uses the standard
    # task chips now also shows the full Note / processing instruction immediately
    # underneath. This covers receive, work, review, returned/reassigned, Leader
    # monitoring and history detail views without duplicating role-specific logic.
    old = '''    st.markdown('<div class="task-chip-row">'+''.join(f'<span class="task-chip {cls}">{html.escape(str(txt))}</span>' for cls,txt in parts)+'</div>', unsafe_allow_html=True)\n\n\ndef _task_list_height'''
    new = '''    st.markdown('<div class="task-chip-row">'+''.join(f'<span class="task-chip {cls}">{html.escape(str(txt))}</span>' for cls,txt in parts)+'</div>', unsafe_allow_html=True)\n    note_value = _g("note", "")\n    try:\n        if pd.isna(note_value):\n            note_value = ""\n    except Exception:\n        pass\n    note_text = str(note_value or "").strip()\n    if note_text:\n        st.info(f"📝 **Ghi chú / yêu cầu xử lý**\\n\\n{note_text}")\n    else:\n        st.caption("📝 Ghi chú / yêu cầu xử lý: Không có ghi chú.")\n\n\ndef _task_list_height'''
    source = _replace_once(source, old, new, "central task note renderer")

    # 2) The receive screen used to show a small duplicate caption. The central
    # renderer above is more prominent and preserves multi-line notes.
    old = '''                if row.note: st.caption(f"Ghi chú: {row.note}")\n'''
    if old in source:
        source = source.replace(old, "", 1)

    # 3) Review keeps processing time separate; the note is now rendered in the
    # common task detail block immediately above the score form.
    old = '''                st.caption(f"Thời gian xử lý: **{money(elapsed_min)} phút**" + (f" · Ghi chú: {row.note}" if row.note else ""))\n'''
    new = '''                st.caption(f"Thời gian xử lý: **{money(elapsed_min)} phút**")\n'''
    source = _replace_once(source, old, new, "review duplicate note caption")

    # 4) QLKH evaluation-history detail also uses the common renderer; include
    # t.note in that detail query so historical jobs display their stored note.
    old = '''                                                     t.assigned_at,t.start_time,t.end_time,t.closed_time,t.status,t.current_round,t.rework_count\n'''
    new = '''                                                     t.assigned_at,t.start_time,t.end_time,t.closed_time,t.note,t.status,t.current_round,t.rework_count\n'''
    source = _replace_once(source, old, new, "QLKH history detail note field")

    return source
