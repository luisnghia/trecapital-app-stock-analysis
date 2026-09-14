"""Static/semantic QA for task Note visibility on all task action/detail screens."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from khdn_apps.mobile_nav_patch import patch_source as mobile_patch
from khdn_apps.reason_categories_patch import patch_source as reason_patch
from khdn_apps.task_note_visibility_patch import patch_source as note_patch


def main():
    root = Path(__file__).resolve().parent
    source = (root / "app_v223_source.py").read_text(encoding="utf-8")
    transformed = note_patch(reason_patch(mobile_patch(source)))

    checks = {
        "central_note_renderer": '📝 **Ghi chú / yêu cầu xử lý**' in transformed and 'note_text = str(note_value or "").strip()' in transformed,
        "empty_note_message": 'Ghi chú / yêu cầu xử lý: Không có ghi chú.' in transformed,
        "receive_uses_common_renderer": 'selectable_task_table(waiting,"accept_task_table"' in transformed and 'render_task_chips(row,time_label="Giao",time_field="assigned_at")' in transformed,
        "receive_duplicate_removed": 'if row.note: st.caption(f"Ghi chú: {row.note}")' not in transformed,
        "work_uses_common_renderer": 'selectable_task_table(active,"finish_task_table"' in transformed and 'render_task_chips(row,time_label="Bắt đầu",time_field="start_time")' in transformed,
        "review_uses_common_renderer": 'selectable_task_table(pending,"eval_task_table"' in transformed and 'render_task_chips(row,time_label="Kết thúc",time_field="end_time")' in transformed,
        "review_duplicate_removed": ' · Ghi chú: {row.note}' not in transformed,
        "returned_qlkh_uses_common_renderer": 'selectable_task_table(returned_df,"qlkh_returned_table"' in transformed and 'def _manage_assignment(rsel, key_prefix):' in transformed and 'render_task_chips(rsel,time_label="Giao",time_field="assigned_at")' in transformed,
        "qlkh_tracking_uses_common_renderer": 'selectable_task_table(ordered,"qlkh_assigned_table"' in transformed,
        "leader_returned_uses_common_renderer": 'selectable_task_table(rt,"leader_returned_table"' in transformed and 'render_task_chips(rr,time_label="CBHT trả lại",time_field="returned_to_qlkh_at")' in transformed,
        "leader_active_uses_common_renderer": 'selectable_task_table(ordered,"leader_manage_table"' in transformed and 'render_task_chips(r,time_label="Giao",time_field="assigned_at")' in transformed,
        "history_detail_has_note": 't.assigned_at,t.start_time,t.end_time,t.closed_time,t.note,t.status,t.current_round,t.rework_count' in transformed,
    }
    try:
        compile(transformed, str(root / "app_v223_source.py"), "exec")
        checks["transformed_source_compiles"] = True
    except Exception:
        checks["transformed_source_compiles"] = False

    failed = [k for k, v in checks.items() if not v]
    msg = "KHDN_TASK_NOTE_VISIBILITY_QA " + repr(checks)
    print(msg, flush=True)
    if failed:
        raise SystemExit("FAIL: " + ", ".join(failed))


if __name__ == "__main__":
    main()
