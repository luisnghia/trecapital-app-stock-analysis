"""Weekly Plan V3 UI/reporting layer for KHDN Ops.

Completes draft editing/copy-last-week, room 8-week trends and personal PDF export.
No Ban Giám đốc role or screen is exposed.
"""
from __future__ import annotations

import html
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v2 as v2


def _copy_candidates(get_conn: Callable, user_id: int, year: int, week: int, plan_id: int):
    py, pw, _ = v2._previous_iso(year, week)
    prev = wp._get_plan(get_conn, int(user_id), py, pw)
    if not prev:
        return pd.DataFrame()
    return wp._qdf(get_conn, """SELECT t.*,f.code focus_code,f.name focus_name
        FROM weekly_tasks t LEFT JOIN weekly_focus_categories f ON f.id=t.focus_category_id
        WHERE t.plan_id=? AND t.status IN ('COMPLETED','CANCELLED')
        AND NOT EXISTS(SELECT 1 FROM weekly_tasks n WHERE n.plan_id=? AND n.source_task_id=t.id)
        ORDER BY t.id""", (int(prev["id"]), int(plan_id)))


def _copy_last_week_panel(get_conn: Callable, u, plan):
    cand = _copy_candidates(get_conn, int(u["id"]), int(plan["iso_year"]), int(plan["iso_week"]), int(plan["id"]))
    if cand.empty:
        return
    with st.expander(f"📋 Sao chép việc lặp lại từ tuần trước ({len(cand)})", expanded=False):
        st.caption("Dùng cho công việc định kỳ đã hoàn thành/hủy ở tuần trước. Công việc chưa xong sử dụng mục Chuyển tiếp.")
        for _, r in cand.iterrows():
            wp._render_task_card(r)
            if st.button("Sao chép vào tuần này", key=f"weekly_copy_{int(r['id'])}", use_container_width=True):
                current = wp._tasks_df(get_conn, int(plan["id"]))
                planned = current[pd.to_numeric(current["is_emergent"], errors="coerce").fillna(0).eq(0)] if not current.empty else current
                if len(planned) >= 7:
                    st.error("Kế hoạch đã đủ 7 công việc.")
                    continue
                total_hours = float(pd.to_numeric(planned["planned_hours"], errors="coerce").fillna(0).sum()) if not planned.empty else 0.0
                if total_hours + float(r.get("planned_hours") or 0) > 45:
                    st.error("Sao chép việc này sẽ làm tổng giờ dự kiến vượt 45 giờ.")
                    continue
                _, _, monday, _ = wp._iso_week()
                try:
                    old_due = pd.to_datetime(r.get("due_date")).date()
                    day_offset = min(6, max(0, old_due.weekday()))
                    due = monday + timedelta(days=day_offset)
                except Exception:
                    due = monday + timedelta(days=4)
                new_id = wp._execute(get_conn, """INSERT INTO weekly_tasks(
                    plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,due_date,
                    planned_hours,actual_hours,status,is_emergent,defer_count,source_task_id,defer_reason,original_due_date,
                    classification_locked,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,0,'NOT_STARTED',0,0,?,NULL,?,0,?,?)""",
                    (int(plan["id"]), str(r.get("title") or ""), str(r.get("expected_result") or ""),
                     int(r["focus_category_id"]) if pd.notna(r.get("focus_category_id")) else None,
                     int(r.get("is_urgent") or 0), int(r.get("has_kpi_or_risk") or 0), str(r.get("quadrant") or "Q4"),
                     due.isoformat(), float(r.get("planned_hours") or 0), int(r["id"]), due.isoformat(), wp._now(), wp._now()))
                wp._log(get_conn, int(u["id"]), "COPY_PREVIOUS_TASK", "weekly_task", new_id, f"source_task_id={int(r['id'])}")
                st.rerun()


