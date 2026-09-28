"""Phase 2: weekly performance, close/review scoring and 8-week dashboards.

Design principle: extend the current app without replacing Customer Work workflow.
- No manual planned/actual-hour fields are reintroduced.
- Weekly Plan status remains separate from Customer Work stages/SLA.
- Staff landing stays Today; leader/admin landing stays Room Dashboard.
- Adds 1–5 self/leader review, objective weekly scores, audit, and 8-week views.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import csv
import io
import json

from khdn_apps import planning_week_board_focus_patch as weekboard
from khdn_apps import planning_room_dashboard_detail_patch as room_dashboard

VERSION = "1.0.0"
_FLAG = "_WEEKLY_PERFORMANCE_PHASE2_VERSION"
WEIGHTS = {2: 3.0, 1: 3.0, 3: 1.0, 4: 0.0}
GRADE = ((90, "A · Xuất sắc"), (75, "B · Tốt"), (60, "C · Đạt"), (0, "D · Cần cải thiện"))
SELF_LEVELS = {
    1: "1 · Chưa đạt – kết quả còn nhiều thiếu sót, cần hỗ trợ rõ rệt",
    2: "2 · Cần cải thiện – hoàn thành một phần, chất lượng/chủ động chưa đạt",
    3: "3 · Đạt – hoàn thành yêu cầu cơ bản của tuần",
    4: "4 · Tốt – hoàn thành tốt, chủ động và ít phải nhắc",
    5: "5 · Xuất sắc – kết quả nổi bật, chủ động và tạo giá trị rõ rệt",
}


def _cols(c, table):
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _add(c, table, name, ddl):
    if name not in _cols(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dmy(v):
    if not v:
        return "—"
    s = str(v)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        try:
            return date.fromisoformat(s[:10]).strftime("%d/%m/%Y")
        except Exception:
            return s


def _ensure_schema(policy, weekly_core, get_conn, logger=None):
    policy._ensure_schema(weekly_core, get_conn, logger)
    with get_conn() as c:
        for name, ddl in (
            ("progress_score", "REAL"),
            ("quality_score", "REAL"),
            ("week_score", "REAL"),
            ("week_grade", "TEXT"),
            ("score_gap_reason", "TEXT"),
            ("quality_fallback", "INTEGER NOT NULL DEFAULT 0"),
        ):
            _add(c, "weekly_plans", name, ddl)
        for name, ddl in (
            ("actual_result", "TEXT"),
            ("completed_at", "TEXT"),
        ):
            _add(c, "weekly_plan_items", name, ddl)
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS weekly_performance_audit(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                actor_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_weekly_perf_audit_plan
              ON weekly_performance_audit(plan_id,created_at);
            """
        )


