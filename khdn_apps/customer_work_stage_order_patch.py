"""Presentation-only catalog ordering for the room Customer Work stage matrix."""
from __future__ import annotations

from khdn_apps import planning_operational_phase3_dashboard as p3

VERSION = "1.0.0"
_FLAG = "_CUSTOMER_WORK_STAGE_ORDER_VERSION"
_BASE_MATRIX = p3._matrix_table
_GET_CONN = None
_CUSTOMER_CORE = None


def _stage_rank():
    if not callable(_GET_CONN) or _CUSTOMER_CORE is None:
        return {}
    try:
        with _GET_CONN() as c:
            stages = _CUSTOMER_CORE.active_stages(c, include_inactive=True)
        return {str(x.get("name") or ""): idx for idx, x in enumerate(stages)}
    except Exception:
        return {}


def _order_rows(heads, rows, rank=None):
    cooked = list(rows or [])
    if not heads or str(heads[0]) != "Mục công việc":
        return cooked
    rank = rank if rank is not None else _stage_rank()
    if not rank:
        return cooked
    tail = len(rank) + 100000
    return sorted(
        cooked,
        key=lambda row: (
            rank.get(str(row[0] if row else ""), tail),
            str(row[0] if row else "").casefold(),
        ),
    )


def _matrix_table(st, heads, rows):
    return _BASE_MATRIX(st, heads, _order_rows(heads, rows))


def _self_check():
    rank = {"Đang tiếp cận": 0, "Đã đề nghị": 1, "Ban FDI": 7}
    rows = [["Ban FDI"], ["Đã đề nghị"], ["Đang tiếp cận"], ["Ngoài danh mục"]]
    got = [r[0] for r in _order_rows(["Mục công việc"], rows, rank)]
    assert got == ["Đang tiếp cận", "Đã đề nghị", "Ban FDI", "Ngoài danh mục"]
    untouched = [["B"], ["A"]]
    assert _order_rows(["Cán bộ"], untouched, rank) == untouched
    return True


def install(app_ns, customer_core, logger=None):
    global _GET_CONN, _CUSTOMER_CORE
    _self_check()
    _GET_CONN = (app_ns or {}).get("get_conn") if isinstance(app_ns, dict) else None
    _CUSTOMER_CORE = customer_core
    p3._matrix_table = _matrix_table
    if isinstance(app_ns, dict):
        app_ns[_FLAG] = VERSION
    if logger:
        logger.info(
            "CUSTOMER_WORK_STAGE_ORDER_PATCH_INSTALLED catalog_sort_order=1 unknown_last=1 data_migration=0"
        )
