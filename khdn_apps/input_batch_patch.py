"""Batch interactive task-entry payloads in Streamlit forms.

The QLKH note field feels fast because normal text editing stays in the browser
until a widget event is committed. This patch extends that principle to the
whole non-search task payload: choose customer first (live search stays outside),
then edit assignee/task/currency/value/note locally and submit once.
"""


def _wrap_block(source: str, start_marker: str, end_marker: str, form_name: str, button_old: str, button_new: str, label: str) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Input batch patch cannot find start: {label}")
    body_start = start + len(start_marker)
    end = source.find(end_marker, body_start)
    if end < 0:
        raise RuntimeError(f"Input batch patch cannot find end: {label}")
    body = source[body_start:end]
    if button_old not in body:
        raise RuntimeError(f"Input batch patch cannot find submit button: {label}")
    body = body.replace(button_old, button_new, 1)
    indented = "".join(("    " + line if line.strip() else line) for line in body.splitlines(True))
    replacement = start_marker + f'        with st.form("{form_name}", clear_on_submit=False, enter_to_submit=False):\n' + indented
    return source[:start] + replacement + source[end:]


def patch_source(source: str) -> str:
    # QLKH create/give-file page: customer search remains live outside the form.
    # Everything after customer selection is a single browser-local payload.
    source = _wrap_block(
        source,
        '        validation=st.session_state.get("ql_new_validation",{}); types=active_task_types(); cust=customer_selector("ql_new_cust",validation.get("customer")); support_df=all_users("Cán bộ hỗ trợ",active_only=True); sid=None\n',
        '    elif view=="review":\n',
        'qlkh_create_payload_form',
        'if st.button("Giao hồ sơ cho Cán bộ hỗ trợ",type="primary",use_container_width=True,key="ql_create_btn"):',
        'if st.form_submit_button("Giao hồ sơ cho Cán bộ hỗ trợ",type="primary",use_container_width=True):',
        'QLKH create payload',
    )

    # CBHT self-create page: same pattern; customer search stays live, payload is batched.
    source = _wrap_block(
        source,
        '        validation=st.session_state.get("new_task_validation",{}); types=active_task_types(); cust=customer_selector("new_cust",validation.get("customer")); qlkh_df=all_users("Cán bộ QLKH",active_only=True); qid_default=None\n',
        '    elif view=="work":\n',
        'support_create_payload_form',
        'if st.button("Tạo tác nghiệp",use_container_width=True,type="primary"):',
        'if st.form_submit_button("Tạo tác nghiệp",use_container_width=True,type="primary"):',
        'CBHT create payload',
    )

    # Existing admin catalog forms are already the correct fast pattern; explicitly
    # disable Enter-to-submit so mobile IME/newline actions cannot cause accidental reruns.
    source = source.replace('with st.form("new_type"):', 'with st.form("new_type", clear_on_submit=False, enter_to_submit=False):', 1)
    source = source.replace('with st.form(create_key):', 'with st.form(create_key, clear_on_submit=False, enter_to_submit=False):', 1)

    # Guardrails: never reintroduce the invalid string-callback crash.
    if 'on_change="ignore"' in source or "on_change='ignore'" in source:
        raise RuntimeError("Invalid Streamlit string callback detected after input batching")
    if 'qlkh_create_payload_form' not in source or 'support_create_payload_form' not in source:
        raise RuntimeError("Task payload batching was not installed")
    compile(source, "<khdn-input-batch-patch>", "exec")
    return source
