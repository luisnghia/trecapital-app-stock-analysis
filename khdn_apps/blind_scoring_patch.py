"""Build-time privacy patch for independent QLKH scoring.

Goals:
- QLKH keeps operational statistics and may review scores they personally gave.
- QLKH never sees CBHT scores originating from other QLKH.
- Admin / Lanh dao retain full scoring visibility.
- CBHT behavior is unchanged.

The repository keeps the large application engine in app_v223_source.py. This
script patches that source inside the Railway image before runtime so the change
is isolated, auditable, and does not alter persistent business data.
"""
from pathlib import Path
import re


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Blind-scoring patch cannot find: {label}")
    return text.replace(old, new, 1)


def install() -> None:
    source_path = Path(__file__).resolve().parent / "app_v223_source.py"
    text = source_path.read_text(encoding="utf-8")

    # 1) Carry the evaluator identity into Dashboard data. This does not expose
    # it in UI; it is used only to mask score fields for QLKH viewers.
    if "e.evaluator_user_id,e.quality_score,e.progress_score,e.comment," not in text:
        text = _replace_once(
            text,
            "              e.quality_score,e.progress_score,e.comment,\n              CASE WHEN t.end_time IS NOT NULL THEN ((julianday(t.end_time)-julianday(t.start_time))*24.0) ELSE NULL END duration_hours",
            "              e.evaluator_user_id,e.quality_score,e.progress_score,e.comment,\n              CASE WHEN t.end_time IS NOT NULL THEN ((julianday(t.end_time)-julianday(t.start_time))*24.0) ELSE NULL END duration_hours",
            "visible_tasks_sql evaluator identity",
        )

    # 2) Blind scoring at the Dashboard data boundary. Operational columns stay
    # intact. Only evaluator-derived score columns from other QLKH are nulled.
    dashboard_anchor = "    df = _room_tasks_frame()\n    if df.empty:\n"
    dashboard_replacement = """    df = _room_tasks_frame()\n\n    # Blind scoring: a normal QLKH may see only scores that they personally\n    # submitted. Counts, values, durations, statuses, rework and all other\n    # operational metrics remain room-wide/personal exactly as before.\n    _blind_qlkh = qlkh_view and not bool(u[\"is_admin\"])\n    if _blind_qlkh and not df.empty:\n        if \"evaluator_user_id\" not in df.columns:\n            raise RuntimeError(\"Blind scoring requires evaluator_user_id in Dashboard data\")\n        _own_eval_mask = pd.to_numeric(df[\"evaluator_user_id\"], errors=\"coerce\").eq(int(u[\"id\"]))\n        for _score_col in (\"quality_score\", \"progress_score\", \"avg_score\"):\n            if _score_col in df.columns:\n                df.loc[~_own_eval_mask, _score_col] = pd.NA\n\n    if df.empty:\n"""
    if "_blind_qlkh = qlkh_view and not bool(u[\"is_admin\"])" not in text:
        text = _replace_once(text, dashboard_anchor, dashboard_replacement, "Dashboard blind-score boundary")

    # 3) Make the score provenance explicit to QLKH so the user understands that
    # any point shown in the CBHT section is their own historical scoring only.
    support_anchor = "    st.subheader(\"Phân tích theo Cán bộ hỗ trợ\")\n    g = _staff_aggregate_with_roster(room_f_stats, \"support_name\", \"Cán bộ hỗ trợ\")\n"
    support_replacement = """    st.subheader(\"Phân tích theo Cán bộ hỗ trợ\")\n    if _blind_qlkh:\n        st.caption(\"🔒 Điểm trong phần này chỉ tính từ các đánh giá do chính bạn thực hiện. Điểm do CBQLKH khác chấm không được hiển thị hoặc dùng làm benchmark trên tài khoản của bạn.\")\n    g = _staff_aggregate_with_roster(room_f_stats, \"support_name\", \"Cán bộ hỗ trợ\")\n"""
    if "Điểm trong phần này chỉ tính từ các đánh giá do chính bạn thực hiện" not in text:
        text = _replace_once(text, support_anchor, support_replacement, "QLKH score provenance caption")

    # 4) Rename the CBHT score chart for QLKH so it cannot be mistaken for the
    # room-wide average. Leader/Admin retain the original title.
    chart_old = '    with a: _altair_bar(g,"support_name","diem_tb","Điểm bình quân theo CB hỗ trợ","Điểm")\n'
    chart_new = '    with a: _altair_bar(g,"support_name","diem_tb",("Điểm bình quân do tôi chấm theo CB hỗ trợ" if _blind_qlkh else "Điểm bình quân theo CB hỗ trợ"),"Điểm")\n'
    if "Điểm bình quân do tôi chấm theo CB hỗ trợ" not in text:
        text = _replace_once(text, chart_old, chart_new, "CBHT score chart title")

    # 5) Task history is another possible score leak after reassignment/rework.
    # For a normal QLKH, show only evaluation rows submitted by that user. Admin,
    # leader and CBHT keep the current full history behavior.
    history_pattern = re.compile(
        r"    evals = qdf\('''SELECT e\.round_no,u\.full_name evaluator,e\.quality_score,e\.progress_score,e\.comment,e\.created_at\s+"
        r"FROM evaluations e JOIN users u ON u\.id=e\.evaluator_user_id\s+"
        r"WHERE e\.task_id=\? ORDER BY e\.round_no''', \(task_id,\)\)"
    )
    history_replacement = '''    _viewer = st.session_state.get("user") or {}\n    if _viewer.get("role") == "Cán bộ QLKH" and not bool(_viewer.get("is_admin")):\n        evals = qdf(\'\'\'SELECT e.round_no,u.full_name evaluator,e.quality_score,e.progress_score,e.comment,e.created_at\n                       FROM evaluations e JOIN users u ON u.id=e.evaluator_user_id\n                       WHERE e.task_id=? AND e.evaluator_user_id=? ORDER BY e.round_no\'\'\', (task_id, int(_viewer.get("id"))))\n    else:\n        evals = qdf(\'\'\'SELECT e.round_no,u.full_name evaluator,e.quality_score,e.progress_score,e.comment,e.created_at\n                       FROM evaluations e JOIN users u ON u.id=e.evaluator_user_id\n                       WHERE e.task_id=? ORDER BY e.round_no\'\'\', (task_id,))'''
    if "WHERE e.task_id=? AND e.evaluator_user_id=? ORDER BY e.round_no" not in text:
        text, count = history_pattern.subn(history_replacement, text, count=1)
        if count != 1:
            raise RuntimeError("Blind-scoring patch cannot find task_history evaluation query")

    # Validate the transformed application source before the Docker image is built.
    compile(text, str(source_path), "exec")
    source_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    install()
