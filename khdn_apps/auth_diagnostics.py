"""Read-only, credential-free authentication diagnostics for production support."""
from collections import Counter
import json
import logging
from pathlib import Path
import sqlite3


def hash_format(value):
    parts = str(value or '').split('$')
    if len(parts) == 2:
        salt, digest = parts
        kind = 'legacy'
    elif len(parts) == 4 and parts[0] == 'pbkdf2_sha256':
        _, count, salt, digest = parts
        try:
            if not 260000 <= int(count) <= 2000000:
                return 'invalid'
        except ValueError:
            return 'invalid'
        kind = 'versioned'
    else:
        return 'invalid'
    if not salt or len(salt) > 128 or len(digest) != 64:
        return 'invalid'
    try:
        bytes.fromhex(digest)
    except ValueError:
        return 'invalid'
    return kind


def log_inventory(db_path, logger):
    try:
        with sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True) as c:
            c.row_factory = sqlite3.Row
            rows = [dict(r) for r in c.execute('SELECT * FROM users')]
        report = {
            'users': len(rows),
            'active': sum(r.get('active') == 1 for r in rows),
            'active_admins': sum(r.get('active') == 1 and bool(r.get('is_admin')) for r in rows),
            'deleted': sum(bool(r.get('deleted_at')) for r in rows),
            'forced_change': sum(bool(r.get('must_change_password')) for r in rows),
            'hash_formats': dict(Counter(hash_format(r.get('password_hash')) for r in rows)),
            'last_successful_login': max((str(r.get('last_login_at') or '') for r in rows), default=''),
        }
        logger.info('AUTH_INVENTORY %s', json.dumps(report, sort_keys=True))
    except Exception as exc:
        logger.warning('AUTH_INVENTORY_UNAVAILABLE type=%s', type(exc).__name__)


def log_login_failure(db_path, username):
    # Never log names, submitted passwords, stored hashes or session tokens.
    try:
        with sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True) as c:
            c.row_factory = sqlite3.Row
            row = c.execute('SELECT * FROM users WHERE lower(username)=lower(?)', (username,)).fetchone()
        reason = 'unknown_user'
        if row:
            row = dict(row)
            reason = ('inactive' if row.get('active') != 1 else
                      'deleted' if row.get('deleted_at') else
                      'invalid_hash' if hash_format(row.get('password_hash')) == 'invalid' else
                      'password_mismatch')
        print('AUTH_LOGIN_REJECTED reason=' + reason, flush=True)
    except Exception as exc:
        print('AUTH_LOGIN_DIAGNOSTIC_UNAVAILABLE type=' + type(exc).__name__, flush=True)
