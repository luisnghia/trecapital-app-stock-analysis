import sqlite3
import tempfile
import unittest
from pathlib import Path
from khdn_apps import device_sessions as s


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name)/'ops.db')
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, active INTEGER, must_change_password INTEGER)')
            c.execute("INSERT INTO users VALUES(1,'test','hash1',1,0)")
        self.user={'id':1,'password_hash':'hash1'}

    def token(self):
        return s.redeem(self.db,s.issue(self.db,self.user))

    def test_restore_and_no_plaintext_at_rest(self):
        token=self.token()
        self.assertEqual(s.resolve(self.db,token)['id'],1)
        self.assertNotIn(token.encode(),Path(self.db).read_bytes())

    def test_one_time_grant(self):
        grant=s.issue(self.db,self.user)
        self.assertTrue(s.redeem(self.db,grant))
        self.assertIsNone(s.redeem(self.db,grant))

    def test_revoke(self):
        token=self.token(); s.revoke_user(self.db,1)
        self.assertIsNone(s.resolve(self.db,token))

    def test_revoke_one_device_keeps_other_device(self):
        first, second = self.token(), self.token()
        s.revoke(self.db, first)
        self.assertIsNone(s.resolve(self.db, first))
        self.assertEqual(s.resolve(self.db, second)['id'], 1)

    def test_password_change(self):
        token=self.token()
        with sqlite3.connect(self.db) as c: c.execute("UPDATE users SET password_hash='hash2'")
        self.assertIsNone(s.resolve(self.db,token))

    def test_disabled(self):
        token=self.token()
        with sqlite3.connect(self.db) as c: c.execute('UPDATE users SET active=0')
        self.assertIsNone(s.resolve(self.db,token))

    def test_expired(self):
        token=self.token()
        with sqlite3.connect(self.db) as c: c.execute('UPDATE device_sessions SET expires=0')
        self.assertIsNone(s.resolve(self.db,token))

    def test_invalid_and_forced_reset(self):
        self.assertIsNone(s.resolve(self.db,'invalid'))
        grant=s.issue(self.db,self.user)
        with sqlite3.connect(self.db) as c: c.execute('UPDATE users SET must_change_password=1')
        self.assertIsNone(s.redeem(self.db,grant))

    def test_http_cookie_exchange_and_csrf(self):
        import os
        from unittest.mock import patch
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from khdn_apps.web_server import DeviceMiddleware
        with patch.dict(os.environ, {'KHDN_DB_PATH':self.db}):
            client=TestClient(DeviceMiddleware(Starlette()), base_url='https://testserver')
            grant=s.issue(self.db,self.user)
            denied=client.post('/_khdn/device-session',json={'action':'set','grant':grant},headers={'origin':'https://evil.example'})
            self.assertEqual(denied.status_code,403)
            invalid=client.post('/_khdn/device-session',json={'action':'unknown'},headers={'origin':'https://testserver'})
            self.assertEqual(invalid.status_code,400)
            response=client.post('/_khdn/device-session',json={'action':'set','grant':grant},headers={'origin':'https://testserver'})
            self.assertEqual(response.status_code,200)
            cookie=response.headers['set-cookie']
            for attr in ['HttpOnly','Secure','SameSite=strict','Max-Age=2592000','Path=/']:
                self.assertIn(attr,cookie)
            self.assertEqual(response.json(),{'ok':True})
            token=client.cookies.get(s.COOKIE)
            self.assertEqual(s.resolve(self.db,token)['id'],1)
            response=client.post('/_khdn/device-session',json={'action':'clear'},headers={'origin':'https://testserver'})
            self.assertEqual(response.status_code,200)
            self.assertIsNone(s.resolve(self.db,token))
