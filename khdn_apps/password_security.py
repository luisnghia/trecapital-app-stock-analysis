"""Versioned password hashes; existing 260k hashes remain readable."""
import hashlib
import hmac
import secrets

ITERATIONS = 600_000
PREFIX = "pbkdf2_sha256"


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERATIONS).hex()
    return f"{PREFIX}${ITERATIONS}${salt}${value}"


def verify_password(password, stored):
    try:
        parts = str(stored).split("$")
        if len(parts) == 2:
            salt, expected = parts
            iterations = 260_000
        elif len(parts) == 4 and parts[0] == PREFIX:
            _, count, salt, expected = parts
            iterations = int(count)
            if not 260_000 <= iterations <= 2_000_000:
                return False
        else:
            return False
        if not salt or len(salt) > 128 or len(expected) != 64:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError, OverflowError):
        return False


def needs_upgrade(stored):
    return not str(stored).startswith(f"{PREFIX}${ITERATIONS}$")
