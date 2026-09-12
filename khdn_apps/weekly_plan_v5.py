"""Weekly Plan V5 reporting and permission hardening for KHDN Ops.

Adds room-level Excel/PDF exports for Lãnh đạo phòng and a second server-side
access gate. The module intentionally contains no Ban Giám đốc view.
"""
from __future__ import annotations

import html
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v2 as v2
from khdn_apps import weekly_plan_v3 as v3
from khdn_apps import weekly_plan_v4 as v4


STAFF_ROLES = ("Cán bộ hỗ trợ", "Cán bộ QLKH")


def _room_export_frames(get_conn: Callable, weeks: int = 8):
    year, week, _, _ = wp._iso_week()
    current_monday = date.fromisocalendar(year, week, 1)
    since = current_monday - pd.Timedelta(days=max(0, int(weeks) - 1) * 7)

    plans = wp._qdf(get_conn, """SELECT p.*,u.full_name,u.username,u.role
        FROM weekly_plans p JOIN users u ON u.id=p.user_id
        WHERE date(p.start_date)>=date(?) AND u.active=1
          AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH')
        ORDER BY p.iso_year DESC,p.iso_week DESC,u.full_name""", (since.isoformat(),))
    if plans.empty:
        return plans, pd.DataFrame(), pd.DataFrame()

    ids = plans["id"].astype(int).tolist()
    marks = ",".join(["?"] * len(ids))
    tasks = wp._qdf(get_conn, f"""SELECT t.*,p.iso_year,p.iso_week,u.full_name,u.username,u.role,
        f.code focus_code,f.name focus_name
        FROM weekly_tasks t JOIN weekly_plans p ON p.id=t.plan_id
        JOIN users u ON u.id=p.user_id
        LEFT JOIN weekly_focus_categories f ON f.id=t.focus_category_id
        WHERE t.plan_id IN ({marks})
        ORDER BY p.iso_year DESC,p.iso_week DESC,u.full_name,t.id""", tuple(ids))
    reviews = wp._qdf(get_conn, f"""SELECT r.*,p.iso_year,p.iso_week,u.full_name,u.username,u.role
        FROM weekly_reviews r JOIN weekly_plans p ON p.id=r.plan_id
        JOIN users u ON u.id=p.user_id
        WHERE r.plan_id IN ({marks})
        ORDER BY p.iso_year DESC,p.iso_week DESC,u.full_name""", tuple(ids))
    return plans, tasks, reviews


def _room_excel_bytes(get_conn: Callable) -> bytes:
    plans, tasks, reviews = _room_export_frames(get_conn, 8)
    if plans.empty:
        return b""
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        plans.to_excel(writer, index=False, sheet_name="Ke_hoach_phong")
        tasks.to_excel(writer, index=False, sheet_name="Cong_viec_phong")
        reviews.to_excel(writer, index=False, sheet_name="Danh_gia_phong")
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                letter = col[0].column_letter
                max_len = max((len(str(cell.value or "")) for cell in col[:120]), default=10)
                ws.column_dimensions[letter].width = min(45, max(11, max_len + 2))
                for cell in col:
                    cell.alignment = cell.alignment.copy(wrap_text=True, vertical="top")
    return out.getvalue()


def _room_current_summary(get_conn: Callable):
    year, week, _, _ = wp._iso_week()
    return wp._qdf(get_conn, """SELECT u.id user_id,u.full_name,u.username,u.role,
        p.id plan_id,p.status,
        COUNT(CASE WHEN t.status<>'CANCELLED' THEN t.id END) total_tasks,
        COUNT(CASE WHEN t.status='COMPLETED' THEN t.id END) done_tasks,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' THEN t.actual_hours ELSE 0 END),0) actual_hours,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' AND t.quadrant='Q2' THEN t.actual_hours ELSE 0 END),0) q2_hours,
        r.progress_score,r.quality_score,r.week_score,r.grade
        FROM users u
        LEFT JOIN weekly_plans p ON p.user_id=u.id AND p.iso_year=? AND p.iso_week=?
        LEFT JOIN weekly_tasks t ON t.plan_id=p.id
        LEFT JOIN weekly_reviews r ON r.plan_id=p.id
        WHERE u.active=1 AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH')
        GROUP BY u.id,u.full_name,u.username,u.role,p.id,p.status,
                 r.progress_score,r.quality_score,r.week_score,r.grade
        ORDER BY u.full_name""", (year, week))


