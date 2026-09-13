"""Make Admin catalog entry follow the light, low-DOM V2.14 path.

This runs after input_batch_patch. It deliberately keeps catalog typing in a native
Streamlit form, but uses the same text-area widget that is empirically smooth in the
QLKH note field and replaces interactive dataframe canvases with lightweight static
HTML tables. No callbacks or per-keystroke backend work are introduced.
"""


def _replace_span(source: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Catalog fast patch cannot find start: {label}")
    end = source.find(end_marker, start + len(start_marker))
    if end < 0:
        raise RuntimeError(f"Catalog fast patch cannot find end: {label}")
    return source[:start] + replacement + source[end:]


def patch_source(source: str) -> str:
    reason_manager = '''def _catalog_static_table(df, columns):
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
    st.markdown('<div class="khdn-catalog-table-wrap"><table class="khdn-catalog-table"><thead><tr>'+head+'</tr></thead><tbody>'+"".join(body)+'</tbody></table></div>',unsafe_allow_html=True)


def _render_reason_category_manager(u):
    st.subheader("Nhóm nguyên nhân trả lại / hủy")
    st.caption("Tên nhóm nguyên nhân được dùng làm danh mục chuẩn. Khi CBHT trả lại hoặc CBQLKH hủy hồ sơ, người thao tác vẫn phải nhập thêm lý do chi tiết.")
    kind_label=st.radio("Danh mục nguyên nhân",["↩️ Trả lại","🗑️ Hủy hồ sơ"],horizontal=True,key="reason_catalog_kind_v214")
    kind="RETURN" if kind_label.startswith("↩️") else "CANCEL"
    title="Nhóm nguyên nhân trả lại" if kind=="RETURN" else "Nhóm nguyên nhân hủy"
    st.markdown(f"#### {title}")

    # Fast create path comes first so the editor is not preceded by a heavy grid.
    with st.form(f"reason_create_{kind}",clear_on_submit=False,enter_to_submit=False):
        name=st.text_area("Tên nhóm nguyên nhân mới",height=68,key=f"catalog_fast_name_reason_{kind}")
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

    df=qdf("SELECT id,name,active,created_at,updated_at FROM reason_categories WHERE reason_type=? ORDER BY id",(kind,))
    if df.empty:
        st.info("Chưa có nhóm nguyên nhân.")
    else:
        show=df.copy()
        show["active"]=show["active"].map({1:"Đang sử dụng",0:"Đã khóa"}).fillna(show["active"])
        _catalog_static_table(show,[('id','ID'),('name','Tên nhóm nguyên nhân'),('active','Trạng thái'),('created_at','Ngày tạo'),('updated_at','Cập nhật')])

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
    source = _replace_span(
        source,
        'def _catalog_static_table(df, columns):\n' if 'def _catalog_static_table(df, columns):\n' in source else 'def _render_reason_category_manager(u):\n',
        'def user_by_username(username, active_only=True):\n',
        reason_manager,
        'reason manager',
    )

    task_type_block = '''    if admin_view == "types":
        # Same browser-local entry behavior as V2.14, using the already-proven
        # smooth text-area widget from the QLKH note field.
        with st.form("new_type",clear_on_submit=False,enter_to_submit=False):
            name=st.text_area("Tên công việc mới",height=68,key="catalog_fast_name_task_type")
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

        types=qdf("SELECT id,name,active,created_at,updated_at FROM task_types ORDER BY id")
        if types.empty:
            st.info("Chưa có loại công việc.")
        else:
            show=types.copy(); show["active"]=show["active"].map({1:"Đang sử dụng",0:"Đã khóa"}).fillna(show["active"])
            _catalog_static_table(show,[('id','ID'),('name','Tên công việc'),('active','Trạng thái'),('created_at','Ngày tạo'),('updated_at','Cập nhật')])
            xid=st.selectbox("Chọn loại công việc để sửa",types.id.astype(int).tolist(),format_func=lambda x:types[types.id.astype(int)==int(x)].iloc[0]["name"],key="catalog_fast_task_type_edit_select")
            r=types[types.id.astype(int)==int(xid)].iloc[0]
            with st.form(f"catalog_fast_task_type_edit_{int(xid)}",clear_on_submit=False,enter_to_submit=False):
                nactive=st.checkbox("Đang sử dụng",value=bool(r.active))
                save_type=st.form_submit_button("Cập nhật loại công việc")
            if save_type:
                execute("UPDATE task_types SET active=?,updated_at=? WHERE id=?",(int(nactive),now_str(),xid)); _active_task_types_cached.clear(); audit(u["id"],"UPDATE_TASK_TYPE","task_type",xid,f"active={nactive}"); st.success("Đã cập nhật."); st.rerun()

'''
    source = _replace_span(
        source,
        '    if admin_view == "types":\n',
        '    if admin_view == "reasons":\n',
        task_type_block,
        'task type manager',
    )

    checks=[
        'key="catalog_fast_name_task_type"',
        'key=f"catalog_fast_name_reason_{kind}"',
        'class="khdn-catalog-table"',
        'enter_to_submit=False',
    ]
    for marker in checks:
        if marker not in source:
            raise RuntimeError(f"Catalog fast marker missing: {marker}")
    if 'on_change="ignore"' in source or "on_change='ignore'" in source:
        raise RuntimeError("Invalid Streamlit string callback detected in catalog fast path")
    compile(source,"<khdn-catalog-input-fast-patch>","exec")
    return source
