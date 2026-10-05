"""Temporary-DB regressions for manager linkage, source inheritance and scope."""
import json
import sqlite3
import unittest

from khdn_apps import weekly_manager_edit as editor
from khdn_apps import weekly_entry_edit_patch as entry
from khdn_apps import weekly_entry_edit_qa as existing
from khdn_apps import weekly_plan as core
from khdn_apps import weekly_priority_policy_patch as policy


class ManagerLinkQA(unittest.TestCase):
    def setUp(self):
        self.fixture=existing.EntryQA(methodName='runTest');self.fixture.setUp()
        self.iid=self.fixture.save();self.fixture.status(3,'DA_NOP')

    def tearDown(self): self.fixture.tearDown()

    def save(self,uid=4,iid=None,token=None,**changes):
        iid=iid or self.iid
        data={'title':'Điều chỉnh QA','work_date':'2026-10-08','due_date':'2026-10-15',
              'customer_id':10,'linked_case_id':20,'controller':'4','focus':'NONE','nonfocus_q':'4',
              'category':'Kế hoạch tuần','source':'Nội dung gốc QA','output':'Kết quả QA','note':'Ghi chú QA'}
        data.update(changes)
        return editor.save_item(self.fixture.conn,policy,core,uid,iid,data,
                                expected_token=token or entry.item_token(self.fixture.row(iid)))

    def test_source_q1_q3_q4_deadline_controller_override_manual_values(self):
        for q in (1,3,4):
            with self.fixture.conn() as c: c.execute('UPDATE customer_work_cases SET priority_quadrant=? WHERE id=20',(q,))
            self.save(controller='2',due_date='2026-12-31',focus='101')
            row=self.fixture.row(self.iid)
            self.assertEqual((row['customer_id'],row['linked_case_id'],row['expected_complete_date'],row['controller_user_id'],row['priority_quadrant']),
                             (10,20,'2026-10-02',4,q))
            self.assertIsNone(row['focus_category_id'])
            self.assertIn('Kế thừa Công việc khách hàng #20',row['priority_basis'])

    def test_q2_source_focus_and_legacy_snapshot_are_preserved(self):
        with self.fixture.conn() as c:
            c.execute('UPDATE customer_work_cases SET priority_quadrant=2,focus_category_id=102 WHERE id=20')
        self.save();row=self.fixture.row(self.iid)
        self.assertEqual((row['priority_quadrant'],row['focus_category_id'],row['focus_name_snapshot']),(2,102,'Mục QA 2'))
        with self.fixture.conn() as c:
            c.execute("UPDATE customer_work_cases SET focus_category_id=NULL,focus_name_snapshot='Trọng tâm đã lưu QA' WHERE id=20")
        self.save();row=self.fixture.row(self.iid)
        self.assertEqual((row['priority_quadrant'],row['focus_name_snapshot']),(2,'Trọng tâm đã lưu QA'))

    def test_duplicate_checked_for_plan_owner_even_when_admin_edits(self):
        self.save(uid=1)
        self.fixture.status(3,'NHAP');other=self.fixture.save();self.fixture.status(3,'DA_NOP')
        with self.assertRaises(ValueError): self.save(uid=1,iid=other)
        self.assertIsNone(self.fixture.row(other)['linked_case_id'])

    def test_unlink_and_change_customer_clear_saved_relation(self):
        self.save();self.save(linked_case_id=None)
        self.assertIsNone(self.fixture.row(self.iid)['linked_case_id'])
        self.save();self.save(customer_id=None,linked_case_id=None)
        row=self.fixture.row(self.iid)
        self.assertEqual((row['customer_id'],row['linked_case_id'],row['customer_text']),(None,None,''))

    def test_wrong_customer_closed_new_case_and_inactive_master_do_not_write(self):
        before=self.fixture.row(self.iid)
        with self.assertRaises(ValueError): self.save(customer_id=None)
        with self.fixture.conn() as c: c.execute("UPDATE customer_work_cases SET status='DONE' WHERE id=20")
        with self.assertRaises(ValueError): self.save()
        with self.fixture.conn() as c:
            c.execute("UPDATE customer_work_cases SET status='ACTIVE' WHERE id=20")
            c.execute('UPDATE customers SET active=0 WHERE id=10')
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(self.fixture.row(self.iid),before)

    def test_existing_completed_link_survives_other_edits(self):
        self.save()
        with self.fixture.conn() as c: c.execute("UPDATE customer_work_cases SET status='DONE' WHERE id=20")
        self.save(title='Giữ liên kết cũ QA')
        self.assertEqual(self.fixture.row(self.iid)['linked_case_id'],20)

    def test_fresh_account_scope_plan_lock_and_token_checks(self):
        before=self.fixture.row(self.iid)
        for uid in (2,3,5,6,999):
            with self.assertRaises(PermissionError): self.save(uid=uid)
        with self.fixture.conn() as c: c.execute('UPDATE users SET manager_user_id=1 WHERE id=3')
        with self.assertRaises(PermissionError): self.save()
        with self.fixture.conn() as c:
            c.execute('UPDATE users SET manager_user_id=4 WHERE id=3')
            c.execute('UPDATE users SET active=0 WHERE id=4')
        with self.assertRaises(PermissionError): self.save()
        with self.fixture.conn() as c: c.execute('UPDATE users SET active=1 WHERE id=4')
        self.fixture.status(3,'DA_CHOT',1)
        with self.assertRaises(PermissionError): self.save(uid=1)
        self.fixture.status(3,'DA_NOP')
        with self.assertRaises(ValueError): self.save(token='outdated')
        with self.assertRaises(ValueError): self.save(work_date='2026-10-12')
        self.assertEqual(self.fixture.row(self.iid),before)

    def test_failed_audit_rolls_back_link_and_inherited_fields(self):
        before=self.fixture.row(self.iid)
        with self.fixture.conn() as c:
            c.execute("CREATE TRIGGER qa_block_manager BEFORE INSERT ON weekly_plan_actions WHEN NEW.action='MANAGER_EDIT_PHASE3' BEGIN SELECT RAISE(ABORT,'QA audit rollback'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.save()
        self.assertEqual(self.fixture.row(self.iid),before)

    def test_audit_contains_old_and_new_relation_and_stable_item_id(self):
        self.assertEqual(self.save(),self.iid)
        with self.fixture.conn() as c:
            detail=json.loads(c.execute("SELECT detail FROM weekly_plan_actions WHERE item_id=? AND action='MANAGER_EDIT_PHASE3'",(self.iid,)).fetchone()[0])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM weekly_plan_items').fetchone()[0],1)
        self.assertIsNone(detail['before']['linked_case_id'])
        self.assertEqual((detail['after']['linked_case_id'],detail['linked_case_id']),(20,20))


def run_qa():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ManagerLinkQA))
    if not result.wasSuccessful(): raise AssertionError('Manager link QA failed')
    print('WEEKLY_MANAGER_LINK_QA_PASS',result.testsRun,'inheritance Q1 Q2 Q3 Q4 owner_duplicate unlink closed_link scopes revoked_role locked stale audit atomic_rollback')


if __name__=='__main__': run_qa()
