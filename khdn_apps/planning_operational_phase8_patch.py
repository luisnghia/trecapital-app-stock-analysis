"""Operational phase 8: restore Tác nghiệp backup UX and harden Weekly Plan links.

This is intentionally a final runtime overlay after phase 7. It keeps the
existing approval/workflow layers intact while addressing three operational
requirements:
- System Admin backup again exposes the legacy Tác nghiệp backup/download and
  annual archive controls in addition to the full database backup;
- selecting an existing Customer Work case in Weekly Plan takes completion
  date, controlling leader and priority/focus category from that case and
  persists ``linked_case_id`` as the workflow link;
- an empty cancellation reason is visibly red before submission.

No business-row values are written to logs.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import html
import os
from pathlib import Path
import sqlite3

from khdn_apps import backup_management_patch as _backup
from khdn_apps import weekly_plan_form_refinement_patch as _form
from khdn_apps import planning_operational_phase7_patch as _p7
from khdn_apps import planning_operational_phase3_weekly as _p3week
from khdn_apps import planning_operational_phase3_dashboard as _p3dash
from khdn_apps.storage import read_status, sqlite_backup_bytes

VERSION = "1.0.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE8_VERSION"
_BACKUP_FLAG = "_P8_OPERATIONAL_BACKUP_WRAPPED"


def _table_exists(c, name):
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (str(name),)).fetchone())


def _cols(c, table):
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _case_rows(c, customer_id, uid, manager=False):
    """Open Customer Work cases plus the three fields Weekly Plan must inherit."""
    if not customer_id or not _table_exists(c, "customer_work_cases"):
        return []
    cols = _cols(c, "customer_work_cases")
    controller_expr = "cw.controller_user_id" if "controller_user_id" in cols else "NULL"
    important_expr = "cw.important_category_id" if "important_category_id" in cols else "NULL"
    sql = f"""
        SELECT cw.id,cw.case_code,cw.title,cw.case_type,cw.owner_user_id,cw.expected_complete_at,
               {controller_expr} AS controller_user_id,
               {important_expr} AS important_category_id,
               COALESCE(ws.name,'') AS stage_name,
               COALESCE(owner.full_name,'') AS owner_name,
               COALESCE(ctrl.full_name,'') AS controller_name
        FROM customer_work_cases cw
        LEFT JOIN work_stage_catalog ws ON ws.id=cw.current_stage_id
        LEFT JOIN users owner ON owner.id=cw.owner_user_id
        LEFT JOIN users ctrl ON ctrl.id={controller_expr}
        WHERE cw.customer_id=? AND cw.status='ACTIVE'
    """
    params = [int(customer_id)]
    if not manager:
        sql += " AND cw.owner_user_id=?"
        params.append(int(uid))
    sql += " ORDER BY CASE WHEN cw.expected_complete_at IS NULL THEN 1 ELSE 0 END,cw.expected_complete_at,cw.id"
    return [dict(r) for r in c.execute(sql, params).fetchall()]


def _source_defaults(linked_case, leaders, focus_rows):
    due = None
    leader = None
    focus = None
    if linked_case:
        raw_due = linked_case.get("expected_complete_at")
        if raw_due:
            try:
                due = date.fromisoformat(str(raw_due)[:10])
            except Exception:
                due = None
        controller = int(linked_case.get("controller_user_id") or 0)
        if controller:
            leader = next(
                (r for r in (leaders or []) if int(r.get("id") or 0) == controller),
                None,
            )
        important = int(linked_case.get("important_category_id") or 0)
        if important:
            focus = next(
                (
                    r for r in (focus_rows or [])
                    if int(r.get("legacy_category_id") or 0) == important
                ),
                None,
            )
    return due, leader, focus


def _archive_file(data_dir: Path, raw):
    """Resolve a legacy annual-archive filename without permitting path escape."""
    if not raw:
        return None
    root = Path(data_dir).resolve()
    value = Path(str(raw))
    candidates = []
    if value.is_absolute():
        candidates.append(value)
    else:
        candidates.extend([root / "annual_archive" / value.name, root / value])
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved.is_relative_to(root) and resolved.exists() and resolved.is_file():
                return resolved
        except Exception:
            continue
    return None


def _annual_rows(db_path: Path):
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30) as c:
        c.row_factory = sqlite3.Row
        if not _table_exists(c, "annual_archives"):
            return []
        return [dict(r) for r in c.execute("SELECT * FROM annual_archives ORDER BY year DESC").fetchall()]


def _render_annual_table(st, rows):
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('year') or '—'))}</td>"
            f"<td>{html.escape(str(row.get('task_count') or 0))}</td>"
            f"<td>{html.escape(str(row.get('archived_at') or '—'))}</td>"
            f"<td>{html.escape(str(row.get('best_five_year_reference') or '—'))}</td>"
            "</tr>"
        )
    st.html(
        "<div class='p8-archive-table'><table><thead><tr>"
        "<th>Năm</th><th>Số hồ sơ tác nghiệp</th><th>Thời gian sao lưu</th><th>Năm chuẩn tham chiếu</th>"
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"
        "<style>.p8-archive-table{overflow-x:auto;width:100%}.p8-archive-table table{width:100%;table-layout:fixed;border-collapse:collapse}"
        ".p8-archive-table th,.p8-archive-table td{padding:8px 9px;border:1px solid rgba(120,160,150,.28);vertical-align:top;white-space:normal;overflow-wrap:anywhere}"
        ".p8-archive-table th{font-weight:900}.p8-archive-table td:nth-child(1),.p8-archive-table th:nth-child(1){width:10%}"
        ".p8-archive-table td:nth-child(2),.p8-archive-table th:nth-child(2){width:16%;text-align:right}</style>"
    )


def _render_operational_backup(st, u, app_ns, logger=None):
    if not bool(u.get("is_admin")):
        return
    if str(st.session_state.get("admin_scope") or "system") != "system":
        return

    data_dir = Path(os.getenv("KHDN_DATA_DIR", str(app_ns.get("RUNTIME_DATA_DIR") or Path.cwd()))).resolve()
    db_path = Path(os.getenv("KHDN_DB_PATH", str(app_ns.get("DB_PATH") or data_dir / "khdn_ops.db"))).resolve()
    status = read_status(data_dir / "backup_status.json")

    st.divider()
    st.markdown("### 🧰 Sao lưu Tác nghiệp & lưu trữ vận hành")
    st.info(
        "Phần Tác nghiệp được giữ đầy đủ song song với Kế hoạch: tải snapshot SQLite hiện tại, "
        "các bản sao lưu tự động hằng ngày và bộ lưu trữ cuối năm (thống kê, chi tiết tác nghiệp, SQLite)."
    )

    if db_path.exists():
        try:
            current_bytes = sqlite_backup_bytes(db_path)
            clicked = st.download_button(
                "⬇️ Tải backup SQLite hiện tại (Tác nghiệp + Kế hoạch)",
                data=current_bytes,
                file_name=f"khdn_ops_current_{datetime.now():%Y-%m-%d_%H%M}.db",
                mime="application/vnd.sqlite3",
                key="p8_current_sqlite_download",
                use_container_width=True,
            )
            if clicked and logger:
                logger.info("P8_OPERATIONAL_BACKUP_DOWNLOAD kind=current_sqlite bytes=%s", len(current_bytes))
        except Exception as exc:
            if logger:
                logger.exception("P8_CURRENT_SQLITE_PREPARE_FAILED")
            st.error(f"Không thể chuẩn bị snapshot SQLite hiện tại: {exc}")

    retained_names = [str(x) for x in (status.get("retained") or [])]
    daily_dir = data_dir / "backups"
    daily = []
    for name in retained_names:
        candidate = (daily_dir / Path(name).name).resolve()
        if candidate.is_relative_to(data_dir) and candidate.exists() and candidate.is_file():
            daily.append(candidate)
    if not daily and daily_dir.exists():
        daily = sorted(daily_dir.glob("khdn_ops_????-??-??.db.gz"), reverse=True)

    last = str(status.get("last_success") or "")
    if last:
        st.caption(
            f"Sao lưu tự động thành công gần nhất: {last}. Giữ tối đa 14 bản hằng ngày, "
            "trong ngân sách lưu trữ 50 MB."
        )
    if daily:
        names = [p.name for p in daily]
        chosen_name = st.selectbox("Chọn bản sao lưu tự động Tác nghiệp", names, key="p8_scheduled_backup_choice")
        chosen = next(p for p in daily if p.name == chosen_name)
        clicked = st.download_button(
            "⬇️ Tải bản sao lưu tự động",
            data=chosen.read_bytes(),
            file_name=chosen.name,
            mime="application/gzip",
            key="p8_scheduled_backup_download",
            use_container_width=True,
        )
        if clicked and logger:
            logger.info("P8_OPERATIONAL_BACKUP_DOWNLOAD kind=daily file=%s bytes=%s", chosen.name, chosen.stat().st_size)
    else:
        st.caption("Chưa có bản sao lưu tự động hằng ngày để tải.")
    st.caption(
        "Các bản sao tự động nằm cùng ổ dữ liệu chính. Nên tải thêm một bản về nơi lưu trữ riêng để có thể phục hồi nếu ổ bị xóa."
    )

    try:
        archives = _annual_rows(db_path)
    except Exception as exc:
        archives = []
        if logger:
            logger.exception("P8_ANNUAL_ARCHIVE_LIST_FAILED")
        st.error(f"Không thể đọc danh mục lưu trữ cuối năm: {exc}")

    if not archives:
        st.caption("Chưa có năm đã kết thúc có dữ liệu để tạo lưu trữ tự động.")
    else:
        st.markdown("#### 📦 Lưu trữ dữ liệu Tác nghiệp theo năm")
        _render_annual_table(st, archives)
        for row in archives:
            year = int(row.get("year") or 0)
            with st.expander(f"Năm {year} · {int(row.get('task_count') or 0)} hồ sơ", expanded=False):
                files = [
                    ("📊 Thống kê năm", "stats_file", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ("📋 Chi tiết tác nghiệp", "detail_file", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ("🗄 Snapshot SQLite", "db_backup_file", "application/vnd.sqlite3"),
                ]
                cols = st.columns(3)
                found = 0
                for col, (label, field, mime) in zip(cols, files):
                    path = _archive_file(data_dir, row.get(field))
                    if not path:
                        col.caption(f"{label}: không tìm thấy file")
                        continue
                    found += 1
                    clicked = col.download_button(
                        label,
                        data=path.read_bytes(),
                        file_name=path.name,
                        mime=mime,
                        key=f"p8_archive_{year}_{field}",
                        use_container_width=True,
                    )
                    if clicked and logger:
                        logger.info("P8_OPERATIONAL_BACKUP_DOWNLOAD kind=annual year=%s field=%s bytes=%s", year, field, path.stat().st_size)
                if not found:
                    st.warning("Bản ghi lưu trữ năm còn trong CSDL nhưng các file vật lý không còn trên volume.")


def _install_backup_overlay(logger=None):
    if getattr(_backup, _BACKUP_FLAG, None) == VERSION:
        return
    original = _backup.render_backup_admin

    def render_backup_admin(st, u, app_ns, logger_arg=None):
        result = original(st, u, app_ns, logger_arg or logger)
        _render_operational_backup(st, u, app_ns, logger_arg or logger)
        return result

    _backup.render_backup_admin = render_backup_admin
    setattr(_backup, _BACKUP_FLAG, VERSION)
    if logger:
        logger.info("P8_OPERATIONAL_BACKUP_INSTALLED legacy_daily=1 annual_archive=1 current_sqlite=1")


def _install_linked_weekly_form(policy, logger=None):
    def add_item_form(st, u, core, conn_fn, ws, focus_rows, emergent=False, logger_arg=None):
        uid = int(policy._uget(u, "id"))
        epoch_key = f"wp_refine_epoch_{ws.isoformat()}_{'ps' if emergent else 'plan'}"
        epoch = int(st.session_state.get(epoch_key, 0) or 0)
        prefix = f"wp_refined_{ws.isoformat()}_{'ps' if emergent else 'plan'}_{epoch}"
        st.markdown("#### ⚡ Công việc phát sinh" if emergent else "#### ＋ Thêm công việc kế hoạch")

        with conn_fn() as c:
            customers = core.customers(c, uid)
            leaders = _form._leader_rows(c)
            inferred_leader = policy._leader_for_staff(c, uid)

        customer = st.selectbox(
            "Khách hàng",
            [None] + customers,
            index=0,
            format_func=lambda x: "— Không gắn khách hàng —" if x is None else f"{x.get('customer_name')} · {'CIF '+str(x.get('cif')) if x.get('cif') else 'Chưa có CIF'}",
            key=f"{prefix}_customer",
        )

        cases = []
        if customer:
            with conn_fn() as c:
                cases = _case_rows(c, int(customer["id"]), uid, policy._manager(u))

        linked_case = None
        if cases:
            linked_case = st.selectbox(
                "Công việc *",
                [None] + cases,
                index=0,
                format_func=lambda x: "— Chọn công việc đang xử lý —" if x is None else " · ".join(
                    p for p in [str(x.get("case_code") or ""), str(x.get("title") or ""), str(x.get("stage_name") or "")] if p
                ),
                key=f"{prefix}_case",
                help="Chọn công việc khách hàng đang xử lý để Kế hoạch tuần liên kết trực tiếp với workflow Công việc khách hàng.",
            )
            title = str(linked_case.get("title") or "").strip() if linked_case else ""
            if linked_case:
                st.success(
                    f"🔗 Đã liên kết workflow {linked_case.get('case_code') or 'CVKH'} · "
                    f"{linked_case.get('stage_name') or 'Đang xử lý'} · linked_case_id={int(linked_case['id'])}"
                )
        else:
            title = st.text_input(
                "Công việc *", key=f"{prefix}_title",
                placeholder="Ví dụ: Gặp Công ty A – tiếp thị tiền gửi",
            )
            if customer:
                st.caption("Khách hàng chưa có công việc đang xử lý của cán bộ này; nhập công việc mới cho kế hoạch tuần.")

        day = st.date_input(
            "Ngày thực hiện *",
            value=max(ws, date.today()) if ws <= max(ws, date.today()) <= ws + timedelta(days=6) else ws,
            min_value=ws, max_value=ws + timedelta(days=6), key=f"{prefix}_day",
        )

        with conn_fn() as c:
            scope = policy._scope_key(c, uid)
            live_focus_rows = policy._focus_categories(c, scope, ws.year, False)
        auto_due, auto_leader, auto_focus = _source_defaults(linked_case, leaders, live_focus_rows)

        if linked_case and auto_due:
            due = st.date_input(
                "Ngày dự kiến hoàn thành *", value=auto_due,
                key=f"{prefix}_due_linked_{int(linked_case['id'])}", disabled=True,
                help="Tự động lấy từ Ngày hoàn thành/dự kiến hoàn thành của Công việc khách hàng.",
            )
            st.caption("🔗 Ngày hoàn thành được đồng bộ từ Công việc khách hàng.")
        else:
            due = st.date_input(
                "Ngày dự kiến hoàn thành *", value=day, min_value=day,
                key=f"{prefix}_due",
            )
            if linked_case:
                st.warning("Công việc khách hàng chưa có Ngày hoàn thành; vui lòng bổ sung ngày cho kế hoạch tuần.")

        leader_options = [None] + leaders
        if linked_case and auto_leader:
            leader = st.selectbox(
                "Lãnh đạo phòng phụ trách *", [auto_leader], index=0,
                format_func=lambda x: str(x.get("full_name") or ""),
                key=f"{prefix}_leader_linked_{int(linked_case['id'])}", disabled=True,
                help="Tự động lấy từ Lãnh đạo kiểm soát/phụ trách của Công việc khách hàng.",
            )
            st.caption("🔗 Lãnh đạo phụ trách được đồng bộ từ Công việc khách hàng.")
        else:
            leader_idx = 0
            if inferred_leader:
                for i, row in enumerate(leader_options):
                    if isinstance(row, dict) and int(row.get("id") or 0) == int(inferred_leader):
                        leader_idx = i
                        break
            leader = st.selectbox(
                "Lãnh đạo phòng phụ trách *", leader_options, index=leader_idx,
                format_func=lambda x: "— Chọn lãnh đạo phụ trách —" if x is None else str(x.get("full_name") or ""),
                key=f"{prefix}_leader",
            )
            if linked_case and linked_case.get("controller_user_id"):
                st.warning("Lãnh đạo gắn với Công việc khách hàng hiện không còn trong danh sách lãnh đạo đang hoạt động; vui lòng chọn lại.")

        if linked_case and auto_focus:
            focus = st.selectbox(
                "1. Việc này thuộc danh mục công việc trọng tâm nào của phòng? *",
                [auto_focus], index=0,
                format_func=lambda x: f"{x.get('code')} · {x.get('name')}",
                key=f"{prefix}_focus_linked_{int(linked_case['id'])}", disabled=True,
                help="Tự động lấy từ Danh mục công việc quan trọng/trọng tâm đã gán cho Công việc khách hàng.",
            )
            due7, risk, q = None, None, 2
            st.success("🔗 Danh mục trọng tâm được đồng bộ từ Công việc khách hàng → Q2 · Trọng tâm.")
        else:
            focus, due7, risk, q = _form._focus_picker(st, policy, live_focus_rows, prefix, due)
            if linked_case and linked_case.get("important_category_id"):
                st.warning("Danh mục trọng tâm của Công việc khách hàng chưa có bản ánh xạ đang hoạt động; vui lòng chọn lại.")

        ok = st.button(
            "Lưu công việc phát sinh" if emergent else "Thêm vào kế hoạch",
            key=f"{prefix}_save", type="primary", use_container_width=True,
        )
        if not ok:
            return

        missing = []
        if not str(title or "").strip():
            missing.append("Công việc")
        if not linked_case and due < day:
            missing.append("Ngày dự kiến hoàn thành")
        if not leader:
            missing.append("Lãnh đạo phòng phụ trách")
        if q is None:
            missing.append("Căn cứ phân loại Q1–Q4")
        if cases and not linked_case:
            missing.append("Công việc đang xử lý")
        if missing:
            st.error("Vui lòng nhập/chọn đầy đủ: " + ", ".join(missing) + ".")
            return

        linked_case_id = int(linked_case["id"]) if linked_case else None
        if linked_case_id:
            with conn_fn() as c:
                duplicate = c.execute(
                    """SELECT 1 FROM weekly_plan_items w JOIN weekly_plans p ON p.id=w.plan_id
                       WHERE p.user_id=? AND p.week_start=? AND w.linked_case_id=? AND w.status<>'CANCELLED' LIMIT 1""",
                    (uid, ws.isoformat(), linked_case_id),
                ).fetchone()
            if duplicate:
                st.error("Công việc khách hàng này đã có trong kế hoạch tuần, không tạo trùng.")
                return

        item = {
            "work_date": day.isoformat(), "start_time": None, "daypart": None,
            "title": str(title).strip(),
            "customer_id": int(customer["id"]) if customer else None,
            "customer_text": str(customer.get("customer_name") or "") if customer else "",
            "category": "Công việc phát sinh" if emergent else "Kế hoạch tuần",
            "purposes": [], "source_text": str(title).strip(), "linked_task_id": None,
            "note": None, "estimated_hours": 1.0, "expected_output": "",
            "is_emergent": 1 if emergent else 0,
            "focus_category_id": int(focus["id"]) if focus else None,
            "deadline_within_7d": due7, "kpi_risk_flag": risk,
        }
        iid, errs = policy._save_extended_item(core, conn_fn, uid, ws, item, logger_arg or logger)
        if not iid:
            st.error("; ".join(str(e) for e in (errs or ["Không thể lưu công việc"])))
            return
        with conn_fn() as c:
            c.execute(
                "UPDATE weekly_plan_items SET expected_complete_date=?,controller_user_id=?,linked_case_id=?,expected_output='' WHERE id=?",
                (due.isoformat(), int(leader["id"]), linked_case_id, int(iid)),
            )
        if logger_arg or logger:
            (logger_arg or logger).info(
                "P8_WEEKLY_CUSTOMER_WORK_LINK_CREATED item=%s case=%s actor=%s due_from_case=%s leader_from_case=%s focus_from_case=%s",
                int(iid), linked_case_id or 0, uid,
                int(bool(linked_case and auto_due)), int(bool(linked_case and auto_leader)), int(bool(linked_case and auto_focus)),
            )
        st.session_state[epoch_key] = epoch + 1
        st.toast("Đã thêm công việc vào kế hoạch và lưu liên kết workflow.", icon="✅")
        st.rerun()

    policy._add_item_form = add_item_form
    if logger:
        logger.info("P8_WEEKLY_LINK_FORM_INSTALLED customer_work_source=1 linked_case_id=1")


_CANCEL_REASON_CSS = """
<style>
div[class*='st-key-p7_cancel_reason_'] textarea:placeholder-shown {
  border:2px solid #FF4B4B !important;
  box-shadow:0 0 0 1px rgba(255,75,75,.22) !important;
  background:rgba(255,75,75,.08) !important;
}
div[class*='st-key-p7_cancel_reason_']:has(textarea:placeholder-shown) label,
div[class*='st-key-p7_cancel_reason_']:has(textarea:placeholder-shown) label * {
  color:#FF4B4B !important;
  -webkit-text-fill-color:#FF4B4B !important;
  font-weight:800 !important;
}
</style>
"""


def _install_cancel_reason_red(logger=None):
    original = _p7._render_update_form

    def render_update_form(st, u, policy, weekly_core, get_conn, item, logger_arg=None):
        # The selector is inert until the cancellation textarea exists. Once it
        # exists, :placeholder-shown means the officer has not entered a reason.
        st.html(_CANCEL_REASON_CSS)
        return original(st, u, policy, weekly_core, get_conn, item, logger_arg or logger)

    _p7._render_update_form = render_update_form
    _p3week.render_week_update_form = render_update_form
    _p3dash.render_week_update_form = render_update_form
    if logger:
        logger.info("P8_CANCEL_REASON_REQUIRED_STYLE_INSTALLED empty_red=1")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    _install_backup_overlay(logger)
    _install_linked_weekly_form(policy, logger)
    _install_cancel_reason_red(logger)
    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "PLANNING_OPERATIONAL_PHASE8_INSTALLED version=%s operational_backup=1 linked_customer_work=1 cancel_empty_red=1",
            VERSION,
        )