def _room_current_tasks(get_conn: Callable):
    year, week, _, _ = wp._iso_week()
    return wp._qdf(get_conn, """SELECT u.full_name,t.quadrant,t.title,t.due_date,t.status,
        t.planned_hours,t.actual_hours,t.expected_result,t.actual_result
        FROM weekly_plans p JOIN users u ON u.id=p.user_id
        JOIN weekly_tasks t ON t.plan_id=p.id
        WHERE p.iso_year=? AND p.iso_week=? AND u.active=1
          AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH')
        ORDER BY u.full_name,
          CASE t.quadrant WHEN 'Q2' THEN 1 WHEN 'Q1' THEN 2 WHEN 'Q3' THEN 3 ELSE 4 END,
          t.id""", (year, week))


def _room_pdf_bytes(get_conn: Callable) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    summary = _room_current_summary(get_conn)
    if summary.empty:
        return b""
    tasks = _room_current_tasks(get_conn)
    year, week, monday, sunday = wp._iso_week()

    regular = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if not regular.exists() or not bold.exists():
        raise RuntimeError("Máy chủ chưa có font DejaVu Sans để xuất PDF tiếng Việt.")
    pdfmetrics.registerFont(TTFont("KHDNRoom", str(regular)))
    pdfmetrics.registerFont(TTFont("KHDNRoomB", str(bold)))

    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), rightMargin=11*mm, leftMargin=11*mm,
                            topMargin=11*mm, bottomMargin=11*mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("room_title", parent=styles["Title"], fontName="KHDNRoomB",
                           fontSize=15, leading=19, alignment=TA_CENTER,
                           textColor=colors.HexColor("#006B68"))
    body = ParagraphStyle("room_body", parent=styles["BodyText"], fontName="KHDNRoom",
                          fontSize=8, leading=10)
    small = ParagraphStyle("room_small", parent=body, fontSize=7, leading=8.5)
    heading = ParagraphStyle("room_heading", parent=body, fontName="KHDNRoomB",
                             fontSize=10, textColor=colors.HexColor("#006B68"))

    story = [
        Paragraph("BÁO CÁO KẾ HOẠCH TUẦN – PHÒNG KHDN", title),
        Paragraph(f"Tuần {week}/{year} · {monday:%d/%m/%Y}–{sunday:%d/%m/%Y}", body),
        Spacer(1, 6),
    ]

    data = [["Cán bộ", "Vai trò", "Trạng thái", "Hoàn thành", "Q2 thực tế", "Điểm tiến độ", "Điểm chất lượng", "Điểm tuần", "Xếp loại"]]
    for _, r in summary.iterrows():
        total = int(r.get("total_tasks") or 0)
        done = int(r.get("done_tasks") or 0)
        actual = float(r.get("actual_hours") or 0)
        q2 = float(r.get("q2_hours") or 0)
        q2_pct = 100.0 * q2 / actual if actual > 0 else 0.0
        status = wp.PLAN_STATUS_LABELS.get(str(r.get("status") or ""), "Chưa lập" if pd.isna(r.get("plan_id")) else str(r.get("status") or ""))
        def score(v):
            return f"{float(v):.1f}" if pd.notna(v) else "—"
        data.append([
            Paragraph(html.escape(str(r.get("full_name") or "")), small),
            Paragraph(html.escape(str(r.get("role") or "")), small),
            status, f"{done}/{total}", f"{q2_pct:.1f}%",
            score(r.get("progress_score")), score(r.get("quality_score")), score(r.get("week_score")),
            str(r.get("grade") or "—") if pd.notna(r.get("grade")) else "—",
        ])
    table = Table(data, colWidths=[37*mm, 29*mm, 26*mm, 20*mm, 21*mm, 24*mm, 26*mm, 22*mm, 18*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "KHDNRoomB"), ("FONTNAME", (0,1), (-1,-1), "KHDNRoom"),
        ("FONTSIZE", (0,0), (-1,-1), 7), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#006B68")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#A8C9C6")),
        ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 3),
        ("RIGHTPADDING", (0,0), (-1,-1), 3), ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(table)

    if not tasks.empty:
        story += [Spacer(1, 9), Paragraph("CHI TIẾT CÔNG VIỆC TUẦN", heading)]
        detail = [["Cán bộ", "Q", "Công việc", "Hạn", "Giờ KH/TT", "Trạng thái", "Kết quả / đầu ra"]]
        for _, r in tasks.iterrows():
            result = str(r.get("actual_result") or r.get("expected_result") or "")
            detail.append([
                Paragraph(html.escape(str(r.get("full_name") or "")), small),
                str(r.get("quadrant") or ""),
                Paragraph(html.escape(str(r.get("title") or "")), small),
                str(r.get("due_date") or "—"),
                f"{float(r.get('planned_hours') or 0):.1f}/{float(r.get('actual_hours') or 0):.1f}",
                wp.TASK_STATUS_LABELS.get(str(r.get("status")), str(r.get("status"))),
                Paragraph(html.escape(result), small),
            ])
        detail_table = Table(detail, colWidths=[35*mm, 11*mm, 58*mm, 22*mm, 22*mm, 30*mm, 78*mm], repeatRows=1)
        detail_table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "KHDNRoomB"), ("FONTNAME", (0,1), (-1,-1), "KHDNRoom"),
            ("FONTSIZE", (0,0), (-1,-1), 6.8), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#006B68")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#A8C9C6")),
            ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 3),
            ("RIGHTPADDING", (0,0), (-1,-1), 3), ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ]))
        story.append(detail_table)

    doc.build(story)
    return out.getvalue()


