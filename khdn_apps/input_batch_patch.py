"""Batch interactive task-entry payloads and keep catalog editors lightweight.

The fast path is based on the QLKH note widget: native Streamlit text entry with no
callback while typing, with server work deferred until an explicit submit. For admin
catalogs we also avoid rendering/querying the heavy list/edit UI while the user is
creating a new name.
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

    reason_manager = '''def _render_reason_category_manager(u):
    st.subheader("Nhóm nguyên nhân trả lại / hủy")
    st.caption("Tên nhóm nguyên nhân được dùng làm danh mục chuẩn. Khi CBHT trả lại hoặc CBQLKH hủy hồ sơ, người thao tác vẫn phải nhập thêm lý do chi tiết.")
    kind_label=st.radio("Danh mục nguyên nhân",["↩️ Trả lại","🗑️ Hủy hồ sơ"],horizontal=True,key="reason_catalog_kind_fast")
    kind="RETURN" if kind_label.startswith("↩️") else "CANCEL"
    title="Nhóm nguyên nhân trả lại" if kind=="RETURN" else "Nhóm nguyên nhân hủy"
    mode=st.radio("Thao tác",["➕ Thêm mới","📋 Danh sách / chỉnh sửa"],horizontal=True,key=f"reason_catalog_mode_{kind}")
    st.markdown(f"#### {title}")
    if mode=="➕ Thêm mới":
        with st.form(f"reason_fast_create_{kind}", clear_on_submit=False, enter_to_submit=False):
            name=st.text_input("Tên nhóm nguyên nhân mới", key=f"reason_fast_name_{kind}")
            ok=st.form_submit_button("Thêm nhóm nguyên nhân")
        if ok:
            clean=name.strip()
            if not clean: st.error("Bắt buộc nhập tên nhóm nguyên nhân.")
            else:
                try:
                    ts=now_str(); xid=execute("INSERT INTO reason_categories(reason_type,name,active,created_by,created_at,updated_at) VALUES(?,?,1,?,?,?)",(kind,clean,int(u["id"]),ts,ts))
                    audit(u["id"],"CREATE_REASON_CATEGORY","reason_category",xid,f"type={kind}; name={clean}")
                    LOGGER.info("REASON_CATEGORY_CREATE actor=%s type=%s id=%s name=%s",u["id"],kind,xid,clean)
                    st.success("Đã thêm nhóm nguyên nhân."); st.rerun()
                except sqlite3.IntegrityError: st.error("Tên nhóm nguyên nhân đã tồn tại trong danh mục này.")
        st.caption("Danh sách hiện có chỉ được tải khi chọn **Danh sách / chỉnh sửa**, giúp ô nhập phản hồi nhanh hơn.")
        return
    df=qdf("SELECT id,name,active,created_at,updated_at FROM reason_categories WHERE reason_type=? ORDER BY id",(kind,))
    if df.empty:
        st.info("Chưa có nhóm nguyên nhân."); return
    show=df.copy(); show["active"]=show["active"].map({1:"Đang sử dụng",0:"Đã khóa"}).fillna(show["active"])
    st.dataframe(show.rename(columns={"id":"ID","name":"Tên nhóm nguyên nhân","active":"Trạng thái","created_at":"Ngày tạo","updated_at":"Cập nhật"}),use_container_width=True,hide_index=True)
    xid=st.selectbox("Chọn nhóm nguyên nhân để sửa",df.id.astype(int).tolist(),key=f"reason_fast_edit_select_{kind}",format_func=lambda x:str(df[df.id.astype(int)==int(x)].iloc[0]["name"]))
    row=df[df.id.astype(int)==int(xid)].iloc[0]
    with st.form(f"reason_fast_edit_form_{kind}_{int(xid)}", clear_on_submit=False, enter_to_submit=False):
        new_name=st.text_input("Tên nhóm nguyên nhân",value=str(row["name"]),key=f"reason_fast_edit_name_{kind}_{int(xid)}")
        active=st.checkbox("Đang sử dụng",value=bool(row["active"]),key=f"reason_fast_edit_active_{kind}_{int(xid)}")
        save_reason=st.form_submit_button("Cập nhật nhóm nguyên nhân")
    if save_reason:
        clean=new_name.strip()
        if not clean: st.error("Tên nhóm nguyên nhân không được để trống.")
        else:
            try:
                execute("UPDATE reason_categories SET name=?,active=?,updated_at=? WHERE id=? AND reason_type=?",(clean,int(active),now_str(),int(xid),kind))
                audit(u["id"],"UPDATE_REASON_CATEGORY","reason_category",xid,f"type={kind}; name={clean}; active={active}")
                LOGGER.info("REASON_CATEGORY_UPDATE actor=%s type=%s id=%s active=%s",u["id"],kind,xid,active)
                st.success("Đã cập nhật nhóm nguyên nhân."); st.rerun()
            except sqlite3.IntegrityError: st.error("Tên nhóm nguyên nhân đã tồn tại trong danh mục này.")


'''
    source = _replace_span(source,'def _render_reason_category_manager(u):\n','def user_by_username(username, active_only=True):\n',reason_manager,'lazy reason manager')

    task_type_block = '''    if admin_view == "types":
        st.subheader("Loại công việc")
        type_mode=st.radio("Thao tác",["➕ Thêm mới","📋 Danh sách / trạng thái"],horizontal=True,key="task_type_catalog_mode_fast")
        if type_mode=="➕ Thêm mới":
            with st.form("new_type", clear_on_submit=False, enter_to_submit=False):
                name=st.text_input("Tên công việc mới", key="new_task_type_name_fast")
                ok=st.form_submit_button("Thêm loại công việc")
            if ok:
                clean=name.strip()
                if not clean: st.error("Bắt buộc nhập tên công việc.")
                else:
                    try:
                        ts=now_str(); xid=execute("INSERT INTO task_types(name,sla_hours,active,created_at,updated_at) VALUES(?,8,1,?,?)",(clean,ts,ts)); _active_task_types_cached.clear(); audit(u["id"],"CREATE_TASK_TYPE","task_type",xid,clean); st.success("Đã thêm loại công việc."); st.rerun()
                    except sqlite3.IntegrityError: st.error("Tên công việc đã tồn tại.")
            st.caption("Danh sách hiện có chỉ được tải khi chọn **Danh sách / trạng thái**, giúp ô nhập phản hồi nhanh hơn.")
        else:
            types=qdf("SELECT id,name,active,created_at,updated_at FROM task_types ORDER BY id")
            if types.empty: st.info("Chưa có loại công việc.")
            else:
                st.dataframe(types,use_container_width=True,hide_index=True)
                xid=st.selectbox("Chọn loại công việc để sửa",types.id.tolist(),key="task_type_edit_select_fast",format_func=lambda x:types[types.id==x].iloc[0]["name"])
                r=types[types.id==xid].iloc[0]
                with st.form(f"task_type_edit_form_{int(xid)}", clear_on_submit=False, enter_to_submit=False):
                    nactive=st.checkbox("Đang sử dụng",value=bool(r.active),key=f"task_type_edit_active_{int(xid)}")
                    save_type=st.form_submit_button("Cập nhật loại công việc")
                if save_type:
                    execute("UPDATE task_types SET active=?,updated_at=? WHERE id=?",(int(nactive),now_str(),xid)); _active_task_types_cached.clear(); audit(u["id"],"UPDATE_TASK_TYPE","task_type",xid,f"active={nactive}"); st.success("Đã cập nhật."); st.rerun()

'''
    # IMPORTANT: stop before the reason block inserted by reason_categories_patch.
    # Using the Audit block as the end marker would accidentally delete reason UI.
    source = _replace_span(source,'    if admin_view == "types":\n','    if admin_view == "reasons":\n',task_type_block,'lazy task-type manager')

    if 'on_change="ignore"' in source or "on_change='ignore'" in source:
        raise RuntimeError("Invalid Streamlit string callback detected after input batching")
    required_once=['with st.form("qlkh_create_payload_form"','with st.form("support_create_payload_form"','key="reason_catalog_kind_fast"','key="task_type_catalog_mode_fast"']
    for marker in required_once:
        if source.count(marker) != 1: raise RuntimeError(f"Input fast marker not installed exactly once: {marker}")
    if '    if admin_view == "reasons":\n        _render_reason_category_manager(u)\n' not in source:
        raise RuntimeError("Reason manager route was lost during task-type optimization")
    compile(source, "<khdn-input-batch-patch>", "exec")
    return source
