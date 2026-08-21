"""Trecapital Investment Checklist — integrated research preview."""

from .contracts import AnalystContext, CompanyContext, HostContext, InventorySourceData
# Import for side effect: portfolio/watchlist schema DDL is cached once per repository instance,
# preventing repeated CREATE TABLE round-trips during Streamlit Question/section reruns.
from .services.extension_schema_cache import ensure_extension_schema as _ensure_extension_schema_once  # noqa: F401

__all__=["AnalystContext","CompanyContext","HostContext","InventorySourceData"]
