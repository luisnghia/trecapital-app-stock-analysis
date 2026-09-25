"""Weekly Plan UI runtime.

This keeps widget-key mutations outside the render pass in which the widget is
instantiated. Streamlit forbids writing ``session_state.wp_text`` after the
``text_area(key='wp_text')`` has been created, so successful saves request a
reset and the reset is applied at the very start of the next rerun.
"""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta

from khdn_apps import weekly_plan as core

VERSION = "1.0.1"
_CLEAR_TEXT_FLAG = "_wp_clear_text_next_run"


def apply_deferred_widget_resets(session_state) -> None:
    """Apply widget state changes before any Weekly Plan widget is created."""
    if session_state.pop(_CLEAR_TEXT_FLAG, False):
        session_state["wp_text"] = ""


def request_quick_input_reset(session_state) -> None:
    """Schedule the quick-entry text area to be cleared on the next rerun."""
    session_state[_CLEAR_TEXT_FLAG] = True
    session_state.pop("wp_preview", None)
    session_state.pop("wp_preview_week", None)


def render_page(st, u, get_conn, page_title=None, logger=None):
    # IMPORTANT: this must run before text_area(key="wp_text") below.
    apply_deferred_widget_resets(st.session_state)

    core.ensure_schema(get_conn, logger)
    uid = int(u["id"])
    if page_title:
        page_title(
            "Kế hoạch công việc",
            "Nhập nhanh như ghi sổ tay · tự chuẩn hóa · theo dõi theo tuần",
        )
    else:
        st.title("📅 Kế hoạch công việc")
    st.caption(f"Weekly Plan v{VERSION} · Mỗi dòng một việc, không cần form dài.")

    off = st.session_state.setdefault("wp_offset", 0)
    n1, n2, n3, n4 = st.columns([1, 1.3, 1, 4])
    if n1.button("← Tuần trước", key="wpp", use_container_width=True):
        st.session_state.wp_offset -= 1
        st.rerun()
    if n2.button("Tuần này", key="wpn", use_container_width=True):
        st.session_state.wp_offset = 0
        st.rerun()
    if n3.button("Tuần sau →", key="wpq", use_container_width=True):
        st.session_state.wp_offset += 1
        st.rerun()

    ws = core.week_start() + timedelta(days=7 * int(st.session_state.wp_offset))
    n4.markdown(f"**{ws:%d/%m} – {(ws + timedelta(days=6)):%d/%m/%Y}**")

    with get_conn() as c:
        cs = core.customers(c, uid)
        items = core.load_items(c, uid, ws)

    active = [x for x in items if x.get("status") != "CANCELLED"]
    a, b, c, d = st.columns(4)
    a.metric("Tổng việc", len(active))
    b.metric("Kế hoạch", sum(x["status"] == "PLANNED" for x in active))
    c.metric("Đang làm", sum(x["status"] == "IN_PROGRESS" for x in active))
    d.metric("Hoàn thành", sum(x["status"] == "DONE" for x in active))

    views = ["📅 Tuần này", "☀️ Hôm nay", "✨ Gợi ý"]
    if str(u.get("role") or "") == "Lãnh đạo phòng" or bool(u.get("is_admin")):
        views.append("👥 Kế hoạch phòng")
    view = st.radio(
        "Chế độ xem",
        views,
        horizontal=True,
        label_visibility="collapsed",
        key="wp_view",
    )
    st.divider()

    if view == "📅 Tuần này":
        with st.expander("⚡ Nhập nhanh kế hoạch", expanded=not items):
            st.caption(
                "Mỗi dòng một việc. Ví dụ: T2 gặp Công ty A - tiền gửi; "
                "T3 làm hạn mức Công ty B; T5 9h họp phòng."
            )
            text = st.text_area(
                "Kế hoạch",
                key="wp_text",
                height=145,
                placeholder=(
                    "T2 gặp Công ty ABC - tiếp thị tiền gửi\n"
                    "T3 làm hạn mức Công ty DEF\n"
                    "T4 trình hồ sơ dự án Công ty XYZ\n"
                    "T5 9h họp phòng"
                ),
                label_visibility="collapsed",
            )
            q1, q2 = st.columns(2)
            if q1.button("✨ Phân tích", key="wpa", use_container_width=True):
                st.session_state.wp_preview = core.parse_text(text, ws, cs)
                st.session_state.wp_preview_week = ws.isoformat()

            if q2.button(
                "⚡ Lưu ngay",
                key="wpf",
                use_container_width=True,
                type="primary",
            ):
                parsed = core.parse_text(text, ws, cs)
                bad = [x for x in parsed if x.get("error")]
                if not parsed:
                    st.warning("Chưa có nội dung kế hoạch.")
                elif bad:
                    st.session_state.wp_preview = parsed
                    st.session_state.wp_preview_week = ws.isoformat()
                    st.warning("Có dòng chưa nhận diện được ngày. Hãy kiểm tra bảng dưới.")
                else:
                    n, _ = core.save_items(get_conn, uid, ws, parsed, logger)
                    # Do not write wp_text here: the widget already exists this run.
                    request_quick_input_reset(st.session_state)
                    st.toast(f"Đã thêm {n} công việc.", icon="✅")
                    st.rerun()

            pv = st.session_state.get("wp_preview")
            if pv and st.session_state.get("wp_preview_week") == ws.isoformat():
                core.preview(st, pv)
                if any(not x.get("error") for x in pv) and st.button(
                    "✓ Lưu kế hoạch",
                    key="wpv",
                    type="primary",
                    use_container_width=True,
                ):
                    n, _ = core.save_items(get_conn, uid, ws, pv, logger)
                    # Same deferred reset for the analyze -> save workflow.
                    request_quick_input_reset(st.session_state)
                    st.toast(f"Đã lưu {n} công việc.", icon="✅")
                    st.rerun()

        x1, x2 = st.columns([1, 2])
        if x1.button(
            "📋 Sao chép tuần trước",
            key=f"wpcopy{ws}",
            use_container_width=True,
        ):
            n = core.copy_prev(get_conn, uid, ws, logger)
            if n:
                st.toast(f"Đã sao chép {n} công việc.", icon="✅")
                st.rerun()
            else:
                st.info("Tuần trước chưa có công việc mới để sao chép.")
        x2.caption("Dời lịch bằng nút ⋯ trên từng công việc; không cần mở form dài.")

        by = {}
        for x in active:
            by.setdefault(str(x["work_date"])[:10], []).append(x)

        for col, dd in zip(
            st.columns(5, gap="small"),
            [ws + timedelta(days=i) for i in range(5)],
        ):
            with col:
                st.markdown(f"### {core.day_label(dd)}")
                day = by.get(dd.isoformat(), [])
                if not day:
                    st.caption("Chưa có công việc")
                for x in day:
                    with st.container(border=True):
                        core.card(st, x, ws, get_conn, uid, logger)
                if st.button("＋ Thêm", key=f"wpadd{dd}", use_container_width=True):
                    st.session_state.wp_add = dd.isoformat()
                    st.rerun()
                if st.session_state.get("wp_add") == dd.isoformat():
                    txt = st.text_input(
                        "Việc cần làm",
                        key=f"wpaddtxt{dd}",
                        placeholder="Gặp Công ty A - tiền gửi",
                    )
                    y1, y2 = st.columns(2)
                    if y1.button(
                        "Lưu",
                        key=f"wpaddsave{dd}",
                        type="primary",
                        use_container_width=True,
                    ):
                        x = core.parse_line(txt, ws, cs, dd)
                        if x:
                            core.save_items(get_conn, uid, ws, [x], logger)
                            st.session_state.pop("wp_add", None)
                            st.rerun()
                    if y2.button(
                        "Đóng",
                        key=f"wpaddclose{dd}",
                        use_container_width=True,
                    ):
                        st.session_state.pop("wp_add", None)
                        st.rerun()

    elif view == "☀️ Hôm nay":
        today = date.today().isoformat()
        data = [x for x in active if str(x["work_date"])[:10] == today]
        st.subheader(f"☀️ Hôm nay · {date.today():%d/%m/%Y}")
        if not data:
            st.info("Hôm nay chưa có công việc trong kế hoạch.")
        for x in data:
            with st.container(border=True):
                core.card(st, x, ws, get_conn, uid, logger)

    elif view == "✨ Gợi ý":
        with get_conn() as c:
            tasks = core.open_tasks(c, uid)
        st.subheader("✨ Gợi ý từ hồ sơ đang xử lý")
        st.caption("Chỉ dùng dữ liệu đã có trong KHDN Ops; không tạo lại hồ sơ tác nghiệp.")
        if not tasks:
            st.info("Không có hồ sơ đang xử lý chưa được đưa vào kế hoạch.")
        days = [ws + timedelta(days=i) for i in range(5)]
        for t in tasks:
            with st.container(border=True):
                st.markdown(
                    f"**📑 {html.escape(str(t.get('task_type') or 'Hồ sơ'))} · "
                    f"{html.escape(str(t.get('customer_name') or ''))}**"
                )
                due = str(t.get("due_time") or "")[:16]
                if due:
                    st.caption(f"Hạn xử lý: {due}")
                idx = 0
                try:
                    dd = datetime.fromisoformat(str(t.get("due_time"))).date()
                    idx = dd.weekday() if ws <= dd < ws + timedelta(days=5) else 0
                except Exception:
                    pass
                target = st.selectbox(
                    "Đưa vào ngày",
                    days,
                    index=idx,
                    format_func=core.day_label,
                    key=f"wpsug{t['id']}",
                )
                if st.button(
                    "＋ Thêm vào kế hoạch",
                    key=f"wpsugb{t['id']}",
                    use_container_width=True,
                ):
                    core.add_task(get_conn, uid, ws, t, target, logger)
                    st.rerun()

    else:
        with get_conn() as c:
            rows = c.execute(
                """SELECT u.full_name,
                SUM(CASE WHEN w.status<>'CANCELLED' THEN 1 ELSE 0 END),
                SUM(CASE WHEN w.status='DONE' THEN 1 ELSE 0 END),
                SUM(CASE WHEN w.category IN ('Khách hàng','Chăm sóc khách hàng') AND w.status<>'CANCELLED' THEN 1 ELSE 0 END),
                SUM(CASE WHEN w.category='Tín dụng' AND w.status<>'CANCELLED' THEN 1 ELSE 0 END),
                SUM(CASE WHEN w.category='Hồ sơ / Dự án' AND w.status<>'CANCELLED' THEN 1 ELSE 0 END),
                SUM(CASE WHEN w.category='Nội bộ' AND w.status<>'CANCELLED' THEN 1 ELSE 0 END)
                FROM users u
                LEFT JOIN weekly_plan_items w ON w.user_id=u.id
                  AND w.work_date>=? AND w.work_date<?
                WHERE u.active=1
                GROUP BY u.id,u.full_name
                ORDER BY u.full_name""",
                (ws.isoformat(), (ws + timedelta(days=7)).isoformat()),
            ).fetchall()
        out = []
        for r in rows:
            total = int(r[1] or 0)
            done = int(r[2] or 0)
            out.append([
                r[0],
                total,
                int(r[3] or 0),
                int(r[4] or 0),
                int(r[5] or 0),
                int(r[6] or 0),
                done,
                f"{done / total * 100:.1f}%" if total else "—",
            ])
        st.subheader("👥 Kế hoạch phòng")
        core.table(
            st,
            ["Cán bộ", "Tổng", "Khách hàng", "Tín dụng", "Dự án", "Nội bộ", "Hoàn thành", "Tỷ lệ"],
            out,
        )