def _draft_editor(get_conn: Callable, u, plan):
    tasks = wp._tasks_df(get_conn, int(plan["id"]))
    if tasks.empty:
        return
    with st.expander("✏️ Sửa công việc trong kế hoạch", expanded=False):
        task_id = st.selectbox("Chọn công việc", tasks["id"].astype(int).tolist(),
            format_func=lambda x: f"{tasks[tasks['id'].eq(int(x))].iloc[0]['quadrant']} · {tasks[tasks['id'].eq(int(x))].iloc[0]['title']}",
            key="weekly_draft_edit_task")
        row = tasks[tasks["id"].eq(int(task_id))].iloc[0].to_dict()
        focus = wp._focus_df(get_conn, int(plan["iso_year"]), active_only=True)
        opts = [0] + (focus["id"].astype(int).tolist() if not focus.empty else [])
        current_focus = int(row["focus_category_id"]) if pd.notna(row.get("focus_category_id")) else 0
        idx = opts.index(current_focus) if current_focus in opts else 0
        def ff(x):
            if x == 0: return "— Không thuộc mục trọng tâm nào —"
            r = focus[focus["id"].eq(int(x))].iloc[0]
            return f"{r['code']} — {r['name']}"
        title = st.text_input("Tên công việc *", value=str(row.get("title") or ""), max_chars=200, key="weekly_edit_title")
        focus_id = st.selectbox("Danh mục trọng tâm Q2", opts, index=idx, format_func=ff, key="weekly_edit_focus")
        urgent = bool(row.get("is_urgent") or 0); has_kpi = bool(row.get("has_kpi_or_risk") or 0)
        if not focus_id:
            urgent = st.checkbox("Có hạn trong 7 ngày tới?", value=urgent, key="weekly_edit_urgent")
            has_kpi = st.checkbox("Gắn chỉ tiêu hoặc rủi ro trọng yếu?", value=has_kpi if urgent else False, disabled=not urgent, key="weekly_edit_kpi")
        q = wp._classification(int(focus_id) if focus_id else None, urgent, has_kpi)
        st.info(f"Phân loại sau khi lưu: **{q} – {wp.QUADRANT_META[q][0]}**")
        try: due0 = pd.to_datetime(row.get("due_date")).date()
        except Exception: due0 = date.today()
        c1, c2 = st.columns(2)
        due = c1.date_input("Hạn hoàn thành *", value=due0, key="weekly_edit_due")
        hours = c2.number_input("Giờ dự kiến *", min_value=0.5, max_value=45.0, value=float(row.get("planned_hours") or 0.5), step=0.5, key="weekly_edit_hours")
        expected = st.text_area("Kết quả đầu ra dự kiến *", value=str(row.get("expected_result") or ""), max_chars=300, key="weekly_edit_expected")
        if st.button("Lưu thay đổi", type="primary", use_container_width=True, key="weekly_edit_save"):
            if not title.strip() or not expected.strip():
                st.error("Tên công việc và kết quả đầu ra là bắt buộc.")
            else:
                other_hours = float(pd.to_numeric(tasks.loc[tasks["id"].ne(int(task_id)), "planned_hours"], errors="coerce").fillna(0).sum())
                if other_hours + float(hours) > 45:
                    st.error("Tổng giờ dự kiến sau chỉnh sửa vượt 45 giờ.")
                else:
                    old_q = str(row.get("quadrant") or "")
                    wp._execute(get_conn, """UPDATE weekly_tasks SET title=?,expected_result=?,focus_category_id=?,is_urgent=?,
                        has_kpi_or_risk=?,quadrant=?,due_date=?,planned_hours=?,updated_at=? WHERE id=?""",
                        (title.strip(), expected.strip(), int(focus_id) if focus_id else None, int(urgent), int(has_kpi), q,
                         due.isoformat(), float(hours), wp._now(), int(task_id)))
                    wp._task_log(get_conn, int(task_id), int(u["id"]), "draft_edit", old_q, q, "Sửa kế hoạch tuần")
                    wp._log(get_conn, int(u["id"]), "EDIT_WEEKLY_TASK", "weekly_task", task_id, f"{old_q}->{q}")
                    st.rerun()


def _my_plan(get_conn: Callable, u):
    year, week, monday, sunday = wp._iso_week()
    plan = wp._get_or_create_plan(get_conn, int(u["id"]), year, week, monday, sunday)
    v2._sync_overdue(get_conn, int(plan["id"]))
    tasks = wp._tasks_df(get_conn, int(plan["id"]))
    wp._render_header(plan, tasks)
    v2._warnings(get_conn, u, plan, tasks)
    status = str(plan["status"])
    if status in {"DRAFT", "RETURNED"}:
        v2._carry_panel(get_conn, u, plan)
        _copy_last_week_panel(get_conn, u, plan)
        _draft_editor(get_conn, u, plan)
        wp._draft_view(get_conn, u, plan, tasks)
    elif status == "SUBMITTED":
        st.info("Kế hoạch đã nộp, đang chờ lãnh đạo phòng duyệt.")
        wp._submitted_view(get_conn, u, plan, tasks)
    elif status == "APPROVED":
        v2._approved_view(get_conn, u, plan, tasks)
    elif status in {"CLOSED", "REVIEWED"}:
        if status == "CLOSED": st.info("Đã chốt tuần; dữ liệu chỉ đọc và đang chờ lãnh đạo đánh giá.")
        wp._reviewed_view(get_conn, plan, tasks)


