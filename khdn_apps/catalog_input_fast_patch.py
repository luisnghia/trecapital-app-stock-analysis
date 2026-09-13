"""Make Admin catalog entry use a submit-only browser component.

The catalog-name fields are isolated from Streamlit's widget tree while typing. The
plain DOM input sends no value to Python until the user presses Enter or clicks Add.
Catalog tables are rendered as stable st.html blocks before the component so component
mounting cannot make a previously visible table appear to vanish.
"""


def _replace_span(source: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start=source.find(start_marker)
    if start<0:
        raise RuntimeError(f"Catalog fast patch cannot find start: {label}")
    end=source.find(end_marker,start+len(start_marker))
    if end<0:
        raise RuntimeError(f"Catalog fast patch cannot find end: {label}")
    return source[:start]+replacement+source[end:]


def patch_source(source: str) -> str:
    reason_manager='''from khdn_apps.fast_catalog_input import fast_catalog_input


def _catalog_static_table(df, columns):
    if df is None or df.empty:
        return
    _html=__import__("html")
    head="".join(f"<th>{_html.escape(str(label))}</th>" for _,label in columns)
    body=[]
    for _,row in df.iterrows():
        cells=[]
        for key,_label in columns:
            value=row.get(key,"")
            if value is None or (hasattr(pd,"isna") and pd.isna(value)):
                value=""
            cells.append(f"<td>{_html.escape(str(value))}</td>")
        body.append("<tr>"+"".join(cells)+"</tr>")
    table_html='<div class="khdn-catalog-table-wrap"><table class="khdn-catalog-table"><thead><tr>'+head+'</tr></thead><tbody>'+"".join(body)+'</tbody></table></div>'
    if hasattr(st,"html"):
        st.html(table_html)
    else:
        st.markdown(table_html,unsafe_allow_html=True)


def _render_reason_category_manager(u):
    st.subheader("Nhóm nguyên nhân trả lại / hủy")
    st.caption("Tên nhóm nguyên nhân được dùng làm danh mục chuẩn. Khi CBHT trả lại hoặc CBQLKH hủy hồ sơ, người thao tác vẫn phải nhập thêm lý do chi tiết.")
    kind_label=st.radio("Danh mục nguyên nhân",["↩️ Trả lại","🗑️ Hủy hồ sơ"],horizontal=True,key="reason_catalog_kind_v214")
    kind="RETURN" if kind_label.startswith("↩️") else "CANCEL"
    title="Nhóm nguyên nhân trả lại" if kind=="RETURN" else "Nhóm nguyên nhân hủy"
    st.markdown(f"#### {title}")

    # V2.14 order: list first, then create field, then edit controls. Rendering the
    # table before the iframe prevents layout/component mounting from hiding it.
    df=qdf("SELECT id,name,active,created_at,updated_at FROM reason_categories WHERE reason_type=? ORDER BY id",(kind,))
    if df.empty:
        st.info("Chưa có nhóm nguyên nhân.")
    else:
        show=df.copy(); show["active"]=show["active"].map({1:"Đang sử dụng",0:"Đã khóa"}).fillna(show["active"])
        _catalog_static_table(show,[('id','ID'),('name','Tên nhóm nguyên nhân'),('active','Trạng thái'),('created_at','Ngày tạo'),('updated_at','Cập nhật')])

    _reset_key=f"_catalog_reason_reset_{kind}"
    submitted_name=fast_catalog_input(
        "Tên nhóm nguyên nhân mới",
        "Thêm nhóm nguyên nhân",
        key=f"catalog_submit_only_reason_{kind}",
        reset_token=str(st.session_state.get(_reset_key,0)),
    )
    if submitted_name is not None:
        clean=submitted_name.strip()
        if not clean:
            st.error("Bắt buộc nhập tên nhóm nguyên nhân.")
        else:
            try:
                ts=now_str(); xid=execute("INSERT INTO reason_categories(reason_type,name,active,created_by,created_at,updated_at) VALUES(?,?,1,?,?,?)",(kind,clean,int(u["id"]),ts,ts))
                audit(u["id"],"CREATE_REASON_CATEGORY","reason_category",xid,f"type={kind}; name={clean}")
                LOGGER.info("REASON_CATEGORY_CREATE actor=%s type=%s id=%s name=%s",u["id"],kind,xid,clean)
                st.session_state[_reset_key]=int(st.session_state.get(_reset_key,0))+1
                st.success("Đã thêm nhóm nguyên nhân."); st.rerun()
            except sqlite3.IntegrityError:
                st.error("Tên nhóm nguyên nhân đã tồn tại trong danh mục này.")

    if not df.empty:
        xid=st.selectbox("Chọn nhóm nguyên nhân để sửa",df.id.astype(int).tolist(),key=f"reason_edit_select_{kind}",format_func=lambda x:str(df[df.id.astype(int)==int(x)].iloc[0]["name"]))
        row=df[df.id.astype(int)==int(xid)].iloc[0]
        with st.form(f"reason_edit_form_{kind}_{int(xid)}",clear_on_submit=False,enter_to_submit=False):
            new_name=st.text_area("Tên nhóm nguyên nhân",value=str(row["name"]),height=68,key=f"catalog_fast_edit_reason_{kind}_{int(xid)}")
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
    source=_replace_span(
        source,
        'def _catalog_static_table(df, columns):\n' if 'def _catalog_static_table(df, columns):\n' in source else 'def _render_reason_category_manager(u):\n',
        'def user_by_username(username, active_only=True):\n',
        reason_manager,
        'reason manager',
    )

    task_type_block='''    if admin_view == "types":
        # Exact V2.14 page order: table -> create -> edit. The create input itself
        # remains the zero-keystroke component to preserve the speed improvement.
        types=qdf("SELECT id,name,active,created_at,updated_at FROM task_types ORDER BY id")
        if types.empty:
            st.info("Chưa có loại công việc.")
        else:
            show=types.copy(); show["active"]=show["active"].map({1:"Đang sử dụng",0:"Đã khóa"}).fillna(show["active"])
            _catalog_static_table(show,[('id','ID'),('name','Tên công việc'),('active','Trạng thái'),('created_at','Ngày tạo'),('updated_at','Cập nhật')])

        _reset_key="_catalog_task_type_reset"
        submitted_name=fast_catalog_input(
            "Tên công việc mới",
            "Thêm loại công việc",
            key="catalog_submit_only_task_type",
            reset_token=str(st.session_state.get(_reset_key,0)),
        )
        if submitted_name is not None:
            clean=submitted_name.strip()
            if not clean:
                st.error("Bắt buộc nhập tên công việc.")
            else:
                try:
                    ts=now_str(); xid=execute("INSERT INTO task_types(name,sla_hours,active,created_at,updated_at) VALUES(?,8,1,?,?)",(clean,ts,ts)); _active_task_types_cached.clear(); audit(u["id"],"CREATE_TASK_TYPE","task_type",xid,clean); st.session_state[_reset_key]=int(st.session_state.get(_reset_key,0))+1; st.success("Đã thêm loại công việc."); st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Tên công việc đã tồn tại.")

        if not types.empty:
            xid=st.selectbox("Chọn loại công việc để sửa",types.id.astype(int).tolist(),format_func=lambda x:types[types.id.astype(int)==int(x)].iloc[0]["name"],key="catalog_fast_task_type_edit_select")
            r=types[types.id.astype(int)==int(xid)].iloc[0]
            with st.form(f"catalog_fast_task_type_edit_{int(xid)}",clear_on_submit=False,enter_to_submit=False):
                nactive=st.checkbox("Đang sử dụng",value=bool(r.active))
                save_type=st.form_submit_button("Cập nhật loại công việc")
            if save_type:
                execute("UPDATE task_types SET active=?,updated_at=? WHERE id=?",(int(nactive),now_str(),xid)); _active_task_types_cached.clear(); audit(u["id"],"UPDATE_TASK_TYPE","task_type",xid,f"active={nactive}"); st.success("Đã cập nhật."); st.rerun()

'''
    source=_replace_span(source,'    if admin_view == "types":\n','    if admin_view == "reasons":\n',task_type_block,'task type manager')

    required=[
        'from khdn_apps.fast_catalog_input import fast_catalog_input',
        'key="catalog_submit_only_task_type"',
        'key=f"catalog_submit_only_reason_{kind}"',
        'class="khdn-catalog-table"',
        'st.html(table_html)',
        '# Exact V2.14 page order: table -> create -> edit.',
    ]
    for marker in required:
        if marker not in source:
            raise RuntimeError(f"Catalog submit-only marker missing: {marker}")
    if 'on_change="ignore"' in source or "on_change='ignore'" in source:
        raise RuntimeError("Invalid Streamlit string callback detected in catalog fast path")
    compile(source,"<khdn-catalog-input-fast-patch>","exec")
    return source