def _parse_date(v):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def _parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00").replace("T", " "))
    except Exception:
        try:
            return datetime.strptime(str(v)[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


def _is_done(item):
    return str(item.get("status") or "").upper() in {"DONE", "HOAN_THANH", "COMPLETED"}


def _is_cancelled(item):
    return str(item.get("status") or "").upper() in {"CANCELLED", "HUY", "CANCELED"}


def _due_date(item):
    return _parse_date(item.get("expected_complete_date")) or _parse_date(item.get("work_date"))


def _completion_date(item):
    dt = _parse_dt(item.get("completed_at")) or _parse_dt(item.get("updated_at"))
    return dt.date() if dt else None


def _grade(score):
    score = float(score or 0)
    for floor, label in GRADE:
        if score >= floor:
            return label
    return "D · Cần cải thiện"


def _metrics(items):
    live = [dict(x) for x in items if not _is_cancelled(x)]
    completed = [x for x in live if _is_done(x)]
    on_time = []
    late = []
    weighted_num = 0.0
    weighted_den = 0.0
    for x in live:
        q = int(x.get("priority_quadrant") or 4)
        w = WEIGHTS.get(q, 0.0)
        weighted_den += w
        h = 0.0
        if _is_done(x):
            due = _due_date(x)
            done = _completion_date(x)
            if due and done and done > due:
                h = 0.6
                late.append(x)
            else:
                h = 1.0
                on_time.append(x)
        weighted_num += w * h
    progress = 100.0 * weighted_num / weighted_den if weighted_den > 0 else 0.0
    total = len(live)
    completion_rate = 100.0 * len(completed) / total if total else 0.0
    ontime_rate = 100.0 * len(on_time) / len(completed) if completed else 0.0
    q2_count = sum(int(x.get("priority_quadrant") or 4) == 2 for x in live)
    q2_ratio = 100.0 * q2_count / total if total else 0.0
    emergent = sum(int(x.get("is_emergent") or 0) for x in live)
    q2_delayed = sum(
        int(x.get("priority_quadrant") or 4) == 2
        and (int(x.get("carryover_count") or 0) >= 2 or int(x.get("q2_watch_flag") or 0) == 1)
        for x in live
    )
    overdue_open = sum(
        (not _is_done(x)) and (_due_date(x) is not None) and _due_date(x) < date.today()
        for x in live
    )
    return {
        "total": total,
        "completed": len(completed),
        "on_time": len(on_time),
        "late": len(late),
        "progress": round(progress, 2),
        "completion_rate": round(completion_rate, 1),
        "ontime_rate": round(ontime_rate, 1),
        "q2_count": q2_count,
        "q2_ratio": round(q2_ratio, 1),
        "emergent": emergent,
        "q2_delayed": q2_delayed,
        "overdue_open": overdue_open,
        "zero_weight": weighted_den <= 0,
    }


def _quality(self_score, manager_score=None, fallback=False):
    s = float(self_score or 0)
    if fallback or manager_score is None:
        return round(20.0 * s, 2)
    m = float(manager_score or 0)
    return round(20.0 * (0.3 * s + 0.7 * m), 2)


def _week_score(progress, quality):
    return round(0.5 * float(progress or 0) + 0.5 * float(quality or 0), 2)


def _load_items(c, plan_id):
    return [dict(r) for r in c.execute(
        "SELECT * FROM weekly_plan_items WHERE plan_id=? ORDER BY work_date,id",
        (int(plan_id),),
    ).fetchall()]


def _suggestions(metrics):
    strengths = f"Hoàn thành {metrics['completed']}/{metrics['total']} công việc; tỷ lệ đúng hạn {metrics['ontime_rate']:.0f}%." if metrics["total"] else "Chưa có dữ liệu công việc để tổng hợp."
    issues = []
    if metrics["overdue_open"]:
        issues.append(f"{metrics['overdue_open']} công việc đang quá hạn")
    if metrics["q2_delayed"]:
        issues.append(f"{metrics['q2_delayed']} công việc Q2 bị lùi nhiều lần")
    if metrics["emergent"]:
        issues.append(f"{metrics['emergent']} công việc phát sinh trong tuần")
    if not issues:
        issues.append("Chưa ghi nhận tồn tại nổi bật từ dữ liệu hệ thống")
    issue_text = "; ".join(issues) + "."
    causes = "Rà soát nguyên nhân đối với các việc trễ/phát sinh và các điểm chưa đạt kế hoạch."
    proposals = "Ưu tiên xử lý công việc Q2 còn tồn, hạn chế phát sinh và chủ động chuẩn bị đầu việc tuần sau."
    return strengths, issue_text, causes, proposals


def _score_cards(st, metrics, plan=None):
    plan = plan or {}
    a, b, c, d = st.columns(4)
    a.metric("Hoàn thành", f"{metrics['completed']}/{metrics['total']}", f"{metrics['completion_rate']:.0f}%")
    b.metric("Đúng hạn", f"{metrics['ontime_rate']:.0f}%", f"{metrics['late']} việc trễ")
    c.metric("Q2 theo số việc", f"{metrics['q2_ratio']:.0f}%", f"{metrics['q2_count']}/{metrics['total']}")
    d.metric("Điểm tiến độ", f"{metrics['progress']:.1f}", "Q4 không tính điểm")
    if metrics["zero_weight"] and metrics["total"]:
        st.warning("Tuần này không có công việc Q1/Q2/Q3 được tính trọng số; Điểm tiến độ = 0.")
    if plan.get("week_score") is not None:
        st.success(f"Điểm tuần **{float(plan['week_score']):.2f}/100** · **{plan.get('week_grade') or _grade(plan['week_score'])}**")


def _render_execution_and_review(st, u, policy, weekly_core, get_conn, ws, plan, items, focus_rows, logger=None):
    uid = int(policy._uget(u, "id"))
    status = str(plan.get("workflow_status") or "NHAP")
    live = [dict(x) for x in items if not _is_cancelled(x)]

    # Keep the familiar Monday-Friday visual board, but do not ask staff to enter hours.
    weekboard._render_week_board(st, policy, get_conn, uid, ws, items, status)
    metrics = _metrics(items)
    _score_cards(st, metrics, plan)

    if status == "DA_DUYET":
        st.success("Kế hoạch đã duyệt. Cập nhật trạng thái/kết quả thực tế tại đây; không phải nhập giờ thực tế.")
        for x in live:
            iid = int(x.get("id") or 0)
            with st.expander(f"Cập nhật · {x.get('title')}", expanded=False):
                opts = ["PLANNED", "IN_PROGRESS", "DONE", "CANCELLED"]
                labels = {"PLANNED": "Chưa làm", "IN_PROGRESS": "Đang làm", "DONE": "Hoàn thành", "CANCELLED": "Hủy"}
                cur = str(x.get("status") or "PLANNED")
                current = cur if cur in opts else "PLANNED"
                stat = st.selectbox("Trạng thái", opts, index=opts.index(current), format_func=lambda z: labels[z], key=f"p2_status_{iid}")
                result = st.text_area("Kết quả thực tế / ghi chú", value=str(x.get("actual_result") or ""), max_chars=1000, key=f"p2_result_{iid}")
                if st.button("Lưu cập nhật", key=f"p2_save_{iid}", type="primary", use_container_width=True):
                    ts = _now()
                    completed_at = ts if stat == "DONE" and not x.get("completed_at") else x.get("completed_at")
                    if stat != "DONE":
                        completed_at = None
                    with get_conn() as c:
                        c.execute(
                            "UPDATE weekly_plan_items SET status=?,actual_result=?,completed_at=?,updated_at=? WHERE id=? AND user_id=?",
                            (stat, str(result or "").strip(), completed_at, ts, iid, uid),
                        )
                        c.execute(
                            "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'EXEC_UPDATE_PHASE2',?,?)",
                            (iid, uid, json.dumps({"status": stat, "actual_result": str(result or "").strip()}, ensure_ascii=False), ts),
                        )
                    st.rerun()

        add_key = f"p2_emergent_open_{int(plan['id'])}"
        if not st.session_state.get(add_key):
            if st.button("＋ Thêm công việc mới trong tuần", key=f"p2_emergent_btn_{plan['id']}", use_container_width=True):
                st.session_state[add_key] = True
                st.rerun()
        else:
            a, b = st.columns([6, 1])
            a.caption("Công việc thêm sau khi kế hoạch đã duyệt tự ghi nhận là công việc phát sinh.")
            if b.button("✕ Đóng", key=f"p2_emergent_close_{plan['id']}", use_container_width=True):
                st.session_state.pop(add_key, None)
                st.rerun()
            policy._add_item_form(st, u, weekly_core, get_conn, ws, focus_rows, emergent=True, logger=logger)

        st.divider()
        with st.expander("✅ Chốt tuần · tự đánh giá", expanded=False):
            s1, s2, s3, s4 = _suggestions(metrics)
            st.info("Gợi ý từ dữ liệu hệ thống – cán bộ chỉnh lại trước khi chốt:\n\n" + s1 + "\n\n" + s2)
            strengths = st.text_area("Mặt được *", value=str(plan.get("self_strengths") or s1), max_chars=500, key=f"p2_self_strength_{plan['id']}")
            issues = st.text_area("Tồn tại, hạn chế *", value=str(plan.get("self_issues") or s2), max_chars=500, key=f"p2_self_issues_{plan['id']}")
            causes = st.text_area("Nguyên nhân *", value=str(plan.get("self_causes") or s3), max_chars=500, key=f"p2_self_causes_{plan['id']}")
            proposals = st.text_area("Đề xuất / kế hoạch khắc phục tuần sau *", value=str(plan.get("self_proposals") or s4), max_chars=500, key=f"p2_self_prop_{plan['id']}")
            old_self = int(round(float(plan.get("self_score") or 3)))
            old_self = min(5, max(1, old_self))
            self_score = st.select_slider("Tự chấm chất lượng tuần *", options=[1,2,3,4,5], value=old_self, format_func=lambda z: SELF_LEVELS[z], key=f"p2_self_score_{plan['id']}")
            if st.button("🔒 Chốt tuần", key=f"p2_close_{plan['id']}", type="primary", use_container_width=True):
                required = [strengths.strip(), issues.strip(), causes.strip(), proposals.strip()]
                if not all(required):
                    st.error("Phải nhập đủ 4 nội dung: Mặt được, Tồn tại, Nguyên nhân và Đề xuất.")
                else:
                    ts = _now()
                    progress = metrics["progress"]
                    with get_conn() as c:
                        c.execute(
                            """UPDATE weekly_plans SET workflow_status='DA_CHOT',self_score=?,self_strengths=?,self_issues=?,self_causes=?,self_proposals=?,closed_at=?,classification_locked=1,progress_score=?,quality_score=NULL,week_score=NULL,week_grade=NULL,score_gap_reason=NULL,quality_fallback=0,updated_at=? WHERE id=?""",
                            (int(self_score), strengths.strip(), issues.strip(), causes.strip(), proposals.strip(), ts, float(progress), ts, int(plan["id"])),
                        )
                        c.execute("UPDATE weekly_plan_items SET classification_locked=1 WHERE plan_id=?", (int(plan["id"]),))
                        c.execute("INSERT INTO weekly_performance_audit(plan_id,actor_user_id,action,detail,created_at) VALUES(?,?, 'SELF_CLOSE', ?, ?)", (int(plan["id"]), uid, json.dumps({"self_score": int(self_score), "progress_score": progress}, ensure_ascii=False), ts))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(NULL,?,'PLAN_CLOSE_PHASE2',?,?)", (uid, f"week={ws.isoformat()}", ts))
                        leader = policy._leader_for_staff(c, uid)
                        if leader and int(leader) != uid:
                            policy._notify(c, int(leader), "📝 Có tuần chờ nhận xét", f"{policy._uget(u, 'full_name') or policy._uget(u, 'username')} đã chốt tuần {ws:%d/%m/%Y}.")
                    st.toast("Đã chốt tuần và gửi Trưởng phòng nhận xét.", icon="✅")
                    st.rerun()
        return

    st.divider()
    st.markdown("### 📝 Kết quả tuần")
    _score_cards(st, metrics, plan)
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Tự đánh giá**")
        st.write(f"Điểm: {int(float(plan.get('self_score') or 0))}/5")
        st.caption("Mặt được"); st.write(plan.get("self_strengths") or "—")
        st.caption("Tồn tại"); st.write(plan.get("self_issues") or "—")
    with c2:
        st.write("**Nguyên nhân / Đề xuất**")
        st.caption("Nguyên nhân"); st.write(plan.get("self_causes") or "—")
        st.caption("Đề xuất"); st.write(plan.get("self_proposals") or "—")
    if status == "DA_CHOT":
        st.info("Kế hoạch đã chốt và chỉ đọc; đang chờ Trưởng phòng nhận xét/chấm điểm.")
    elif status == "DA_DANH_GIA":
        st.success(f"Trưởng phòng: {int(float(plan.get('leader_score') or 0))}/5 · {plan.get('leader_comment') or 'Không có nhận xét'}")
        if int(plan.get("quality_fallback") or 0):
            st.warning("Điểm chất lượng đang dùng tự chấm do quá thời hạn 5 ngày làm việc mà chưa có nhận xét lãnh đạo.")


def _plan_metrics(c, plan):
    items = _load_items(c, int(plan["id"]))
    return _metrics(items)


def _render_manager_reviews(st, u, policy, weekly_core, get_conn, logger=None):
    if not policy._manager(u):
        return
    uid = int(policy._uget(u, "id")); admin = policy._is_admin(u)
    with get_conn() as c:
        rows = [dict(r) for r in c.execute(
            """SELECT p.*,u.full_name,u.role FROM weekly_plans p JOIN users u ON u.id=p.user_id
               WHERE p.workflow_status='DA_CHOT' ORDER BY p.week_start DESC,u.full_name"""
        ).fetchall()]
        rows = [p for p in rows if policy._direct_scope_ok(c, uid, int(p["user_id"]), admin)]
    st.markdown("## ⭐ Chấm điểm / nhận xét tuần")
    if not rows:
        st.caption("Không có tuần nào đang chờ nhận xét của Trưởng phòng.")
        return
    for p in rows:
        ws = _parse_date(p.get("week_start")) or date.today()
        with get_conn() as c:
            metrics = _plan_metrics(c, p)
        with st.expander(f"{p.get('full_name')} · tuần {ws:%d/%m/%Y} · tự chấm {int(float(p.get('self_score') or 0))}/5", expanded=False):
            _score_cards(st, metrics, p)
            a, b = st.columns(2)
            with a:
                st.caption("Mặt được"); st.write(p.get("self_strengths") or "—")
                st.caption("Tồn tại, hạn chế"); st.write(p.get("self_issues") or "—")
            with b:
                st.caption("Nguyên nhân"); st.write(p.get("self_causes") or "—")
                st.caption("Đề xuất"); st.write(p.get("self_proposals") or "—")
            manager_score = st.select_slider("Điểm chất lượng Trưởng phòng *", options=[1,2,3,4,5], value=3, format_func=lambda z: SELF_LEVELS[z], key=f"p2_mgr_score_{p['id']}")
            comment = st.text_area("Nhận xét Trưởng phòng *", max_chars=1000, key=f"p2_mgr_comment_{p['id']}")
            self_score = int(round(float(p.get("self_score") or 0)))
            gap = abs(int(manager_score) - self_score)
            gap_reason = ""
            if gap >= 2:
                st.warning("Chênh lệch tự chấm và lãnh đạo từ 2 điểm trở lên: bắt buộc ghi lý do.")
                gap_reason = st.text_area("Lý do chênh lệch điểm *", max_chars=500, key=f"p2_gap_{p['id']}")
            if st.button("⭐ Xác nhận kết quả tuần", key=f"p2_eval_{p['id']}", type="primary", use_container_width=True):
                if not comment.strip():
                    st.error("Vui lòng nhập nhận xét Trưởng phòng.")
                    continue
                if gap >= 2 and not gap_reason.strip():
                    st.error("Vui lòng nhập lý do chênh lệch điểm.")
                    continue
                progress = metrics["progress"]
                quality = _quality(self_score, manager_score)
                week_score = _week_score(progress, quality)
                grade = _grade(week_score)
                ts = _now()
                with get_conn() as c:
                    c.execute(
                        """UPDATE weekly_plans SET workflow_status='DA_DANH_GIA',leader_score=?,leader_comment=?,score_gap_reason=?,progress_score=?,quality_score=?,week_score=?,week_grade=?,quality_fallback=0,evaluated_at=?,evaluated_by=?,classification_locked=1,updated_at=? WHERE id=?""",
                        (int(manager_score), comment.strip(), gap_reason.strip(), float(progress), float(quality), float(week_score), grade, ts, uid, ts, int(p["id"])),
                    )
                    c.execute("UPDATE weekly_plan_items SET classification_locked=1 WHERE plan_id=?", (int(p["id"]),))
                    c.execute("INSERT INTO weekly_performance_audit(plan_id,actor_user_id,action,detail,created_at) VALUES(?,?, 'MANAGER_REVIEW', ?, ?)", (int(p["id"]), uid, json.dumps({"manager_score": int(manager_score), "quality_score": quality, "week_score": week_score, "grade": grade, "gap_reason": gap_reason.strip()}, ensure_ascii=False), ts))
                    policy._notify(c, int(p["user_id"]), "🏁 Kết quả tuần đã có", f"Tuần {ws:%d/%m/%Y}: {week_score:.2f}/100 · {grade}.")
                st.toast("Đã xác nhận kết quả tuần.", icon="✅")
                st.rerun()


def _history_rows(c, uid, limit=8):
    plans = [dict(r) for r in c.execute(
        """SELECT * FROM weekly_plans WHERE user_id=? AND workflow_status IN ('DA_CHOT','DA_DANH_GIA')
           ORDER BY week_start DESC LIMIT ?""",
        (int(uid), int(limit)),
    ).fetchall()]
    rows = []
    for p in plans:
        m = _plan_metrics(c, p)
        week_score = p.get("week_score")
        if week_score is None and p.get("self_score") and int(p.get("quality_fallback") or 0):
            quality = _quality(p.get("self_score"), fallback=True)
            week_score = _week_score(m["progress"], quality)
        rows.append({"plan": p, "metrics": m, "week_score": week_score})
    return rows


def _render_personal_performance(st, u, policy, weekly_core, get_conn):
    if policy._manager(u):
        return
    uid = int(policy._uget(u, "id"))
    with get_conn() as c:
        rows = _history_rows(c, uid, 8)
    with st.expander("📈 Hiệu quả 8 tuần", expanded=False):
        if not rows:
            st.caption("Chưa có tuần đã chốt để tổng hợp.")
            return
        latest = rows[0]
        p = latest["plan"]; m = latest["metrics"]
        _score_cards(st, m, p)
        table = []
        for r in rows:
            pp, mm = r["plan"], r["metrics"]
            table.append({
                "Tuần": _dmy(pp.get("week_start")),
                "Trạng thái": policy.PLAN_STATUS.get(pp.get("workflow_status"), pp.get("workflow_status")),
                "Hoàn thành": f"{mm['completion_rate']:.0f}%",
                "Đúng hạn": f"{mm['ontime_rate']:.0f}%",
                "Q2 (số việc)": f"{mm['q2_ratio']:.0f}%",
                "Điểm tuần": "—" if r["week_score"] is None else f"{float(r['week_score']):.2f}",
                "Xếp loại": pp.get("week_grade") or ("—" if r["week_score"] is None else _grade(r["week_score"])),
            })
        st.dataframe(table, use_container_width=True, hide_index=True)
        reviewed = [r for r in rows if r["plan"].get("leader_comment")]
        if reviewed:
            st.markdown("**Nhận xét gần nhất của lãnh đạo**")
            for r in reviewed[:4]:
                st.caption(f"Tuần {_dmy(r['plan'].get('week_start'))}")
                st.write(r["plan"].get("leader_comment"))


def _render_room_performance(st, u, policy, weekly_core, get_conn):
    if not policy._manager(u):
        return
    leader_uid = int(policy._uget(u, "id")); admin = policy._is_admin(u)
    cutoff = (date.today() - timedelta(weeks=8)).isoformat()
    with get_conn() as c:
        users = [dict(r) for r in c.execute("SELECT id,full_name,role FROM users WHERE active=1 ORDER BY full_name").fetchall()]
        users = [x for x in users if str(x.get("role") or "") not in {"Lãnh đạo phòng"} and policy._direct_scope_ok(c, leader_uid, int(x["id"]), admin)]
        output = []
        for person in users:
            rows = _history_rows(c, int(person["id"]), 8)
            all_recent = [dict(r) for r in c.execute("SELECT * FROM weekly_plans WHERE user_id=? AND week_start>=? ORDER BY week_start DESC LIMIT 8", (int(person["id"]), cutoff)).fetchall()]
            latest_plan = all_recent[0] if all_recent else None
            scores = [float(r["week_score"]) for r in rows if r["week_score"] is not None]
            comp = [r["metrics"]["completion_rate"] for r in rows]
            q2 = [r["metrics"]["q2_ratio"] for r in rows]
            output.append({
                "Cán bộ": person["full_name"],
                "Trạng thái gần nhất": "Chưa có kế hoạch" if not latest_plan else policy.PLAN_STATUS.get(latest_plan.get("workflow_status"), latest_plan.get("workflow_status")),
                "Điểm TB 8 tuần": "—" if not scores else f"{sum(scores)/len(scores):.1f}",
                "Hoàn thành TB": "—" if not comp else f"{sum(comp)/len(comp):.0f}%",
                "Q2 TB (số việc)": "—" if not q2 else f"{sum(q2)/len(q2):.0f}%",
                "Số tuần đã đánh giá": len(scores),
            })
    st.markdown("## 📊 Hiệu quả công việc 8 tuần")
    st.caption("Chỉ số Q2 đang tính theo **số công việc**, không theo giờ, để giữ đúng thiết kế hiện tại không yêu cầu cán bộ nhập giờ.")
    if not output:
        st.caption("Chưa có dữ liệu cán bộ để tổng hợp.")
        return
    st.dataframe(output, use_container_width=True, hide_index=True)
    buff = io.StringIO()
    writer = csv.DictWriter(buff, fieldnames=list(output[0].keys()))
    writer.writeheader(); writer.writerows(output)
    st.download_button("⬇ Xuất CSV tổng hợp 8 tuần", data=buff.getvalue().encode("utf-8-sig"), file_name=f"KHDN_hieu_qua_8_tuan_{date.today():%Y%m%d}.csv", mime="text/csv", use_container_width=True)


def install(policy, weekly_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return

    original_staff = policy._render_staff_week
    def render_staff_week(st, u, core, get_conn, ws, plan, items, focus_rows, logger=None, logger_arg=None, **kwargs):
        _ensure_schema(policy, weekly_core, get_conn, logger or logger_arg)
        status = str(plan.get("workflow_status") or "NHAP")
        if status in {"DA_DUYET", "DA_CHOT", "DA_DANH_GIA"}:
            # Reload so newly added Phase-2 columns are available in dict rows.
            with get_conn() as c:
                fresh_plan = dict(c.execute("SELECT * FROM weekly_plans WHERE id=?", (int(plan["id"]),)).fetchone())
                fresh_items = _load_items(c, int(plan["id"]))
            return _render_execution_and_review(st, u, policy, weekly_core, get_conn, ws, fresh_plan, fresh_items, focus_rows, logger or logger_arg)
        return original_staff(st, u, core, get_conn, ws, plan, items, focus_rows, logger=logger or logger_arg, **kwargs)
    policy._render_staff_week = render_staff_week

    # Staff landing remains Today: append an 8-week performance block only.
    original_today = customer_ui.render_today_page
    def render_today_page(st, u, get_conn, page_title=None, logger=None, **kwargs):
        _ensure_schema(policy, weekly_core, get_conn, logger)
        detail_before = bool(st.session_state.get("cw_case_id"))
        result = original_today(st, u, get_conn, page_title=page_title, logger=logger, **kwargs)
        if not detail_before and not st.session_state.get("cw_case_id"):
            _render_personal_performance(st, u, policy, weekly_core, get_conn)
        return result
    customer_ui.render_today_page = render_today_page

    # Room dashboard's approval center is deliberately last. Put Phase-2 review
    # and analytics immediately before it so the earlier UX contract stays true.
    original_approval_center = room_dashboard._render_approval_center
    def approval_center(st, u, policy_arg, weekly_core_arg, customer_core, customer_ui_arg, get_conn, logger=None):
        _ensure_schema(policy, weekly_core, get_conn, logger)
        _render_manager_reviews(st, u, policy, weekly_core, get_conn, logger)
        _render_room_performance(st, u, policy, weekly_core, get_conn)
        return original_approval_center(st, u, policy_arg, weekly_core_arg, customer_core, customer_ui_arg, get_conn, logger)
    room_dashboard._render_approval_center = approval_center

    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info("WEEKLY_PERFORMANCE_PHASE2_INSTALLED version=%s no_hours=1 review_1_5=1 scoring=1 personal_8w=1 room_8w=1", VERSION)