def _room_history(get_conn: Callable):
    since = (date.today() - timedelta(days=56)).isoformat()
    return wp._qdf(get_conn, """SELECT p.iso_year,p.iso_week,u.full_name,u.role,p.status,
        COUNT(CASE WHEN t.status<>'CANCELLED' THEN t.id END) total_tasks,
        COUNT(CASE WHEN t.status='COMPLETED' THEN t.id END) done_tasks,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' THEN t.actual_hours ELSE 0 END),0) actual_hours,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' AND t.quadrant='Q2' THEN t.actual_hours ELSE 0 END),0) q2_hours,
        r.week_score,r.grade FROM weekly_plans p JOIN users u ON u.id=p.user_id
        LEFT JOIN weekly_tasks t ON t.plan_id=p.id LEFT JOIN weekly_reviews r ON r.plan_id=p.id
        WHERE date(p.start_date)>=date(?) AND u.active=1 AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH')
        GROUP BY p.id,p.iso_year,p.iso_week,u.full_name,u.role,p.status,r.week_score,r.grade
        ORDER BY p.iso_year DESC,p.iso_week DESC,u.full_name""", (since,))


def _room_dashboard(get_conn: Callable):
    wp._room_dashboard(get_conn)
    st.divider(); st.markdown("### Xu hướng phòng · 8 tuần")
    df = _room_history(get_conn)
    if df.empty:
        st.info("Chưa đủ dữ liệu lịch sử."); return
    df["Tuần"] = df.apply(lambda r: f"{int(r['iso_week'])}/{int(r['iso_year'])}", axis=1)
    df["Hoàn thành"] = df.apply(lambda r: f"{100.0*float(r['done_tasks'] or 0)/float(r['total_tasks']):.1f}%" if float(r["total_tasks"] or 0)>0 else "0.0%", axis=1)
    df["Q2"] = df.apply(lambda r: f"{100.0*float(r['q2_hours'] or 0)/float(r['actual_hours']):.1f}%" if float(r["actual_hours"] or 0)>0 else "0.0%", axis=1)
    df["Điểm tuần"] = df["week_score"].map(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    df["Xếp loại"] = df["grade"].fillna("—")
    v2._html_table(df[["Tuần","full_name","role","Hoàn thành","Q2","Điểm tuần","Xếp loại"]].rename(columns={"full_name":"Cán bộ","role":"Vai trò"}), 520)
    scored = df[pd.to_numeric(df["week_score"], errors="coerce").notna()].copy()
    if not scored.empty:
        avg = scored.groupby(["iso_year","iso_week"], as_index=False)["week_score"].mean().sort_values(["iso_year","iso_week"])
        avg["Tuần"] = avg.apply(lambda r: f"{int(r['iso_week'])}/{int(r['iso_year'])}", axis=1)
        if len(avg) >= 2:
            st.line_chart(avg.set_index("Tuần")[["week_score"]].rename(columns={"week_score":"Điểm TB phòng"}), height=220)


def _pdf_bytes(get_conn: Callable, u):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    year, week, monday, sunday = wp._iso_week()
    plan = wp._get_plan(get_conn, int(u["id"]), year, week)
    if not plan: return b""
    tasks = wp._tasks_df(get_conn, int(plan["id"]))
    review = wp._review(get_conn, int(plan["id"])) or {}
    regular = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if not regular.exists() or not bold.exists():
        raise RuntimeError("Máy chủ chưa có font DejaVu Sans để xuất PDF tiếng Việt.")
    pdfmetrics.registerFont(TTFont("KHDN", str(regular))); pdfmetrics.registerFont(TTFont("KHDNB", str(bold)))
    out = BytesIO(); doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=14*mm, leftMargin=14*mm, topMargin=14*mm, bottomMargin=14*mm)
    styles = getSampleStyleSheet(); title = ParagraphStyle("t", parent=styles["Title"], fontName="KHDNB", fontSize=15, leading=19, alignment=TA_CENTER, textColor=colors.HexColor("#006B68")); body = ParagraphStyle("b", parent=styles["BodyText"], fontName="KHDN", fontSize=8.5, leading=11); small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9)
    story=[Paragraph("BÁO CÁO KẾ HOẠCH VÀ KẾT QUẢ TUẦN", title), Paragraph(f"{html.escape(str(u.get('full_name') or ''))} · Tuần {week}/{year} · {monday:%d/%m/%Y}–{sunday:%d/%m/%Y}", body), Spacer(1,6)]
    data=[["Q","Công việc","Hạn","Giờ KH/TT","Trạng thái","Kết quả/đầu ra"]]
    for _,r in tasks.iterrows():
        result=str(r.get("actual_result") or r.get("expected_result") or "")
        data.append([str(r.get("quadrant") or ""),Paragraph(html.escape(str(r.get("title") or "")),small),str(r.get("due_date") or "—"),f"{float(r.get('planned_hours') or 0):.1f}/{float(r.get('actual_hours') or 0):.1f}",wp.TASK_STATUS_LABELS.get(str(r.get("status")),str(r.get("status"))),Paragraph(html.escape(result),small)])
    table=Table(data,colWidths=[10*mm,52*mm,21*mm,22*mm,28*mm,49*mm],repeatRows=1)
    table.setStyle(TableStyle([("FONTNAME",(0,0),(-1,0),"KHDNB"),("FONTNAME",(0,1),(-1,-1),"KHDN"),("FONTSIZE",(0,0),(-1,-1),7.2),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#006B68")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#A8C9C6")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)])); story.append(table)
    if review:
        story += [Spacer(1,8),Paragraph("ĐÁNH GIÁ TUẦN", ParagraphStyle("h",parent=body,fontName="KHDNB",fontSize=10,textColor=colors.HexColor("#006B68")))]
        for label,key in [("Mặt được","strengths"),("Tồn tại","limitations"),("Nguyên nhân","causes"),("Đề xuất","next_actions"),("Nhận xét lãnh đạo","leader_comment")]:
            if review.get(key): story.append(Paragraph(f"<b>{label}:</b> {html.escape(str(review.get(key)))}", body))
        if review.get("week_score") is not None: story.append(Paragraph(f"<b>Điểm tuần:</b> {float(review.get('week_score') or 0):.1f} · Xếp loại {html.escape(str(review.get('grade') or '—'))}", body))
    doc.build(story); return out.getvalue()


def _export_view(get_conn: Callable, u):
    st.markdown("### Xuất báo cáo Kế hoạch tuần")
    excel = v2._excel_bytes(get_conn, int(u["id"]))
    c1,c2 = st.columns(2)
    if excel:
        c1.download_button("⬇️ Excel 8 tuần", data=excel, file_name=f"Ke_hoach_tuan_{u.get('username','can_bo')}_{date.today():%Y%m%d}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    else: c1.info("Chưa có dữ liệu Excel.")
    try: pdf = _pdf_bytes(get_conn,u)
    except Exception as exc:
        pdf=b""; c2.error(f"Chưa tạo được PDF: {exc}")
    if pdf:
        c2.download_button("⬇️ PDF tuần hiện tại", data=pdf, file_name=f"Ke_hoach_tuan_{date.today():%Y%m%d}.pdf", mime="application/pdf", use_container_width=True)


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    v2._init_v2_schema(get_conn); wp._inject_weekly_css(); v2._inject_css()
    page_title("Kế hoạch tuần", "Quản trị ưu tiên theo Q1–Q4; hệ thống tự phân loại, cán bộ không tự chọn góc phần tư.")
    v2._glossary()
    if wp._is_leader(u):
        options=[("mine","📅 Kế hoạch của tôi"),("review","✅ Duyệt & đánh giá"),("focus","🎯 Trọng tâm Q2"),("room","📊 Tổng quan phòng"),("history","📈 8 tuần"),("export","⬇️ Xuất báo cáo")]
    else:
        options=[("mine","📅 Tuần của tôi"),("history","📈 8 tuần"),("export","⬇️ Xuất báo cáo")]
    if pill_nav:
        view=pill_nav("weekly_plan_view",options,default="mine",prefix="weekly_plan_v3")
    else:
        labels=[x[1] for x in options]; values=[x[0] for x in options]; current=st.session_state.get("weekly_plan_view","mine"); idx=values.index(current) if current in values else 0
        selected=st.radio("Chế độ",labels,index=idx,horizontal=True,label_visibility="collapsed"); view=dict((label,value) for value,label in options)[selected]; st.session_state["weekly_plan_view"]=view
    if view=="mine": _my_plan(get_conn,u)
    elif view=="review" and wp._is_leader(u): v2._leader_review(get_conn,u)
    elif view=="focus" and wp._is_leader(u): v2._focus_admin(get_conn,u)
    elif view=="room" and wp._is_leader(u): _room_dashboard(get_conn)
    elif view=="history": v2._history_view(get_conn,u)
    elif view=="export": _export_view(get_conn,u)
