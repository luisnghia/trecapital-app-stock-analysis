from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3
import tempfile

from khdn_apps import planning_operational_phase13_patch as p13

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_operational_phase13_patch.py").read_text(encoding="utf-8")
shim = (ROOT / "planning_operational_phase10_fix.py").read_text(encoding="utf-8")

board_segment = src[src.index("def _single_week_board"):src.index("def _install_single_week_board")]
form_segment = src[src.index("def _install_weekly_add_form"):src.index("def _install_approved_progress_top")]
progress_segment = src[src.index("def _install_approved_progress_top"):src.index("def _pending_week_cancel_rows")]
export_segment = src[src.index("def _install_room_export_bottom"):src.index("def install(")]

checks = {
    "phase13_after_phase12": "phase13.install" in shim and shim.find("phase13.install") > shim.find("phase12.install"),
    "single_weekday_row": "p13-day-strip" in board_segment and "p6-day-head" not in board_segment and "p3-day-head" not in board_segment,
    "top_row_counts": "_weekday_strip(ws, live)" in board_segment and "{counts[idx]} việc" in src,
    "quick_add_sets_exact_day": "_open_quick_add(st, ws, d, status)" in board_segment,
    "form_hidden_without_gate": 'if not gate or not selected_day_raw:' in form_segment,
    "clicked_day_readonly": '"Ngày thực hiện *"' in form_segment and "disabled=True" in form_segment and "selected_day" in form_segment,
    "autoclose_clears_session": "_clear_add_state(st.session_state, ws)" in form_segment,
    "optional_case_link": "Liên kết Công việc khách hàng (không bắt buộc)" in form_segment,
    "manual_title_always": 'st.text_input(\n            "Công việc *"' in form_segment,
    "no_case_required_error": 'missing.append("Công việc đang xử lý")' not in form_segment,
    "source_priority_inherited": "priority_quadrant=?" in form_segment and "source_q" in form_segment,
    "source_q4_no_questions": "_classification_from_source(q)" in form_segment and "_focus_picker" in form_segment,
    "progress_before_board": progress_segment.find("phase2._score_cards") < progress_segment.find("p3week.render_week_board"),
    "no_generic_emergent_button": "Thêm công việc mới trong tuần" not in progress_segment,
    "export_bottom": "_p13_defer_room_export" in export_segment and export_segment.find("current_dashboard(") < export_segment.find("actual_export(st, get_conn"),
    "four_waiting_tabs": all(x in src for x in [
        "✅ Phê duyệt kế hoạch / dời hạn", "🔄 Cập nhật tiến độ / vướng mắc",
        "🗑 Hủy kế hoạch tuần", "🗑 Hủy công việc KH",
    ]),
    "weekly_cancel_detached": "_P13_WEEK_CANCEL_DETACHED" in src,
    "waiting_pulse": "p13AttentionPulse" in src and "prefers-reduced-motion" in src,
    "runtime_logs": all(x in src for x in [
        "P13_WEEK_BOARD_INSTALLED", "P13_WEEK_ADD_FORM_INSTALLED",
        "P13_APPROVED_PROGRESS_TOP_INSTALLED", "P13_WAITING_TABS_INSTALLED",
        "P13_ROOM_EXPORT_BOTTOM_INSTALLED", "PLANNING_OPERATIONAL_PHASE13_INSTALLED",
    ]),
}

bad = [k for k, v in checks.items() if not v]
if bad:
    raise SystemExit(f"PLANNING_OPERATIONAL_PHASE13_QA_FAIL {bad} {checks}")

# Semantic: the upper strip counts only non-cancelled Monday-Friday work.
ws = date(2026, 9, 28)
assert p13._day_counts(ws, [
    {"work_date": "2026-09-28", "status": "PLANNED"},
    {"work_date": "2026-09-28", "status": "DONE"},
    {"work_date": "2026-09-29", "status": "PLANNED"},
    {"work_date": "2026-09-30", "status": "CANCELLED"},
]) == [2, 1, 0, 0, 0]
strip = p13._weekday_strip(ws, [{"work_date": "2026-09-30", "status": "PLANNED"}])
assert strip.count("p13-day") >= 5 and "1 việc" in strip

# Semantic: legacy and Phase-13 quick-add gates are all removed together.
state = {
    f"wp_add_open_{ws.isoformat()}": True,
    f"wp_quick_day_{ws.isoformat()}": "2026-09-30",
    f"p3_emergent_open_{ws.isoformat()}": True,
    p13._add_day_key(ws): "2026-09-30",
    "other": 1,
}
p13._clear_add_state(state, ws)
assert state == {"other": 1}, state

# Semantic: a linked source quadrant is authoritative. In particular Q4 maps
# to classifier flags that force Q4 without asking risk/focus questions.
assert p13._classification_from_source(1) == (True, True)
assert p13._classification_from_source(2) == (None, None)
assert p13._classification_from_source(3) == (True, False)
assert p13._classification_from_source(4) == (False, None)

leaders = [{"id": 8, "full_name": "Lãnh đạo"}]
focus = [{"id": 31, "legacy_category_id": 14, "code": "TT14", "name": "Trọng tâm"}]
due, leader, mapped, q = p13._source_defaults({
    "expected_complete_at": "2026-10-15 17:00:00",
    "controller_user_id": 8,
    "important_category_id": None,
    "priority_quadrant": 4,
}, leaders, focus)
assert due.isoformat() == "2026-10-15" and leader["id"] == 8 and mapped is None and q == 4

due2, leader2, mapped2, q2 = p13._source_defaults({
    "expected_complete_at": "2026-10-08",
    "controller_user_id": 8,
    "important_category_id": 14,
    "priority_quadrant": 2,
}, leaders, focus)
assert mapped2["id"] == 31 and q2 == 2

# Semantic: the customer-work case query exposes the stored priority so Weekly
# Plan can inherit Q4 rather than reclassify it.
with tempfile.TemporaryDirectory(prefix="p13-case-qa-") as td:
    db = Path(td) / "qa.db"
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE customer_work_cases(
            id INTEGER PRIMARY KEY,case_code TEXT,title TEXT,case_type TEXT,
            customer_id INTEGER,owner_user_id INTEGER,expected_complete_at TEXT,
            controller_user_id INTEGER,important_category_id INTEGER,
            priority_quadrant INTEGER,status TEXT,current_stage_id INTEGER
        );
        CREATE TABLE work_stage_catalog(id INTEGER PRIMARY KEY,name TEXT);
        CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT);
        INSERT INTO users VALUES(1,'CB A');
        INSERT INTO users VALUES(8,'Lãnh đạo');
        INSERT INTO work_stage_catalog VALUES(3,'Đang tiếp cận khách hàng');
        INSERT INTO customer_work_cases VALUES(
            41,'CVKH-2026-0041','Tiếp thị gửi tiền','Dịch vụ',9,1,'2026-10-15',8,NULL,4,'ACTIVE',3
        );
        """
    )
    rows = p13._case_rows(c, 9, 1, False)
    assert len(rows) == 1 and int(rows[0]["priority_quadrant"]) == 4
    c.close()

print(
    "PLANNING_OPERATIONAL_PHASE13_QA_PASS",
    checks,
    "single_week_row=PASS hidden_add=PASS q4_inheritance=PASS progress_top=PASS export_bottom=PASS four_tabs=PASS",
)
