"""Weekly Plan V13 bootstrap hardening.

V12 adds tables with foreign keys to weekly_plans. A user can enter Weekly Plan
before those core tables exist in a fresh database, so initialize the established
V6/core schema first, then apply V12 parameter/autosave/admin extensions.
"""
from __future__ import annotations

from typing import Callable, Optional

from khdn_apps import weekly_plan_v6 as v6
from khdn_apps import weekly_plan_v12 as v12


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    v6._init_v6_schema(get_conn)
    return v12.weekly_plan_page(u, get_conn, page_title, pill_nav)


def weekly_admin_panel(u, get_conn: Callable):
    v6._init_v6_schema(get_conn)
    return v12.weekly_admin_panel(u, get_conn)
