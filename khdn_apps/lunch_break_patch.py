"""Install configurable lunch-break exclusion into the KHDN source.

The compressed application source is transformed during the image build.  This
patch keeps the setting in SQLite, exposes small helpers for the UI and applies
the same overlap calculation to historical, live and audit-facing durations.
"""


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"Lunch-break patch cannot find: {label}")
    return source.replace(old, new, 1)


def _replace_span(source: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Lunch-break patch cannot find start: {label}")
    end = source.find(end_marker, start + len(start_marker))
    if end < 0:
        raise RuntimeError(f"Lunch-break patch cannot find end: {label}")
    return source[:start] + replacement + source[end:]


def patch_source(source: str) -> str:
    # The settings table is deliberately separate from task_types: one global
    # office calendar applies to every task type and every staff member.
    old = '''        CREATE TABLE IF NOT EXISTS annual_archives (\n            year INTEGER PRIMARY KEY,\n            stats_file TEXT,\n            detail_file TEXT,\n            db_backup_file TEXT,\n            task_count INTEGER NOT NULL DEFAULT 0,\n            archived_at TEXT NOT NULL,\n            best_five_year_reference INTEGER,\n            notes TEXT\n        );\n'''
    new = '''        CREATE TABLE IF NOT EXISTS annual_archives (\n            year INTEGER PRIMARY KEY,\n            stats_file TEXT,\n            detail_file TEXT,\n            db_backup_file TEXT,\n            task_count INTEGER NOT NULL DEFAULT 0,\n            archived_at TEXT NOT NULL,\n            best_five_year_reference INTEGER,\n            notes TEXT\n        );\n        CREATE TABLE IF NOT EXISTS system_settings (\n            key TEXT PRIMARY KEY,\n            value TEXT NOT NULL,\n            updated_at TEXT NOT NULL,\n            updated_by INTEGER,\n            FOREIGN KEY(updated_by) REFERENCES users(id)\n        );\n'''
    source = _replace_once(source, old, new, "system_settings schema")

    # Seed the real-world default while retaining an explicit enabled flag.  A
    # leader can change or disable it from Admin/Lãnh đạo phòng → Loại công việc.
    old = '''        ts = now_str()\n        for name in DEFAULT_TASK_TYPES:\n'''
    new = '''        ts = now_str()\n        c.execute("INSERT INTO system_settings(key,value,updated_at,updated_by) VALUES('lunch_break_enabled','1',?,NULL) ON CONFLICT(key) DO NOTHING", (ts,))\n        c.execute("INSERT INTO system_settings(key,value,updated_at,updated_by) VALUES('lunch_break_start','12:00',?,NULL) ON CONFLICT(key) DO NOTHING", (ts,))\n        c.execute("INSERT INTO system_settings(key,value,updated_at,updated_by) VALUES('lunch_break_end','13:30',?,NULL) ON CONFLICT(key) DO NOTHING", (ts,))\n        for name in DEFAULT_TASK_TYPES:\n'''
    source = _replace_once(source, old, new, "system_settings defaults")

    helpers = r'''\n\n# ---------- Office calendar / lunch-break settings ----------\ndef _parse_clock_minutes(value, fallback):\n    try:\n        text = str(value or "").strip()\n        hour, minute = [int(x) for x in text.split(":", 1)]\n        if 0 <= hour <= 23 and 0 <= minute <= 59:\n            return hour * 60 + minute\n    except Exception:\n        pass\n    return int(fallback)\n\n\ndef lunch_break_settings():\n    """Return (enabled, start_minute, end_minute) for the global office break."""\n    enabled, start_minute, end_minute = True, 12 * 60, 13 * 60 + 30\n    try:\n        rows = qdf("SELECT key,value FROM system_settings WHERE key IN ('lunch_break_enabled','lunch_break_start','lunch_break_end')")\n        values = {str(row["key"]): str(row["value"]) for _, row in rows.iterrows()}\n        enabled = str(values.get("lunch_break_enabled", "1")).strip().lower() in {"1", "true", "yes", "on"}\n        start_minute = _parse_clock_minutes(values.get("lunch_break_start"), start_minute)\n        end_minute = _parse_clock_minutes(values.get("lunch_break_end"), end_minute)\n    except Exception:\n        # The helper is also used by build-time/static checks before a database\n        # exists; use the documented default in that case.\n        pass\n    return bool(enabled), int(start_minute), int(end_minute)\n\n\n+def lunch_break_interval():\n    enabled, start_minute, end_minute = lunch_break_settings()\n    if not enabled or end_minute <= start_minute:\n        return None\n    return int(start_minute), int(end_minute)\n\n\ndef _minutes_to_clock(value):\n    value = max(0, min(23 * 60 + 59, int(value)))\n    return datetime.min.replace(hour=value // 60, minute=value % 60).time()\n\n\ndef _clock_to_minutes(value):\n    return int(value.hour) * 60 + int(value.minute)\n\n\ndef save_lunch_break_settings(actor_user_id, enabled, start_time, end_time):\n    start_minute = _clock_to_minutes(start_time)\n    end_minute = _clock_to_minutes(end_time)\n    if end_minute <= start_minute:\n        raise ValueError("Giờ kết thúc nghỉ trưa phải sau giờ bắt đầu.")\n    if start_minute < 0 or end_minute > 24 * 60:\n        raise ValueError("Giờ nghỉ trưa không hợp lệ.")\n    ts = now_str()\n    values = {\n        "lunch_break_enabled": "1" if bool(enabled) else "0",\n        "lunch_break_start": f"{start_minute // 60:02d}:{start_minute % 60:02d}",\n        "lunch_break_end": f"{end_minute // 60:02d}:{end_minute % 60:02d}",\n    }\n    with get_conn() as c:\n        for key, value in values.items():\n            c.execute("INSERT INTO system_settings(key,value,updated_at,updated_by) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at,updated_by=excluded.updated_by", (key, value, ts, int(actor_user_id)))\n        c.commit()\n    audit(int(actor_user_id), "UPDATE_LUNCH_BREAK", "system_setting", "lunch_break", f"enabled={values['lunch_break_enabled']}; start={values['lunch_break_start']}; end={values['lunch_break_end']}")\n\n\ndef _elapsed_minutes_excluding_lunch(start, end, interval=None):\n    """Elapsed minutes minus lunch overlap on every calendar day in the interval."""\n    if start is None or end is None:\n        return math.nan\n    try:\n        start = pd.Timestamp(start)\n        end = pd.Timestamp(end)\n    except Exception:\n        return math.nan\n    if pd.isna(start) or pd.isna(end):\n        return math.nan\n    raw_minutes = max(0.0, (end - start).total_seconds() / 60.0)\n    if raw_minutes <= 0 or not interval:\n        return raw_minutes\n    lunch_start, lunch_end = [int(x) for x in interval]\n    removed = 0.0\n    day = start.normalize()\n    last_day = end.normalize()\n    while day <= last_day:\n        break_start = day + pd.Timedelta(minutes=lunch_start)\n        break_end = day + pd.Timedelta(minutes=lunch_end)\n        overlap_start = max(start, break_start)\n        overlap_end = min(end, break_end)\n        if overlap_end > overlap_start:\n            removed += (overlap_end - overlap_start).total_seconds() / 60.0\n        day = day + pd.Timedelta(days=1)\n    return max(0.0, raw_minutes - removed)\n\n\ndef _elapsed_series_excluding_lunch(starts, ends, interval=None):\n    return pd.Series(\n        [_elapsed_minutes_excluding_lunch(start, end, interval) for start, end in zip(starts, ends)],\n        index=starts.index,\n        dtype="float64",\n    )\n\n\n'''
    helpers = helpers.replace("\\n+def lunch_break_interval", "\\ndef lunch_break_interval")
    helpers = helpers.replace("\\n", "\n")
    # Keep the helper insertion independent of the reason-category schema patch.
    source = _replace_once(source, 'def audit(actor_user_id, action, object_type="", object_id="", detail=""):\n', helpers + 'def audit(actor_user_id, action, object_type="", object_id="", detail=""):\n', "office-calendar helpers")

    enrich = r'''def enrich_tasks(df):\n    if df.empty:\n        return df\n    out = df.copy()\n    out["avg_score"] = (pd.to_numeric(out["quality_score"], errors="coerce") + pd.to_numeric(out["progress_score"], errors="coerce")) / 2\n    out["start_dt"] = pd.to_datetime(out["start_time"], errors="coerce")\n    out["end_dt"] = pd.to_datetime(out["end_time"], errors="coerce")\n    for _c in ["assigned_at","accepted_at","first_accepted_at","returned_to_qlkh_at","cancelled_at","evaluated_at","last_rework_at","closed_time"]:\n        if _c in out.columns:\n            out[_c + "_dt"] = pd.to_datetime(out[_c], errors="coerce")\n\n    _lunch_interval = lunch_break_interval()\n    _duration = _elapsed_series_excluding_lunch(out["start_dt"], out["end_dt"], _lunch_interval)\n    # A few legacy queries only carry the SQL duration expression.  Keep it as\n    # a safe fallback, while all normal task frames use the calendar-aware path.\n    if "duration_hours" in out.columns:\n        _legacy_duration = pd.to_numeric(out["duration_hours"], errors="coerce") * 60.0\n        _duration = _duration.where(_duration.notna(), _legacy_duration)\n    out["duration_minutes"] = _duration\n    out["duration_hours"] = out["duration_minutes"] / 60.0\n\n    # Thời gian chờ tiếp nhận: từ lúc QLKH khởi tạo/giao ban đầu đến lần CBHT tiếp nhận đầu tiên.\n    if "assigned_at_dt" in out.columns and "first_accepted_at_dt" in out.columns:\n        _first_accept = out["first_accepted_at_dt"]\n        if "accepted_at_dt" in out.columns:\n            _first_accept = _first_accept.fillna(out["accepted_at_dt"])\n        out["assignment_to_accept_minutes"] = _elapsed_series_excluding_lunch(out["assigned_at_dt"], _first_accept, _lunch_interval)\n    elif "assigned_at_dt" in out.columns and "accepted_at_dt" in out.columns:\n        out["assignment_to_accept_minutes"] = _elapsed_series_excluding_lunch(out["assigned_at_dt"], out["accepted_at_dt"], _lunch_interval)\n    else:\n        out["assignment_to_accept_minutes"] = pd.NA\n    out["status_label"] = out["status"].map(STATUS_LABEL).fillna(out["status"])\n    if "amount_vnd" not in out.columns:\n        out["amount_vnd"] = pd.to_numeric(out.get("amount"), errors="coerce").fillna(0)\n    out["amount_vnd"] = pd.to_numeric(out["amount_vnd"], errors="coerce").fillna(0)\n    return out\n\n\n'''
    enrich = enrich.replace("\\n", "\n")
    source = _replace_span(source, 'def enrich_tasks(df):\n', '# ---------- UI helpers ----------', enrich, "calendar-aware task enrichment")

    # Historical phase medians and live heatmap waits must use the same rule as
    # the task detail/dashboard metrics.
    old = '''    h["accept_minutes"] = (h["first_accepted_at_dt"].fillna(h["accepted_at_dt"]) - h["assigned_at_dt"]).dt.total_seconds()/60.0\n    h["work_minutes"] = (h["end_time_dt"] - h["start_time_dt"]).dt.total_seconds()/60.0\n    h["review_minutes"] = (h["evaluated_at_dt"] - h["end_time_dt"]).dt.total_seconds()/60.0\n'''
    new = '''    _lunch_interval = lunch_break_interval()\n    h["accept_minutes"] = _elapsed_series_excluding_lunch(h["assigned_at_dt"], h["first_accepted_at_dt"].fillna(h["accepted_at_dt"]), _lunch_interval)\n    h["work_minutes"] = _elapsed_series_excluding_lunch(h["start_time_dt"], h["end_time_dt"], _lunch_interval)\n    h["review_minutes"] = _elapsed_series_excluding_lunch(h["end_time_dt"], h["evaluated_at_dt"], _lunch_interval)\n'''
    source = _replace_once(source, old, new, "historical phase durations")
    old = '''    elapsed=max(0.0,(now_dt()-start).total_seconds()/60.0) if start else 0.0\n'''
    new = '''    elapsed=_elapsed_minutes_excluding_lunch(start, now_dt(), lunch_break_interval()) if start else 0.0\n'''
    source = _replace_once(source, old, new, "live phase duration")

    # User-facing workflow messages and the QLKH review summary also report the
    # operational duration, so they must not reintroduce raw wall-clock minutes.
    old = '                    wait_mins = ((first_accept-assigned).total_seconds()/60.0) if first_accept and assigned else None\n'
    new = '                    wait_mins = _elapsed_minutes_excluding_lunch(assigned, first_accept, lunch_break_interval()) if first_accept and assigned else None\n'
    source = _replace_once(source, old, new, "accept audit duration")
    old = '                    ts=now_str(); start_dt=parse_dt(row.start_time); mins=round((parse_dt(ts)-start_dt).total_seconds()/60) if start_dt else None; execute("UPDATE tasks SET status=\'PENDING_REVIEW\',end_time=?,note=CASE WHEN ?=\'\' THEN note ELSE ? END,updated_at=? WHERE id=? AND support_user_id=? AND status IN (\'OPEN\',\'REWORK\')",(ts,note2.strip(),note2.strip(),ts,tid,u["id"])); log_action(tid,u["id"],"SUBMIT_REVIEW",f"Hoàn thành lúc {fmt_dt(ts)}; thời gian xử lý={mins} phút; ghi chú={note2.strip()}"); st.success(f"Đã báo hoàn thành. Thời gian xử lý: {money(mins)} phút."); st.rerun()\n'
    new = '                    ts=now_str(); start_dt=parse_dt(row.start_time); mins=round(_elapsed_minutes_excluding_lunch(start_dt,parse_dt(ts),lunch_break_interval())) if start_dt else None; execute("UPDATE tasks SET status=\'PENDING_REVIEW\',end_time=?,note=CASE WHEN ?=\'\' THEN note ELSE ? END,updated_at=? WHERE id=? AND support_user_id=? AND status IN (\'OPEN\',\'REWORK\')",(ts,note2.strip(),note2.strip(),ts,tid,u["id"])); log_action(tid,u["id"],"SUBMIT_REVIEW",f"Hoàn thành lúc {fmt_dt(ts)}; thời gian xử lý={mins} phút; ghi chú={note2.strip()}"); st.success(f"Đã báo hoàn thành. Thời gian xử lý: {money(mins)} phút."); st.rerun()\n'
    source = _replace_once(source, old, new, "finish audit duration")
    old = '                tid=int(row.id); elapsed_min=round((parse_dt(row.end_time)-parse_dt(row.start_time)).total_seconds()/60) if row.end_time and row.start_time else 0\n'
    new = '                tid=int(row.id); elapsed_min=round(_elapsed_minutes_excluding_lunch(parse_dt(row.start_time),parse_dt(row.end_time),lunch_break_interval())) if row.end_time and row.start_time else 0\n'
    source = _replace_once(source, old, new, "review duration summary")

    # Performance/benchmark frames normally arrive enriched, but retain the
    # same exclusion if a caller supplies a raw frame without derived columns.
    old = '''    if "duration_minutes" not in x.columns:\n        x["duration_minutes"] = (x["end_dt"] - x["start_dt"]).dt.total_seconds() / 60.0\n'''
    new = '''    if "duration_minutes" not in x.columns:\n        x["duration_minutes"] = _elapsed_series_excluding_lunch(x["start_dt"], x["end_dt"], lunch_break_interval())\n'''
    source = _replace_once(source, old, new, "performance duration fallback")
    old = '''        x["assignment_to_accept_minutes"] = (first_accept - assigned).dt.total_seconds() / 60.0\n'''
    new = '''        x["assignment_to_accept_minutes"] = _elapsed_series_excluding_lunch(assigned, first_accept, lunch_break_interval())\n'''
    source = _replace_once(source, old, new, "performance accept fallback")

    required = [
        "CREATE TABLE IF NOT EXISTS system_settings",
        "def lunch_break_settings():",
        "def save_lunch_break_settings(actor_user_id, enabled, start_time, end_time):",
        "def _elapsed_minutes_excluding_lunch(start, end, interval=None):",
        "_duration = _elapsed_series_excluding_lunch",
        "_lunch_interval = lunch_break_interval()",
        "elapsed=_elapsed_minutes_excluding_lunch(start, now_dt(), lunch_break_interval())",
        "_elapsed_series_excluding_lunch(assigned, first_accept, lunch_break_interval())",
    ]
    for marker in required:
        if marker not in source:
            raise RuntimeError(f"Lunch-break marker missing after patch: {marker}")
    compile(source, "<khdn-lunch-break-patch>", "exec")
    return source