def _export_view(get_conn: Callable, u):
    if not wp._is_leader(u):
        v3._export_view(get_conn, u)
        return

    st.markdown("### Xuất báo cáo Kế hoạch tuần")
    scope = st.radio("Phạm vi báo cáo", ["Cá nhân", "Phòng KHDN"], horizontal=True,
                     key="weekly_export_scope")
    if scope == "Cá nhân":
        v3._export_view(get_conn, u)
        return

    st.caption("Báo cáo phòng gồm cán bộ hỗ trợ và cán bộ QLKH; không có cấp Ban Giám đốc.")
    excel = _room_excel_bytes(get_conn)
    c1, c2 = st.columns(2)
    if excel:
        c1.download_button("⬇️ Excel phòng · 8 tuần", data=excel,
                           file_name=f"Ke_hoach_tuan_Phong_KHDN_{date.today():%Y%m%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    else:
        c1.info("Chưa có dữ liệu phòng để xuất Excel.")

    try:
        pdf = _room_pdf_bytes(get_conn)
    except Exception as exc:
        pdf = b""
        c2.error(f"Chưa tạo được PDF phòng: {exc}")
    if pdf:
        c2.download_button("⬇️ PDF phòng · tuần hiện tại", data=pdf,
                           file_name=f"Ke_hoach_tuan_Phong_KHDN_{date.today():%Y%m%d}.pdf",
                           mime="application/pdf", use_container_width=True)


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    # Defense in depth: do not rely only on the sidebar/router to enforce access.
    if not (wp._is_officer(u) or wp._is_leader(u)):
        st.error("Bạn không có quyền truy cập Kế hoạch tuần.")
        return

    v4._init_v4_schema(get_conn)
    v4._apply_score_fallbacks(get_conn)
    wp._inject_weekly_css()
    v2._inject_css()
    page_title("Kế hoạch tuần", "Quản trị ưu tiên theo Q1–Q4; hệ thống tự phân loại, cán bộ không tự chọn góc phần tư.")
    v2._glossary()

    if wp._is_leader(u):
        options = [
            ("mine", "📅 Kế hoạch của tôi"), ("review", "✅ Duyệt & đánh giá"),
            ("focus", "🎯 Trọng tâm Q2"), ("room", "📊 Tổng quan phòng"),
            ("history", "📈 8 tuần"), ("export", "⬇️ Xuất báo cáo"),
        ]
    else:
        options = [("mine", "📅 Tuần của tôi"), ("history", "📈 8 tuần"), ("export", "⬇️ Xuất báo cáo")]

    if pill_nav:
        view = pill_nav("weekly_plan_view", options, default="mine", prefix="weekly_plan_v5")
    else:
        labels = [x[1] for x in options]
        values = [x[0] for x in options]
        current = st.session_state.get("weekly_plan_view", "mine")
        idx = values.index(current) if current in values else 0
        selected = st.radio("Chế độ", labels, index=idx, horizontal=True, label_visibility="collapsed")
        view = dict((label, value) for value, label in options)[selected]
        st.session_state["weekly_plan_view"] = view

    if view == "mine":
        v4._my_plan(get_conn, u)
    elif view == "review" and wp._is_leader(u):
        v4._leader_review(get_conn, u)
    elif view == "focus" and wp._is_leader(u):
        v4._focus_maintenance(get_conn, u)
    elif view == "room" and wp._is_leader(u):
        v3._room_dashboard(get_conn)
    elif view == "history":
        v2._history_view(get_conn, u)
    elif view == "export":
        _export_view(get_conn, u)
