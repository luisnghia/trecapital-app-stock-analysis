from __future__ import annotations
import sqlite3
import tempfile
from pathlib import Path
from khdn_apps.customer_work_refinement_patch import _task_types,_q,_status_meta


def main():
    db=Path(tempfile.mkstemp(prefix='khdn-cw-refine-',suffix='.db')[1])
    try:
        c=sqlite3.connect(db); c.row_factory=sqlite3.Row
        c.executescript('''
        CREATE TABLE task_types(id INTEGER PRIMARY KEY,name TEXT,sla_hours REAL,active INTEGER);
        INSERT INTO task_types VALUES(1,'Tín dụng',8,1);
        INSERT INTO task_types VALUES(2,'Huy động',4,1);
        INSERT INTO task_types VALUES(3,'Ngưng dùng',2,0);
        ''')
        rows=_task_types(c)
        assert [x['name'] for x in rows]==['Huy động','Tín dụng']
        assert _q(1)==1 and _q(9)==4 and _q(None)==4
        assert 'Quá hạn' in _status_meta({'is_overdue':1})[0]
        assert 'Trong hạn' in _status_meta({})[0]
        src=Path(__file__).with_name('customer_work_refinement_patch.py').read_text(encoding='utf-8')
        for marker in [
            'FROM task_types WHERE active=1',
            'st.tabs(["Đang xử lý","Tạo công việc mới"])',
            'st.session_state["admin_scope"]="system"',
            'st.session_state["admin_view"]="users"',
            'page=="customer_work" and before!="customer_work"',
            'cw-focus-card',
            'case_type=case_type["name"]',
        ]:
            assert marker in src, marker
        print('CUSTOMER_WORK_REFINEMENT_QA_PASS')
    finally:
        try:c.close()
        except Exception:pass
        try:db.unlink()
        except OSError:pass

if __name__=='__main__':
    main()
