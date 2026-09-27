"""Small runtime corrections for weekly_priority_policy_patch."""
from __future__ import annotations

VERSION = "1.0.1"


def install(policy, logger=None):
    def inline_focus_create(st, u, get_conn, year, logger_arg=None):
        uid = int(policy._uget(u, "id"))
        with get_conn() as c:
            leaders = [dict(r) for r in c.execute(
                "SELECT id,full_name FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY full_name"
            ).fetchall()]
        leader_id = uid
        if policy._is_admin(u) and leaders:
            leader_id = int(st.selectbox(
                "Phòng/Trưởng phòng áp dụng",
                leaders,
                format_func=lambda x: x["full_name"],
                key=f"inline_focus_leader_{year}",
            )["id"])
        scope = f"LEADER:{leader_id}"
        with st.expander("＋ Bổ sung mục trọng tâm ngay tại màn hình duyệt", expanded=False):
            a, b = st.columns([1, 3])
            code = a.text_input("Mã *", key=f"inline_focus_code_{year}", placeholder="TT06")
            name = b.text_input("Tên ngắn gọn *", key=f"inline_focus_name_{year}")
            desc = st.text_area("Mô tả phạm vi (1–2 câu) *", key=f"inline_focus_desc_{year}")
            order = st.number_input("Thứ tự", min_value=1, value=6, step=1, key=f"inline_focus_order_{year}")
            if st.button("Thêm vào danh mục trọng tâm", key=f"inline_focus_save_{year}", type="primary"):
                if not code.strip() or not name.strip() or not desc.strip():
                    st.error("Vui lòng nhập đủ mã, tên và mô tả phạm vi.")
                    return
                ts = policy._now()
                try:
                    with get_conn() as c:
                        c.execute(
                            """INSERT INTO weekly_focus_categories(
                               department_key,apply_year,code,name,description,sort_order,active,
                               created_by,updated_by,created_at,updated_at)
                               VALUES(?,?,?,?,?,?,1,?,?,?,?)""",
                            (
                                scope, int(year), code.strip().upper(), name.strip(), desc.strip(),
                                int(order), uid, uid, ts, ts,
                            ),
                        )
                    st.toast("Đã bổ sung mục trọng tâm.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    policy._inline_focus_create = inline_focus_create
    policy.VERSION = "1.0.1"
    if logger:
        logger.info("WEEKLY_PRIORITY_POLICY_HOTFIX_INSTALLED version=%s", VERSION)
