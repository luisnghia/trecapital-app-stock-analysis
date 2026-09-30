from __future__ import annotations

from pathlib import Path
import os
import sqlite3
import tempfile

from khdn_apps import mobile_input_performance_patch as p

ROOT=Path(__file__).resolve().parent
SRC=(ROOT/'mobile_input_performance_patch.py').read_text(encoding='utf-8')
FORM=(ROOT/'fast_client_form.py').read_text(encoding='utf-8')
HTML=(ROOT/'fast_client_form_component'/'index.html').read_text(encoding='utf-8')
PROBE=(ROOT/'theme_probe_component'/'index.html').read_text(encoding='utf-8')
BRIDGE=(ROOT/'theme_bridge_fix.py').read_text(encoding='utf-8')
P10FIX=(ROOT/'planning_operational_phase10_fix.py').read_text(encoding='utf-8')

checks={
    'version_v2': 'VERSION = "2.0.0"' in SRC,
    'component_declared': 'khdn_fast_client_form' in FORM and 'declare_component' in FORM,
    'component_submit_only': "streamlit:setComponentValue" in HTML and "form.addEventListener('submit'" in HTML,
    'component_no_input_bridge': "addEventListener('input'" not in HTML,
    'component_keeps_dom_on_render': "if(signature!==nextSig)" in HTML and "else if(resetToken===null||resetToken!==nextToken)" in HTML,
    'ios_font_16': 'font-size:16px' in HTML,
    'users_fast': 'zero_keystroke_users=1' in SRC and 'system_user_create_fast_v2' in SRC,
    'task_types_fast': 'zero_keystroke_task_types=1' in SRC and 'system_task_type_create_fast_v5' in SRC,
    'stage_fast': 'zero_keystroke_stages=1' in SRC and 'cw_stage_fast_v2_' in SRC,
    'focus_fast': 'zero_keystroke_focus=1' in SRC and 'focus_catalog_fast_v2_' in SRC,
    'realtime_disabled': 'MOBILE_INPUT_PERIODIC_REFRESH_DISABLED seconds=0' in SRC and 'def realtime_refresh_watch(_u): return None' in SRC,
    'task_type_scope_index': 'ux_task_types_scope_name_norm' in SRC and 'module_scope, lower(trim(name))' in SRC,
    'scope_specific_create_guard': 'WHERE module_scope=? AND lower(trim(name))=lower(trim(?))' in SRC,
    'scope_specific_edit_guard': 'WHERE module_scope=? AND lower(trim(name))=lower(trim(?)) AND id<>?' in SRC,
    'probe_no_poll': 'setInterval' not in PROBE,
    'bridge_no_poll_source': 'setInterval' not in BRIDGE,
    'installed_last': 'mobile_input_perf.install(app_ns, policy, logger)' in P10FIX and P10FIX.index('mobile_input_perf.install')>P10FIX.index('phase15.install'),
}
assert all(checks.values()),checks

with tempfile.TemporaryDirectory() as td:
    root=Path(td); db=root/'legacy.db'
    c=sqlite3.connect(db)
    c.executescript('''
    CREATE TABLE task_types(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE NOT NULL,
      sla_hours REAL NOT NULL DEFAULT 8,
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      module_scope TEXT NOT NULL DEFAULT 'OPS'
    );
    INSERT INTO task_types(name,sla_hours,active,created_at,updated_at,module_scope)
    VALUES('Giải ngân',8,1,'2026-01-01','2026-01-01','OPS');
    ''')
    c.commit(); c.close()
    def get_conn():
        x=sqlite3.connect(db); x.row_factory=sqlite3.Row; x.execute('PRAGMA foreign_keys=ON'); return x
    old=os.environ.get('KHDN_DATA_DIR'); os.environ['KHDN_DATA_DIR']=str(root)
    try:
        p._migrate_task_type_scope_uniqueness({'get_conn':get_conn,'DB_PATH':str(db)},None)
    finally:
        if old is None: os.environ.pop('KHDN_DATA_DIR',None)
        else: os.environ['KHDN_DATA_DIR']=old
    with get_conn() as c:
        row=c.execute("SELECT name,module_scope FROM task_types WHERE id=1").fetchone()
        assert tuple(row)==('Giải ngân','OPS'),tuple(row)
        c.execute("INSERT INTO task_types(name,sla_hours,active,created_at,updated_at,module_scope) VALUES('Giải ngân',8,1,'2026-01-02','2026-01-02','PLAN')")
        duplicate_blocked=False
        try:
            c.execute("INSERT INTO task_types(name,sla_hours,active,created_at,updated_at,module_scope) VALUES('  giải NGÂN  ',8,1,'2026-01-03','2026-01-03','OPS')")
        except sqlite3.IntegrityError:
            duplicate_blocked=True
        assert duplicate_blocked
        scopes=[r[0] for r in c.execute("SELECT module_scope FROM task_types WHERE lower(trim(name))=lower(trim('Giải ngân')) ORDER BY module_scope").fetchall()]
        assert scopes==['OPS','PLAN'],scopes
    assert (root/'backups'/'pre_task_type_scope_unique_v2.db').exists()

print('MOBILE_INPUT_PERFORMANCE_V2_QA_PASS',checks,'cross_scope_duplicate=PASS same_scope_duplicate_block=PASS migration_backup=PASS')
