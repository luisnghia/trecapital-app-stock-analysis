"""Batch task-entry payloads and keep catalog entry close to the fast V2.14 flow.

The catalog fast path deliberately uses plain native Streamlit widgets: the table is
rendered once, typing happens inside st.form without callbacks, and server work only
runs on submit. This matches the simple behavior visible in the V2.14 local UI while
preserving the newer reason-category workflow and task-entry batching.
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


def _replace_span(source: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Input batch patch cannot find span start: {label}")
    end = source.find(end_marker, start + len(start_marker))
    if end < 0:
        raise RuntimeError(f"Input batch patch cannot find span end: {label}")
    return source[:start] + replacement + source[end:]


def patch_source(source: str) -> str:
    # Keep CIF/name search live. Everything after customer selection is one local
    # browser form, so changing value/note/selectors does not rerun the app.
    source = _wrap_block(
        source,
        '        validation=st.session_state.get("ql_new_validation",{}); types=active_task_types(); cust=customer_selector("ql_new_cust",validation.get("customer")); support_df=all_users("Cán bộ hỗ trợ",active_only=True); sid=None\n',
        '    elif view=="review":\n',
        'qlkh_create_payload_form',
        'if st.button("Giao hồ sơ cho Cán bộ hỗ trợ",type="primary",use_container_width=True,key="ql_create_btn"):',
        'if st.form_submit_button("Giao hồ sơ cho Cán bộ hỗ trợ",type="primary",use_container_width=True):',
        'QLKH create payload',
    )
    source = _wrap_block(
        source,
        '        validation=st.session_state.get("new_task_validation",{}); types=active_task_types(); cust=customer_selector("new_cust",validation.get("customer")); qlkh_df=all_users("Cán bộ QLKH",active_only=True); qid_default=None\n',
        '    elif view=="work":\n',
        'support_create_payload_form',
        'if st.button("Tạo tác nghiệp",use_container_width=True,type="primary"):',
        'if st.form_submit_button("Tạo tác nghiệp",use_container_width=True,type="primary"):',
        'CBHT create payload',
    )

    # Reason master: one selected category at a time (so RETURN and CANCEL are not
    # both rendered), but within that category use the old simple V2.14-style page:
    # table -> plain create form -> edit controls. No extra "mode" navigation.
    reason_manager = '''def _render_reason_category_manager(u):
    st.subheader("Nhóm nguyên nhân trả lại / hủy")
    st.caption("Tên nhóm nguyên nhân được dùng làm danh mục chuẩn. Khi CBHT trả lại hoặc CBQLKH hủy hồ sơ, người thao tác vẫn phải nhập thêm lý do chi tiết.")
    kind_label=st.radio("Danh mục nguyên nhân",["↩️ Trả lại","🗑️ Hủy hồ sơ"],horizontal=True,key="reason_catalog_kind_v214")
    kind="RETURN" if kind_label.startswith("↩️") else "CANCEL"
    title="Nhóm nguyên nhân trả lại" if kind=="RETURN" else "Nhóm nguyên nhân hủy"
    st.markdown(f"#### {title}")

    df=qdf("SELECT id,name,active,created_at,updated_at FROM reason_categories WHERE reason_type=? ORDER BY id",(kind,))
    if df.empty:
        st.info("Chưa có nhóm nguyên nhân.")
    else:
        show=df.copy()
        show["active"]=show["active"].map({1:"Đang sử dụng",0:"Đã khóa"}).fillna(show["active"])
        st.dataframe(show.rename(columns={"id":"ID","name":"Tên nhóm nguyên nhân","active":"Trạng thái","created_at":"Ngày tạo","updated_at":"Cập nhật"}),use_container_width=True,hide_index=True)

    with st.form(f"reason_create_{kind}"):
        name=st.text_input("Tên nhóm nguyên nhân mới",key=f"reason_create_name_{kind}")
        ok=st.form_submit_button("Thêm nhóm nguyên nhân")
    if ok:
        clean=name.strip()
        if not clean:
            st.error("Bắt buộc nhập tên nhóm nguyên nhân.")
        else:
            try:
                ts=now_str(); xid=execute("INSERT INTO reason_categories(reason_type,name,active,created_by,created_at,updated_at) VALUES(?,?,1,?,?,?)",(kind,clean,int(u["id"]),ts,ts))
                audit(u["id"],"CREATE_REASON_CATEGORY","reason_category",xid,f"type={kind}; name={clean}")
                LOGGER.info("REASON_CATEGORY_CREATE actor=%s type=%s id=%s name=%s",u["id"],kind,xid,clean)
                st.success("Đã thêm nhóm nguyên nhân."); st.rerun()
            except sqlite3.IntegrityError:
                st.error("Tên nhóm nguyên nhân đã tồn tại trong danh mục này.")

    if not df.empty:
        xid=st.selectbox("Chọn nhóm nguyên nhân để sửa",df.id.astype(int).tolist(),key=f"reason_edit_select_{kind}",format_func=lambda x:str(df[df.id.astype(int)==int(x)].iloc[0]["name"]))
        row=df[df.id.astype(int)==int(xid)].iloc[0]
        with st.form(f"reason_edit_form_{kind}_{int(xid)}"):
            new_name=st.text_input("Tên nhóm nguyên nhân",value=str(row["name"]),key=f"reason_edit_name_{kind}_{int(xid)}")
            active=st.checkbox("Đang sử dụng",value=bool(row["active"]),key=f"reason_edit_active_{kind}_{int(xid)}")
            save_reason=st.form_submit_button("Cập nhật nhóm nguyên nhân")
        if save_reason:
            clean=new_name.strip()
            if not clean:
                st.error("Tên nhóm nguyên nhân không được để trống.")
            else:
                try:
                    execute("UPDATE reason_categories SET name=?,active=?,updated_at=? WHERE id=? AND reason_type=?",(clean,int(active),now_str(),int(xid),kind))
                    audit(u["id"],"UPDATE_REASON_CATEGORY","reason_category",xid,f"type={kind}; name={clean}; active={active}")
                    LOGGER.info("REASON_CATEGORY_UPDATE actor=%s type=%s id=%s active=%s",u["id"],kind,xid,active)
                    st.success("Đã cập nhật nhóm nguyên nhân."); st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Tên nhóm nguyên nhân đã tồn tại trong danh mục này.")


'''
    source = _replace_span(
        source,
        'def _render_reason_category_manager(u):\n',
        'def user_by_username(username, active_only=True):\n',
        reason_manager,
        'V2.14-style reason manager',
    )

    # Task type catalog: intentionally mirror the compact pre-online/V2.14 flow
    # visible in the user's local screenshot. No extra mode radio, no callbacks,
    # and the create field is a plain text_input inside a plain st.form.
    task_type_block = '''    if admin_view == "types":
        types=qdf("SELECT id,name,active,created_at,updated_at FROM task_types ORDER BY id")
        st.dataframe(types,use_container_width=True,hide_index=True)
        with st.form("new_type"):
            name=st.text_input("Tên công việc mới")
            ok=st.form_submit_button("Thêm loại công việc")
        if ok:
            clean=name.strip()
            if not clean:
                st.error("Bắt buộc nhập tên công việc.")
            else:
                try:
                    ts=now_str(); xid=execute("INSERT INTO task_types(name,sla_hours,active,created_at,updated_at) VALUES(?,8,1,?,?)",(clean,ts,ts)); _active_task_types_cached.clear(); audit(u["id"],"CREATE_TASK_TYPE","task_type",xid,clean); st.success("Đã thêm loại công việc."); st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Tên công việc đã tồn tại.")
        if not types.empty:
            xid=st.selectbox("Chọn loại công việc để sửa",types.id.tolist(),format_func=lambda x:types[types.id==x].iloc[0]["name"])
            r=types[types.id==xid].iloc[0]
            nactive=st.checkbox("Đang sử dụng",value=bool(r.active))
            if st.button("Cập nhật loại công việc"):
                execute("UPDATE task_types SET active=?,updated_at=? WHERE id=?",(int(nactive),now_str(),xid)); _active_task_types_cached.clear(); audit(u["id"],"UPDATE_TASK_TYPE","task_type",xid,f"active={nactive}"); st.success("Đã cập nhật."); st.rerun()

'''
    source = _replace_span(
        source,
        '    if admin_view == "types":\n',
        '    if admin_view == "reasons":\n',
        task_type_block,
        'V2.14-style task type manager',
    )

    if 'on_change="ignore"' in source or "on_change='ignore'" in source:
        raise RuntimeError("Invalid Streamlit string callback detected after input batching")
    required_once=[
        'with st.form("qlkh_create_payload_form"',
        'with st.form("support_create_payload_form"',
        'key="reason_catalog_kind_v214"',
        'with st.form("new_type"):',
    ]
    for marker in required_once:
        if source.count(marker) != 1:
            raise RuntimeError(f"V2.14 fast marker not installed exactly once: {marker}")
    if 'task_type_catalog_mode_fast' in source or 'reason_catalog_mode_' in source:
        raise RuntimeError("Legacy lazy catalog mode controls still present")
    if '    if admin_view == "reasons":\n        _render_reason_category_manager(u)\n' not in source:
        raise RuntimeError("Reason manager route was lost during task-type optimization")
    compile(source, "<khdn-input-batch-patch>", "exec")
    return source
