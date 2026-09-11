"""Compressed loader for KHDN Ops V2.23 embedded in Trecapital.
Generated from the audited V2.23 source.
"""
from pathlib import Path as _Path
import base64 as _base64
import gzip as _gzip

_parts = sorted((_Path(__file__).resolve().parent / "_src").glob("*.txt"))
_payload = "".join(_p.read_text(encoding="ascii") for _p in _parts)
_source = _gzip.decompress(_base64.b64decode(_payload)).decode("utf-8")
exec(compile(_source, str(_Path(__file__).resolve().parent / "app_v223_source.py"), "exec"), globals(), globals())
