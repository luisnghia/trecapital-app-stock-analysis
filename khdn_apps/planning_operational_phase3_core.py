"""Operational planning Phase 3 core: realtime token, leader attention events, detail UX."""
from __future__ import annotations

from datetime import date, datetime
import html
import inspect
import json
import os
import re

from khdn_apps import planning_final_ux_patch as finalux


def esc(v):
    return html.escape("—" if v is None or v == "" else str(v))


def dmy(v):
    if not v:
        return "—"
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        try:
            return date.fromisoformat(str(v)[:10]).strftime("%d/%m/%Y")
        except Exception:
            return str(v)


def dt(v):
    if not v:
        return "—"
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(v)


def ensure_schema(get_conn, logger=None):
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS planning_attention_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            case_id INTEGER NOT NULL,
            actor_user_id INTEGER,
            title TEXT NOT NULL,
            detail TEXT,
            severity TEXT NOT NULL DEFAULT 'INFO',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            acknowledged_at TEXT,
            acknowledged_by INTEGER,
            acknowledgement_note TEXT,
            status TEXT NOT NULL DEFAULT 'OPEN',
            UNIQUE(event_type,source_id)
        );
        CREATE INDEX IF NOT EXISTS idx_pae_status_created ON planning_attention_events(status,created_at);
        CREATE INDEX IF NOT EXISTS idx_pae_case ON planning_attention_events(case_id,created_at);
        """)
    if logger:
        logger.info("PLANNING_OPERATIONAL_PHASE3_SCHEMA_READY")


def _event_insert(get_conn, event_type, source_id, case_id, actor_uid, title, detail, severity, logger=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_conn() as c:
            c.execute("""INSERT OR IGNORE INTO planning_attention_events(
                event_type,source_id,case_id,actor_user_id,title,detail,severity,created_at,updated_at,status)
                VALUES(?,?,?,?,?,?,?,?,?,'OPEN')""",
                (event_type, int(source_id), int(case_id), int(actor_uid) if actor_uid else None,
                 str(title), json.dumps(detail, ensure_ascii=False), str(severity or "INFO"), ts, ts))
    except Exception:
        if logger:
            logger.exception("PLANNING_ATTENTION_EVENT_INSERT_FAILED type=%s source=%s", event_type, source_id)


def install_realtime_token(app_ns, get_conn, logger=None):
    original = app_ns.get("_visible_task_change_token")
    if not callable(original) or app_ns.get("_PLANNING_REALTIME_TOKEN_V3"):
        return

    def visible_change_token(u):
        base = str(original(u))
        parts = []
        try:
            with get_conn() as c:
                tables = {str(r[0]) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                specs = [
                    ("customer_work_cases", "updated_at"), ("case_actions", "created_at"),
                    ("case_stage_history", "created_at"), ("case_issues", "opened_at"),
                    ("case_reschedule_requests", "requested_at"), ("weekly_plans", "updated_at"),
                    ("weekly_plan_items", "updated_at"), ("weekly_plan_actions", "created_at"),
                    ("weekly_plan_reschedule_requests", "requested_at"), ("planning_attention_events", "updated_at"),
                ]
                for table, col in specs:
                    if table not in tables:
                        parts.append("-")
                        continue
                    row = c.execute(f"SELECT COALESCE(MAX(id),0),COALESCE(MAX({col}),'') FROM {table}").fetchone()
                    parts.append(f"{row[0]}:{row[1]}")
        except Exception:
            if logger:
                logger.exception("PLANNING_REALTIME_TOKEN_FAILED")
        return base + "|PLN|" + "|".join(parts)

    app_ns["_visible_task_change_token"] = visible_change_token
    app_ns["_PLANNING_REALTIME_TOKEN_V3"] = True
    if logger:
        logger.info("PLANNING_REALTIME_TOKEN_V3_INSTALLED")


def install_event_wrappers(customer_core, logger=None):
    if getattr(customer_core, "_PLANNING_EVENT_WRAPPERS_V3", False):
        return
    original_change_stage = customer_core.change_stage
    original_add_issue = customer_core.add_issue
    original_resolve_issue = customer_core.resolve_issue

    def change_stage(get_conn, case_id, actor_uid, new_stage_id, note=None, logger=None):
        note_text = str(note or "").strip()
        if not note_text:
            raise ValueError("Bắt buộc nhập Ghi chú chuyển bước trước khi cập nhật tiến độ")
        old_stage, title = "—", "Công việc khách hàng"
        with get_conn() as c:
            r = c.execute("""SELECT s.name,c.customer_name,w.title FROM customer_work_cases w
                JOIN customers c ON c.id=w.customer_id LEFT JOIN work_stage_catalog s ON s.id=w.current_stage_id
                WHERE w.id=?""", (int(case_id),)).fetchone()
            if r:
                old_stage = str(r[0] or "—")
                title = f"{r[1] or 'Khách hàng'} · {r[2] or 'Công việc'}"
        ok = original_change_stage(get_conn, case_id, actor_uid, new_stage_id, note_text, logger)
        if ok:
            with get_conn() as c:
                h = c.execute("""SELECT h.id,s.name FROM case_stage_history h
                    LEFT JOIN work_stage_catalog s ON s.id=h.stage_id WHERE h.case_id=? ORDER BY h.id DESC LIMIT 1""",
                    (int(case_id),)).fetchone()
            if h:
                _event_insert(get_conn, "STAGE_CHANGE", h[0], case_id, actor_uid, title,
                              {"from_stage": old_stage, "to_stage": h[1] or "—", "note": note_text}, "INFO", logger)
        return ok

    def add_issue(get_conn, case_id, actor_uid, issue_text, severity="MEDIUM", logger=None):
        issue_id = original_add_issue(get_conn, case_id, actor_uid, issue_text, severity, logger)
        if issue_id:
            with get_conn() as c:
                r = c.execute("""SELECT c.customer_name,w.title,s.name FROM customer_work_cases w
                    JOIN customers c ON c.id=w.customer_id LEFT JOIN work_stage_catalog s ON s.id=w.current_stage_id
                    WHERE w.id=?""", (int(case_id),)).fetchone()
            title = f"{r[0] or 'Khách hàng'} · {r[1] or 'Công việc'}" if r else "Công việc khách hàng"
            _event_insert(get_conn, "ISSUE_OPEN", issue_id, case_id, actor_uid, title,
                          {"issue": str(issue_text or "").strip(), "stage": r[2] if r else None}, severity, logger)
        return issue_id

    def resolve_issue(get_conn, issue_id, actor_uid, resolution_text=None, logger=None):
        ok = original_resolve_issue(get_conn, issue_id, actor_uid, resolution_text, logger)
        if ok:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_conn() as c:
                c.execute("UPDATE planning_attention_events SET updated_at=? WHERE event_type='ISSUE_OPEN' AND source_id=?",
                          (ts, int(issue_id)))
        return ok

    customer_core.change_stage = change_stage
    customer_core.add_issue = add_issue
    customer_core.resolve_issue = resolve_issue
    customer_core._PLANNING_EVENT_WRAPPERS_V3 = True
    if logger:
        logger.info("PLANNING_EVENT_WRAPPERS_V3_INSTALLED")


class StageNoteProxy:
    def __init__(self, st, case_id):
        self._st = st
        self.case_id = int(case_id)
        self.note_key = f"cw_stage_note_{self.case_id}"
        self.invalid_key = f"cw_stage_note_invalid_{self.case_id}"

    def __getattr__(self, name):
        return getattr(self._st, name)

    def text_input(self, label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        if key == self.note_key and self._st.session_state.get(self.invalid_key):
            finalux._missing_css(self._st, [self.note_key])
        return self._st.text_input(label, *args, **kwargs)

    def button(self, label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        clicked = self._st.button(label, *args, **kwargs)
        if clicked and key == f"cw_stage_save_{self.case_id}":
            note = str(self._st.session_state.get(self.note_key) or "").strip()
            if not note:
                self._st.session_state[self.invalid_key] = True
                finalux._missing_css(self._st, [self.note_key])
                self._st.error("Bắt buộc nhập **Ghi chú chuyển bước** trước khi cập nhật tiến độ.")
                return False
            self._st.session_state.pop(self.invalid_key, None)
        return clicked


def _detail_highlights(st, customer_core, get_conn, case_id):
    with get_conn() as c:
        stages = [dict(r) for r in c.execute("""SELECT h.started_at,h.note,s.name stage_name,u.full_name actor_name
            FROM case_stage_history h LEFT JOIN work_stage_catalog s ON s.id=h.stage_id LEFT JOIN users u ON u.id=h.actor_user_id
            WHERE h.case_id=? ORDER BY h.id DESC LIMIT 6""", (int(case_id),)).fetchall()]
        issues = [dict(r) for r in c.execute("""SELECT i.*,s.name stage_name,u.full_name actor_name
            FROM case_issues i LEFT JOIN work_stage_catalog s ON s.id=i.stage_id LEFT JOIN users u ON u.id=i.opened_by
            WHERE i.case_id=? ORDER BY i.id DESC LIMIT 6""", (int(case_id),)).fetchall()]
    if not stages and not issues:
        return
    st.markdown("### 🔔 Chuyển đổi / vướng mắc nổi bật")
    cards = []
    for h in stages:
        cards.append((str(h.get("started_at") or ""), f"""<div class='p3-activity p3-stage'>
        <div class='p3-act-title'>🔄 CHUYỂN BƯỚC → {esc(h.get('stage_name'))}</div>
        <div><b>{esc(h.get('actor_name'))}</b> · {esc(dt(h.get('started_at')))}</div>
        <div class='p3-act-note'>📝 {esc(h.get('note') or '—')}</div></div>"""))
    for i in issues:
        resolved = bool(i.get("resolved_at"))
        cls, state = ("p3-resolved", "ĐÃ XỬ LÝ") if resolved else ("p3-issue", "VƯỚNG MẮC ĐANG MỞ")
        detail = (" · " + esc(i.get("resolution_text"))) if resolved and i.get("resolution_text") else ""
        cards.append((str(i.get("opened_at") or ""), f"""<div class='p3-activity {cls}'>
        <div class='p3-act-title'>⚠ {state} · {esc(customer_core.SEVERITY_LABEL.get(i.get('severity'), i.get('severity')))}</div>
        <div><b>{esc(i.get('issue_text'))}</b></div><div>{esc(i.get('stage_name'))} · {esc(i.get('actor_name'))} · {esc(dt(i.get('opened_at')))}{detail}</div></div>"""))
    cards.sort(key=lambda z: z[0], reverse=True)
    st.html("".join(v for _, v in cards[:10]) + """<style>
    .p3-activity{padding:10px 12px;border-radius:10px;margin:7px 0;font-size:.84rem;line-height:1.4;white-space:normal;overflow-wrap:anywhere}
    .p3-act-title{font-weight:950;font-size:.90rem;margin-bottom:4px}.p3-act-note{margin-top:4px;font-weight:800}
    .p3-stage{border:1px solid #F4B41A;border-left:6px solid #F4B41A;background:rgba(244,180,26,.11);color:#FFD166}
    .p3-issue{border:1px solid #F04438;border-left:6px solid #F04438;background:rgba(240,68,56,.12);color:#FF8A80}
    .p3-resolved{border:1px solid #12B76A;border-left:6px solid #12B76A;background:rgba(18,183,106,.10);color:#63DCCB}</style>""")


def install_case_detail(customer_ui, customer_core, logger=None):
    if getattr(customer_ui, "_P3_CASE_DETAIL", False):
        return
    original = customer_ui._case_detail

    def case_detail(st, u, get_conn, case_id, logger=None):
        result = original(StageNoteProxy(st, case_id), u, get_conn, case_id, logger)
        try:
            _detail_highlights(st, customer_core, get_conn, case_id)
        except Exception:
            if logger:
                logger.exception("P3_DETAIL_HIGHLIGHTS_FAILED case=%s", case_id)
        return result

    customer_ui._case_detail = case_detail
    customer_ui._P3_CASE_DETAIL = True


def install_unique_card_context(logger=None):
    def render_context():
        skip = {"planning_final_ux_patch.py", "planning_usability_v3_patch.py", "planning_ui_v4_patch.py", "planning_week_board_focus_patch.py"}
        try:
            for frame in inspect.stack()[2:]:
                name = os.path.basename(frame.filename)
                if name in skip:
                    continue
                return re.sub(r"[^A-Za-z0-9_]+", "_", f"{name}_{frame.function}_{frame.lineno}")
        except Exception:
            pass
        return "p3_default"
    finalux._render_context = render_context
    if logger:
        logger.info("PLANNING_UNIQUE_CARD_CONTEXT_V3_INSTALLED")
