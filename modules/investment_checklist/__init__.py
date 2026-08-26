"""Trecapital Investment Checklist — integrated research preview."""

from .contracts import AnalystContext, CompanyContext, HostContext, InventorySourceData
# Import for side effect: portfolio/watchlist schema DDL is cached once per repository instance,
# preventing repeated CREATE TABLE round-trips during Streamlit Question/section reruns.
from .services.extension_schema_cache import ensure_extension_schema as _ensure_extension_schema_once  # noqa: F401

# Keep the displayed Formula & Assumption registry synchronized with the new Watchlist/analyst
# correction calculations without duplicating rows across Streamlit reruns/imports.
from . import formula_assumptions as _formula_registry
from .watchlist_formula_assumptions import WATCHLIST_FORMULA_ROWS
for _row in WATCHLIST_FORMULA_ROWS:
    _key = (_row.get("Nhóm"), _row.get("Chỉ tiêu"))
    if not any((x.get("Nhóm"), x.get("Chỉ tiêu")) == _key for x in _formula_registry.FORMULA_ROWS):
        _formula_registry.FORMULA_ROWS.append(_row)

__all__=["AnalystContext","CompanyContext","HostContext","InventorySourceData"]
