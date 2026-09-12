"""Revocable remembered devices. Only hashes are persisted in SQLite."""
import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager

COOKIE = "__Host-khdn-device"
TTL = 30 * 86400


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@contextmanager
def connect(path):
    c = sqlite3.connect(path, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS device_sessions (
        token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
        password_stamp TEXT NOT NULL, expires REAL NOT NULL,
        grant_hash TEXT UNIQUE, grant_expires REAL)''')
    c.commit()
    try:
        with c:
            yield c
    finally:
        c.close()


def issue(path, user):
    grant = secrets.token_urlsafe(32)
    # A placeholder is never exposed to the client and is not a usable token.
    with connect(path) as c:
        c.execute("DELETE FROM device_sessions WHERE expires<=?", (time.time(),))
        c.execute("INSERT INTO device_sessions VALUES (?,?,?,?,?,?)", (
            digest(secrets.token_urlsafe(32)), user['id'], digest(user['password_hash']),
            time.time()+TTL, digest(grant), time.time()+120))
    return grant


def redeem(path, grant):
    if not isinstance(grant, str) or len(grant) > 128:
        return None
    with connect(path) as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute('''SELECT d.*, u.password_hash, u.active, u.must_change_password
            FROM device_sessions d JOIN users u ON u.id=d.user_id
            WHERE grant_hash=?''', (digest(grant),)).fetchone()
        if (not row or row['grant_expires'] <= time.time() or not row['active']
                or row['must_change_password'] or row['password_stamp'] != digest(row['password_hash'])):
            return None
        token = secrets.token_urlsafe(32)
        c.execute('''UPDATE device_sessions SET token_hash=?, grant_hash=NULL,
            grant_expires=NULL WHERE grant_hash=?''', (digest(token), digest(grant)))
        return token


def resolve(path, token):
    if not isinstance(token, str) or not 32 <= len(token) <= 128:
        return None
    with connect(path) as c:
        row = c.execute('''SELECT u.*, d.password_stamp, d.expires FROM users u
            JOIN device_sessions d ON d.user_id=u.id
            WHERE d.token_hash=? AND d.grant_hash IS NULL''', (digest(token),)).fetchone()
        if not row:
            return None
        if (row['expires'] <= time.time() or not row['active'] or row['must_change_password']
                or row['password_stamp'] != digest(row['password_hash'])):
            c.execute("DELETE FROM device_sessions WHERE token_hash=?", (digest(token),))
            return None
        return dict(row)


def revoke(path, token):
    if isinstance(token, str):
        with connect(path) as c:
            c.execute("DELETE FROM device_sessions WHERE token_hash=?", (digest(token),))


def revoke_user(path, user_id):
    with connect(path) as c:
        c.execute("DELETE FROM device_sessions WHERE user_id=?", (user_id,))
