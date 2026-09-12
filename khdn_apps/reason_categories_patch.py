"""V2.38 preview patch: mandatory reason groups for CBHT returns and QLKH cancellations.

This transformer is intentionally deterministic and only targets exact V2.38 source
fragments after mobile_nav_patch has run. It does not touch Leader work-management UI.
"""


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"Reason-category patch cannot find V2.38 fragment: {label}")
    return source.replace(old, new, 1)


def patch_source(source: str) -> str:
    # --- 1. Schema: category master + immutable task reason events ---
    old = '''        CREATE TABLE IF NOT EXISTS system_audit (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            actor_user_id INTEGER,\n            action TEXT NOT NULL,\n            object_type TEXT,\n            object_id TEXT,\n            detail TEXT,\n            created_at TEXT NOT NULL,\n            FOREIGN KEY(actor_user_id) REFERENCES users(id)\n        );\n'''
    new = '''        CREATE TABLE IF NOT EXISTS reason_categories (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            reason_type TEXT NOT NULL CHECK(reason_type IN ('RETURN','CANCEL')),\n            name TEXT NOT NULL,\n            active INTEGER NOT NULL DEFAULT 1,\n            created_by INTEGER,\n            created_at TEXT NOT NULL,\n            updated_at TEXT NOT NULL,\n            UNIQUE(reason_type,name),\n            FOREIGN KEY(created_by) REFERENCES users(id)\n        );\n        CREATE TABLE IF NOT EXISTS task_reason_events (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            task_id INTEGER NOT NULL,\n            actor_user_id INTEGER NOT NULL,\n            event_type TEXT NOT NULL CHECK(event_type IN ('RETURN','CANCEL')),\n            reason_category_id INTEGER NOT NULL,\n            reason_category_name TEXT NOT NULL,\n            reason_detail TEXT NOT NULL,\n            created_at TEXT NOT NULL,\n            FOREIGN KEY(task_id) REFERENCES tasks(id),\n            FOREIGN KEY(actor_user_id) REFERENCES users(id),\n            FOREIGN KEY(reason_category_id) REFERENCES reason_categories(id)\n        );\n        CREATE TABLE IF NOT EXISTS system_audit (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            actor_user_id INTEGER,\n            action TEXT NOT NULL,\n            object_type TEXT,\n            object_id TEXT,\n            detail TEXT,\n            created_at TEXT NOT NULL,\n            FOREIGN KEY(actor_user_id) REFERENCES users(id)\n        );\n'''
    source = _replace_once(source, old, new, "schema tables")

    old = '''        CREATE INDEX IF NOT EXISTS idx_actions_action_task ON task_actions(action,task_id);\n        CREATE INDEX IF NOT EXISTS idx_eval_task_round ON evaluations(task_id,round_no);\n'''
    new = '''        CREATE INDEX IF NOT EXISTS idx_actions_action_task ON task_actions(action,task_id);\n        CREATE INDEX IF NOT EXISTS idx_reason_categories_type_active ON reason_categories(reason_type,active,id);\n        CREATE INDEX IF NOT EXISTS idx_task_reason_events_task ON task_reason_events(task_id,event_type,id);\n        CREATE INDEX IF NOT EXISTS idx_eval_task_round ON evaluations(task_id,round_no);\n'''
    source = _replace_once(source, old, new, "schema indexes")

    # --- 2. Helpers: category selection, atomic workflow transition, admin maintenance ---
    old = '''def user_by_username(username, active_only=True):\n'''
    helpers = r'''def active_reason_categories(reason_type):
    kind=str(reason_type or "").upper().strip()
    if kind not in {"RETURN","CANCEL"}:
        return pd.DataFrame(columns=["id","name"])
    return qdf("SELECT id,name FROM reason_categories WHERE reason_type=? AND active=1 ORDER BY id", (kind,))


def reason_category_selectbox(reason_type, label, key):
    df=active_reason_categories(reason_type)
    if df.empty:
        st.warning("Chưa có nhóm nguyên nhân đang hoạt động. Admin/Lãnh đạo phòng cần tạo nhóm trong Quản trị hệ thống → Nhóm nguyên nhân trước khi thực hiện thao tác này.")
        st.selectbox(label,[0],format_func=lambda _x:"— Chưa có nhóm nguyên nhân —",disabled=True,key=key)
        return 0
    names={int(r.id):str(r["name"]) for _,r in df.iterrows()}
    options=[0]+list(names.keys())
    return int(st.selectbox(label,options,index=0,key=key,format_func=lambda x:"— Chọn nhóm nguyên nhân —" if int(x)==0 else names[int(x)]))


def _reasoned_task_transition(task_id, actor_user_id, event_type, reason_category_id, reason_detail, update_sql, update_params, action, action_prefix):
    kind=str(event_type or "").upper().strip()
    detail=str(reason_detail or "").strip()
    if kind not in {"RETURN","CANCEL"}:
        raise ValueError("Loại nguyên nhân không hợp lệ.")
    if not detail:
        raise ValueError("Bắt buộc nhập lý do chi tiết.")
    with get_conn() as c:
        cat=c.execute("SELECT id,name FROM reason_categories WHERE id=? AND reason_type=? AND active=1",(int(reason_category_id),kind)).fetchone()
        if not cat:
            raise ValueError("Nhóm nguyên nhân không còn hoạt động. Vui lòng chọn lại.")
        cur=c.execute(update_sql,update_params)
        if cur.rowcount!=1:
            raise ValueError("Trạng thái hồ sơ đã thay đổi. Vui lòng tải lại và thử lại.")
        ts=now_str()
        cat_name=str(cat["name"])
        c.execute("""INSERT INTO task_reason_events(task_id,actor_user_id,event_type,reason_category_id,reason_category_name,reason_detail,created_at)
                     VALUES(?,?,?,?,?,?,?)""",(int(task_id),int(actor_user_id),kind,int(reason_category_id),cat_name,detail,ts))
        full_detail=f"{action_prefix}; nhóm nguyên nhân={cat_name}; lý do={detail}"
        c.execute("INSERT INTO task_actions(task_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",(int(task_id),int(actor_user_id),str(action),full_detail,ts))
        c.execute("INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) VALUES(?,?,?,?,?,?)",(int(actor_user_id),str(action),"task",str(task_id),full_detail,ts))
        c.commit()
    LOGGER.info("REASON_WORKFLOW action=%s task_id=%s actor=%s category=%s",action,task_id,actor_user_id,cat_name)
    return cat_name


def _render_reason_category_manager(u):
    st.subheader("Nhóm nguyên nhân trả lại / hủy")
    st.caption("Tên nhóm nguyên nhân được dùng làm danh mục chuẩn. Khi CBHT trả lại hoặc CBQLKH hủy hồ sơ, người thao tác vẫn phải nhập thêm lý do chi tiết.")

    def _one(kind, title, create_key, edit_key):
        st.markdown(f"#### {title}")
        df=qdf("SELECT id,name,active,created_at,updated_at FROM reason_categories WHERE reason_type=? ORDER BY id",(kind,))
        if df.empty:
            st.info("Chưa có nhóm nguyên nhân.")
        else:
            show=df.copy()
            show["active"]=show["active"].map({1:"Đang sử dụng",0:"Đã khóa"}).fillna(show["active"])
            st.dataframe(show.rename(columns={"id":"ID","name":"Tên nhóm nguyên nhân","active":"Trạng thái","created_at":"Ngày tạo","updated_at":"Cập nhật"}),use_container_width=True,hide_index=True)
        with st.form(create_key):
            name=st.text_input("Tên nhóm nguyên nhân mới",key=f"{create_key}_name")
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
            xid=st.selectbox("Chọn nhóm nguyên nhân để sửa",df.id.astype(int).tolist(),key=f"{edit_key}_select",format_func=lambda x:str(df[df.id.astype(int)==int(x)].iloc[0]["name"]))
            row=df[df.id.astype(int)==int(xid)].iloc[0]
            new_name=st.text_input("Tên nhóm nguyên nhân",value=str(row["name"]),key=f"{edit_key}_name_{int(xid)}")
            active=st.checkbox("Đang sử dụng",value=bool(row["active"]),key=f"{edit_key}_active_{int(xid)}")
            if st.button("Cập nhật nhóm nguyên nhân",key=f"{edit_key}_save_{int(xid)}"):
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

    tab_return,tab_cancel=st.tabs(["↩️ Trả lại","🗑️ Hủy hồ sơ"])
    with tab_return:
        _one("RETURN","Nhóm nguyên nhân trả lại","reason_return_create","reason_return_edit")
    with tab_cancel:
        _one("CANCEL","Nhóm nguyên nhân hủy","reason_cancel_create","reason_cancel_edit")


'''
    source = _replace_once(source, old, helpers + old, "reason helper insertion")

    # --- 3. CBHT return before acceptance: group + detail mandatory ---
    old = '''                return_reason = st.text_input("Lý do trả lại QLKH (chỉ nhập khi cần trả hồ sơ)", key=f"return_pending_reason_{tid}")\n'''
    new = '''                return_group_id = reason_category_selectbox("RETURN","Nhóm nguyên nhân trả lại *",key=f"return_pending_group_{tid}")\n                return_reason = st.text_input("Lý do trả lại chi tiết *", key=f"return_pending_reason_{tid}")\n'''
    source = _replace_once(source, old, new, "CBHT pending return inputs")

    old = '''                if ac2.button("↩️ Trả lại QLKH",use_container_width=True,key=f"return_pending_btn_{tid}"):\n                    if not return_reason.strip():\n                        st.error("Bắt buộc nhập lý do trả lại QLKH.")\n                    else:\n                        ts=now_str(); execute("UPDATE tasks SET status='RETURNED_TO_QLKH',returned_to_qlkh_at=?,updated_at=? WHERE id=? AND support_user_id=? AND status='PENDING_ACCEPTANCE'",(ts,ts,tid,u["id"])); log_action(tid,u["id"],"RETURN_TO_QLKH",f"Trả lại trước khi tiếp nhận lúc {fmt_dt(ts)}; lý do={return_reason.strip()}"); st.success("Đã trả hồ sơ về Cán bộ QLKH. Mốc giao ban đầu vẫn được giữ nguyên."); st.rerun()\n'''
    new = '''                if ac2.button("↩️ Trả lại QLKH",use_container_width=True,key=f"return_pending_btn_{tid}"):\n                    if not return_group_id:\n                        st.error("Bắt buộc chọn Nhóm nguyên nhân trả lại.")\n                    elif not return_reason.strip():\n                        st.error("Bắt buộc nhập Lý do trả lại chi tiết.")\n                    else:\n                        try:\n                            ts=now_str(); _reasoned_task_transition(tid,u["id"],"RETURN",return_group_id,return_reason,"UPDATE tasks SET status='RETURNED_TO_QLKH',returned_to_qlkh_at=?,updated_at=? WHERE id=? AND support_user_id=? AND status='PENDING_ACCEPTANCE'",(ts,ts,tid,u["id"]),"RETURN_TO_QLKH",f"Trả lại trước khi tiếp nhận lúc {fmt_dt(ts)}"); st.success("Đã trả hồ sơ về Cán bộ QLKH. Mốc giao ban đầu vẫn được giữ nguyên."); st.rerun()\n                        except ValueError as exc:\n                            st.error(str(exc))\n'''
    source = _replace_once(source, old, new, "CBHT pending return action")

    # --- 4. CBHT return while working ---
    old = '''                return_reason = st.text_input("Lý do trả lại QLKH (nếu chưa thể xử lý xong)", key=f"return_work_reason_{tid}_{int(row.current_round)}")\n'''
    new = '''                return_group_id = reason_category_selectbox("RETURN","Nhóm nguyên nhân trả lại *",key=f"return_work_group_{tid}_{int(row.current_round)}")\n                return_reason = st.text_input("Lý do trả lại chi tiết *", key=f"return_work_reason_{tid}_{int(row.current_round)}")\n'''
    source = _replace_once(source, old, new, "CBHT work return inputs")

    old = '''                if fc2.button("↩️ Trả lại QLKH",use_container_width=True,key=f"return_work_btn_{tid}_{int(row.current_round)}"):\n                    if not return_reason.strip():\n                        st.error("Bắt buộc nhập lý do trả lại QLKH.")\n                    else:\n                        ts=now_str(); execute("""UPDATE tasks SET status='RETURNED_TO_QLKH',returned_to_qlkh_at=?,accepted_at=NULL,updated_at=?\n                                                   WHERE id=? AND support_user_id=? AND status IN ('OPEN','REWORK') AND end_time IS NULL""",(ts,ts,tid,u["id"])); log_action(tid,u["id"],"RETURN_TO_QLKH",f"Trả lại trong khi đang xử lý lúc {fmt_dt(ts)}; lý do={return_reason.strip()}; giữ nguyên mốc giao và mốc bắt đầu đầu tiên"); st.success("Đã trả hồ sơ về QLKH. Mốc giao/tiếp nhận lần đầu và thời gian đã trôi qua được giữ nguyên."); st.rerun()\n'''
    new = '''                if fc2.button("↩️ Trả lại QLKH",use_container_width=True,key=f"return_work_btn_{tid}_{int(row.current_round)}"):\n                    if not return_group_id:\n                        st.error("Bắt buộc chọn Nhóm nguyên nhân trả lại.")\n                    elif not return_reason.strip():\n                        st.error("Bắt buộc nhập Lý do trả lại chi tiết.")\n                    else:\n                        try:\n                            ts=now_str(); _reasoned_task_transition(tid,u["id"],"RETURN",return_group_id,return_reason,"""UPDATE tasks SET status='RETURNED_TO_QLKH',returned_to_qlkh_at=?,accepted_at=NULL,updated_at=?\n                                                   WHERE id=? AND support_user_id=? AND status IN ('OPEN','REWORK') AND end_time IS NULL""",(ts,ts,tid,u["id"]),"RETURN_TO_QLKH",f"Trả lại trong khi đang xử lý lúc {fmt_dt(ts)}; giữ nguyên mốc giao và mốc bắt đầu đầu tiên"); st.success("Đã trả hồ sơ về QLKH. Mốc giao/tiếp nhận lần đầu và thời gian đã trôi qua được giữ nguyên."); st.rerun()\n                        except ValueError as exc:\n                            st.error(str(exc))\n'''
    source = _replace_once(source, old, new, "CBHT work return action")

    # --- 5. QLKH cancel before acceptance ---
    old = '''                delete_reason=st.text_input("Lý do xóa/hủy hồ sơ chưa tiếp nhận",key=f"{key_prefix}_cancel_reason_{tid}")\n'''
    new = '''                cancel_group_id=reason_category_selectbox("CANCEL","Nhóm nguyên nhân hủy *",key=f"{key_prefix}_cancel_group_{tid}")\n                delete_reason=st.text_input("Lý do hủy chi tiết *",key=f"{key_prefix}_cancel_reason_{tid}")\n'''
    source = _replace_once(source, old, new, "QLKH pending cancel inputs")

    old = '''                if c2.button("🗑️ Xóa công việc",use_container_width=True,key=f"{key_prefix}_cancel_{tid}"):\n                    if first_accept is not None:\n                        st.error("Hồ sơ đã từng được CBHT tiếp nhận nên không được xóa. Có thể tiếp tục điều phối/giao lại nhưng mốc thời gian gốc luôn được giữ.")\n                    elif not delete_reason.strip():\n                        st.error("Bắt buộc nhập lý do xóa/hủy để lưu dấu vết audit.")\n                    else:\n                        ts=now_str(); execute("UPDATE tasks SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=? AND qlkh_user_id=? AND status='PENDING_ACCEPTANCE' AND first_accepted_at IS NULL",(ts,ts,tid,u["id"])); log_action(tid,u["id"],"QLKH_CANCEL",f"QLKH xóa/hủy hồ sơ chưa tiếp nhận lúc {fmt_dt(ts)}; lý do={delete_reason.strip()}; giữ bản ghi để thống kê/audit"); st.success("Đã hủy hồ sơ. Bản ghi và mốc thời gian vẫn được giữ để thống kê/audit."); st.rerun()\n'''
    new = '''                if c2.button("🗑️ Xóa công việc",use_container_width=True,key=f"{key_prefix}_cancel_{tid}"):\n                    if first_accept is not None:\n                        st.error("Hồ sơ đã từng được CBHT tiếp nhận nên không được xóa. Có thể tiếp tục điều phối/giao lại nhưng mốc thời gian gốc luôn được giữ.")\n                    elif not cancel_group_id:\n                        st.error("Bắt buộc chọn Nhóm nguyên nhân hủy.")\n                    elif not delete_reason.strip():\n                        st.error("Bắt buộc nhập Lý do hủy chi tiết.")\n                    else:\n                        try:\n                            ts=now_str(); _reasoned_task_transition(tid,u["id"],"CANCEL",cancel_group_id,delete_reason,"UPDATE tasks SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=? AND qlkh_user_id=? AND status='PENDING_ACCEPTANCE' AND first_accepted_at IS NULL",(ts,ts,tid,u["id"]),"QLKH_CANCEL",f"QLKH hủy hồ sơ chưa tiếp nhận lúc {fmt_dt(ts)}; giữ bản ghi để thống kê/audit"); st.success("Đã hủy hồ sơ. Bản ghi và mốc thời gian vẫn được giữ để thống kê/audit."); st.rerun()\n                        except ValueError as exc:\n                            st.error(str(exc))\n'''
    source = _replace_once(source, old, new, "QLKH pending cancel action")

    # --- 6. QLKH cancel returned task ---
    old = '''                delete_reason=st.text_input("Lý do xóa/hủy hồ sơ CBHT đã trả lại",key=f"{key_prefix}_cancel_returned_reason_{tid}")\n'''
    new = '''                cancel_group_id=reason_category_selectbox("CANCEL","Nhóm nguyên nhân hủy *",key=f"{key_prefix}_cancel_returned_group_{tid}")\n                delete_reason=st.text_input("Lý do hủy chi tiết *",key=f"{key_prefix}_cancel_returned_reason_{tid}")\n'''
    source = _replace_once(source, old, new, "QLKH returned cancel inputs")

    old = '''                if st.button("🗑️ Xóa / hủy công việc đã trả lại",use_container_width=True,key=f"{key_prefix}_cancel_returned_{tid}"):\n                    if not delete_reason.strip():\n                        st.error("Bắt buộc nhập lý do xóa/hủy để lưu dấu vết audit.")\n                    else:\n                        ts=now_str()\n                        execute("UPDATE tasks SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=? AND qlkh_user_id=? AND status='RETURNED_TO_QLKH'",(ts,ts,tid,u["id"]))\n                        prior_accept = fmt_dt(rsel.first_accepted_at) if first_accept is not None else "chưa từng tiếp nhận"\n                        log_action(tid,u["id"],"QLKH_CANCEL",f"QLKH xóa/hủy hồ sơ sau khi CBHT trả lại lúc {fmt_dt(ts)}; lý do={delete_reason.strip()}; tiếp nhận lần đầu={prior_accept}; giữ nguyên toàn bộ mốc thời gian và lịch sử để thống kê/audit")\n                        st.success("Đã hủy hồ sơ CBHT trả lại. Bản ghi, mốc giao/tiếp nhận/xử lý và lịch sử audit vẫn được giữ nguyên.")\n                        st.rerun()\n'''
    new = '''                if st.button("🗑️ Xóa / hủy công việc đã trả lại",use_container_width=True,key=f"{key_prefix}_cancel_returned_{tid}"):\n                    if not cancel_group_id:\n                        st.error("Bắt buộc chọn Nhóm nguyên nhân hủy.")\n                    elif not delete_reason.strip():\n                        st.error("Bắt buộc nhập Lý do hủy chi tiết.")\n                    else:\n                        try:\n                            ts=now_str(); prior_accept = fmt_dt(rsel.first_accepted_at) if first_accept is not None else "chưa từng tiếp nhận"\n                            _reasoned_task_transition(tid,u["id"],"CANCEL",cancel_group_id,delete_reason,"UPDATE tasks SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=? AND qlkh_user_id=? AND status='RETURNED_TO_QLKH'",(ts,ts,tid,u["id"]),"QLKH_CANCEL",f"QLKH hủy hồ sơ sau khi CBHT trả lại lúc {fmt_dt(ts)}; tiếp nhận lần đầu={prior_accept}; giữ nguyên toàn bộ mốc thời gian và lịch sử để thống kê/audit")\n                            st.success("Đã hủy hồ sơ CBHT trả lại. Bản ghi, mốc giao/tiếp nhận/xử lý và lịch sử audit vẫn được giữ nguyên."); st.rerun()\n                        except ValueError as exc:\n                            st.error(str(exc))\n'''
    source = _replace_once(source, old, new, "QLKH returned cancel action")

    # --- 7. Leader may enter Quản trị, but non-admin leaders see ONLY reason master data. ---
    old = '''    if u["is_admin"]: options.append(("admin", "⚙️  Quản trị"))\n'''
    new = '''    if u["is_admin"] or u["role"] == "Lãnh đạo phòng": options.append(("admin", "⚙️  Quản trị"))\n'''
    source = _replace_once(source, old, new, "leader admin navigation")

    old = '''def admin_page(u):\n    if not u["is_admin"]:\n        st.error("Bạn không có quyền quản trị.")\n        return\n    page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF, loại công việc, audit và sao lưu dữ liệu.")\n    _admin_options=[("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF"),("types","🧩","Loại công việc"),("audit","🧾","Audit"),("backup","💾","Sao lưu")]\n    _admin_values=[v for v,_,_ in _admin_options]\n    _admin_current=st.session_state.get("admin_view","users")\n    if _admin_current not in _admin_values: _admin_current="users"; st.session_state["admin_view"]="users"\n'''
    new = '''def admin_page(u):\n    _reason_only = bool(u["role"] == "Lãnh đạo phòng" and not u["is_admin"])\n    if not u["is_admin"] and u["role"] != "Lãnh đạo phòng":\n        st.error("Bạn không có quyền quản trị.")\n        return\n    page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF, loại công việc, nhóm nguyên nhân, audit và sao lưu dữ liệu." if u["is_admin"] else "Quản lý danh mục nhóm nguyên nhân trả lại / hủy.")\n    _admin_options=[("reasons","🧩","Nhóm nguyên nhân")] if _reason_only else [("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF"),("types","🧩","Loại công việc"),("reasons","🧩","Nhóm nguyên nhân"),("audit","🧾","Audit"),("backup","💾","Sao lưu")]\n    _admin_values=[v for v,_,_ in _admin_options]\n    _admin_default="reasons" if _reason_only else "users"\n    _admin_current=st.session_state.get("admin_view",_admin_default)\n    if _admin_current not in _admin_values: _admin_current=_admin_default; st.session_state["admin_view"]=_admin_default\n'''
    source = _replace_once(source, old, new, "admin reason navigation")

    old = '''    if admin_view == "audit":\n'''
    new = '''    if admin_view == "reasons":\n        _render_reason_category_manager(u)\n\n    if admin_view == "audit":\n'''
    source = _replace_once(source, old, new, "admin reason content")

    # Build-time safety assertions. Reason manager must not be injected into leader_page.
    leader_start=source.find("def leader_page(u):")
    excel_start=source.find("def make_excel_report",leader_start)
    if leader_start<0 or excel_start<0:
        raise RuntimeError("Cannot verify leader page boundaries")
    leader_block=source[leader_start:excel_start]
    if "Nhóm nguyên nhân" in leader_block or "_render_reason_category_manager" in leader_block:
        raise RuntimeError("Reason-category UI leaked into Leader work-management page")
    if source.count('        _render_reason_category_manager(u)') != 1:
        raise RuntimeError("Reason-category manager must render exactly once")
    if source.count('reason_category_selectbox("RETURN"') != 2:
        raise RuntimeError("Expected exactly two CBHT return reason selectors")
    if source.count('reason_category_selectbox("CANCEL"') != 2:
        raise RuntimeError("Expected exactly two QLKH cancel reason selectors")
    compile(source, "<khdn-v238-reason-preview>", "exec")
    return source
