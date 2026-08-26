from __future__ import annotations

"""Prevent repeated CREATE TABLE round-trips during Streamlit reruns.

The repository instance is cached for process lifetime. Extension DDL therefore needs to run once per
repository instance, not on every Question/section change. The wrapper also replaces the function in
portfolio_extensions so existing service calls inherit the same fast path.
"""

from . import portfolio_extensions as _pe


_UNCACHED = getattr(_pe, "_uncached_extension_schema_impl", _pe.ensure_extension_schema)
setattr(_pe, "_uncached_extension_schema_impl", _UNCACHED)


def ensure_extension_schema(repo) -> None:
    if getattr(repo, "_portfolio_extension_schema_ready", False):
        return
    _UNCACHED(repo)
    setattr(repo, "_portfolio_extension_schema_ready", True)


_pe.ensure_extension_schema = ensure_extension_schema

__all__ = ["ensure_extension_schema"]
