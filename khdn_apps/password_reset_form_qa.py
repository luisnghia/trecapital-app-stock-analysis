"""Exercise both actual admin edit handlers against a synthetic SQLite database.

AST extraction avoids importing the unrelated Streamlit presentation stack.
"""
import ast
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from khdn_apps.password_security import hash_password, verify_password


class Rerun(Exception):
    pass


def rerun():
    raise Rerun


class PasswordResetFormQA(unittest.TestCase):
    def test_reset_then_save_does_not_overwrite_users_new_password(self):
        for filename in ('mobile_admin_restore_perf_patch.py', 'mobile_input_performance_patch.py'):
            with self.subTest(renderer=filename), sqlite3.connect(':memory:') as db:
                db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT, active INTEGER, is_admin INTEGER, updated_at TEXT, password_hash TEXT, must_change_password INTEGER)')
                db.execute('INSERT INTO users VALUES(2, ?, 1, 0, ?, ?, 0)', ('Staff', '', hash_password('Original123')))
                tree = ast.parse(Path(__file__).with_name(filename).read_text())
                handler = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and ast.unparse(n.test) == 'edit is not None')
                form = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and any(k.arg == 'key' and 'system_user_edit_fast_' in ast.unparse(k.value) for k in n.keywords))
                token_expr = next(k.value for k in form.keywords if k.arg == 'reset_token')
                state = {}
                errors = []
                ns = dict(execute=db.execute, hash_password=hash_password,
                          password_ok=lambda p: len(p) >= 8,
                          now_str=lambda: 'same-second', audit=lambda *a: None)
                env = dict(st=SimpleNamespace(session_state=state, toast=lambda *a, **k: None,
                                              error=errors.append, rerun=rerun),
                           ns=ns, sqlite3=sqlite3, selected=2, u={'id': 1},
                           _uget=lambda u, key: u[key], roles=['Staff'],
                           cur={'username': 'test', 'role': 'Staff', 'active': 1, 'is_admin': 0})
                wrapper = ast.parse('def run_handler():\n    pass\n')
                wrapper.body[0].body = [handler]
                code = compile(ast.fix_missing_locations(wrapper), filename, 'exec')
                exec(code, env)
                token_code = compile(ast.Expression(token_expr), filename, 'eval')
                def save(password):
                    env['edit'] = dict(username='test', role='Staff', active=True, is_admin=False, password=password)
                    with self.assertRaises(Rerun):
                        env['run_handler']()
                before = eval(token_code, env)
                save('Temporary123')
                after = eval(token_code, env)
                self.assertNotEqual(before, after, 'Password-only save must reset browser form defaults')
                stored, required = db.execute('SELECT password_hash,must_change_password FROM users').fetchone()
                self.assertTrue(verify_password('Temporary123', stored))
                self.assertEqual(required, 1)
                self.assertFalse(verify_password('Original123', stored))
                db.execute('UPDATE users SET password_hash=?, must_change_password=0', (hash_password('UserChosen456'),))
                # Browser applies the declared blank password default on resetToken change.
                password_field = next(n for n in ast.walk(form) if isinstance(n, ast.Dict) and any(isinstance(v, ast.Constant) and v.value == 'Reset mật khẩu (để trống nếu không đổi)' for v in n.values))
                default = next(v.value for k, v in zip(password_field.keys, password_field.values) if isinstance(k, ast.Constant) and k.value == 'default')
                self.assertEqual(default, '')
                save(default)
                stored, required = db.execute('SELECT password_hash,must_change_password FROM users').fetchone()
                self.assertTrue(verify_password('UserChosen456', stored))
                self.assertFalse(verify_password('Temporary123', stored))
                self.assertEqual(required, 0)
                self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
