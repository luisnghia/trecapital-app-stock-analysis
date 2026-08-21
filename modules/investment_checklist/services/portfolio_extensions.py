from __future__ import annotations

"""Persistent watchlist + analyst correction overlay for Investment Checklist.

Design rules:
- Trecapital remains the Single Source of Truth. Analyst overrides never mutate canonical financial data.
- Historical corrections are append-only versions with an explicit reason.
- Watchlist reads the latest Table 1.2 snapshot for the latest review and stores only watchlist metadata/CAGR helpers.
- Missing financial data stays missing; CAGR is not fabricated across non-positive endpoints.
"""

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ..repositories.sqlite_repository import ValidationError


EXTENSION_SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS checklist_watchlist(
        company_ref_id BIGINT PRIMARY KEY REFERENCES checklist_company_refs(id),
        added_at TEXT NOT NULL,
        added_by TEXT,
        note TEXT,
        revenue_cagr_5y DOUBLE PRECISION,
        profit_cagr_5y DOUBLE PRECISION,
        cagr_source_period TEXT,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analyst_table_overrides(
        company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
        table_key TEXT NOT NULL,
        period_key TEXT NOT NULL,
        metric_key TEXT NOT NULL,
        version_no INTEGER NOT NULL,
        value_numeric DOUBLE PRECISION,
        value_text TEXT,
        reason TEXT NOT NULL,
        actor TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY(company_ref_id, table_key, period_key, metric_key, version_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_table_overrides_lookup ON analyst_table_overrides(company_ref_id, table_key, period_key, metric_key, version_no)",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_extension_schema(repo) -> None:
    """Create the Phase 2.1 extension tables on SQLite or PostgreSQL through the repository proxy."""
    with repo._conn() as c:  # repository owns transaction/pooling semantics
        for statement in EXTENSION_SCHEMA_SQL:
            c.execute(statement)


def _annual_frame(provider) -> pd.DataFrame:
    df = getattr(provider, "annual_df", None)
    if isinstance(df, pd.DataFrame):
        return df.copy()
    inner = getattr(provider, "inner", None)
    df = getattr(inner, "annual_df", None)
    return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


def compute_5y_cagrs(provider_or_df) -> dict[str, Any]:
    """Return strict five-year FY revenue/profit CAGR from canonical Trecapital annual data.

    Six annual endpoints are required (latest FY and FY-5). CAGR is deliberately left Unknown when
    either endpoint is non-positive because the conventional CAGR formula is not economically
    meaningful across zero/sign changes.
    """
    df = provider_or_df.copy() if isinstance(provider_or_df, pd.DataFrame) else _annual_frame(provider_or_df)
    if df.empty:
        return {"revenue_cagr_5y": None, "profit_cagr_5y": None, "cagr_source_period": None}

    work = df.copy()
    if "period_type" in work.columns:
        work = work[work["period_type"].astype(str).str.upper().eq("Y")]
    if "year" not in work.columns:
        if "period" not in work.columns:
            return {"revenue_cagr_5y": None, "profit_cagr_5y": None, "cagr_source_period": None}
        work["year"] = pd.to_numeric(work["period"].astype(str).str.extract(r"(\d{4})")[0], errors="coerce")
    else:
        work["year"] = pd.to_numeric(work["year"], errors="coerce")
    work = work.dropna(subset=["year"]).copy()
    if work.empty:
        return {"revenue_cagr_5y": None, "profit_cagr_5y": None, "cagr_source_period": None}
    work["year"] = work["year"].astype(int)
    work = work.sort_values("year").drop_duplicates("year", keep="last")

    latest_year = int(work["year"].max())
    base_year = latest_year - 5
    latest = work[work["year"].eq(latest_year)]
    base = work[work["year"].eq(base_year)]
    if latest.empty or base.empty:
        return {"revenue_cagr_5y": None, "profit_cagr_5y": None, "cagr_source_period": None}
    latest = latest.iloc[-1]
    base = base.iloc[-1]

    def value(row, candidates):
        for col in candidates:
            if col in row.index:
                try:
                    v = float(row[col])
                    if pd.notna(v):
                        return v
                except Exception:
                    pass
        return None

    def cagr(end, start):
        if end is None or start is None or end <= 0 or start <= 0:
            return None
        return (end / start) ** (1.0 / 5.0) - 1.0

    revenue_start = value(base, ["revenue_bil", "net_revenue_bil"])
    revenue_end = value(latest, ["revenue_bil", "net_revenue_bil"])
    profit_start = value(base, ["net_profit_bil", "net_income_bil", "profit_after_tax_bil"])
    profit_end = value(latest, ["net_profit_bil", "net_income_bil", "profit_after_tax_bil"])
    return {
        "revenue_cagr_5y": cagr(revenue_end, revenue_start),
        "profit_cagr_5y": cagr(profit_end, profit_start),
        "cagr_source_period": f"FY{base_year}→FY{latest_year}",
    }


def is_watchlisted(repo, company_ref_id: int) -> bool:
    ensure_extension_schema(repo)
    with repo._conn() as c:
        return c.execute("SELECT company_ref_id FROM checklist_watchlist WHERE company_ref_id=?", (company_ref_id,)).fetchone() is not None


def set_watchlist(repo, company_ref_id: int, *, active: bool, actor: str, provider=None, note: str = "") -> None:
    ensure_extension_schema(repo)
    now = _now()
    with repo._conn() as c:
        before_row = c.execute("SELECT * FROM checklist_watchlist WHERE company_ref_id=?", (company_ref_id,)).fetchone()
        before = dict(before_row) if before_row else None
        if not active:
            c.execute("DELETE FROM checklist_watchlist WHERE company_ref_id=?", (company_ref_id,))
            repo._audit(c, company_ref_id=company_ref_id, actor=actor, action="remove_watchlist", entity_type="watchlist", entity_id=company_ref_id, before=before, after=None)
            return
        cg = compute_5y_cagrs(provider) if provider is not None else {"revenue_cagr_5y": None, "profit_cagr_5y": None, "cagr_source_period": None}
        c.execute(
            """INSERT INTO checklist_watchlist(company_ref_id,added_at,added_by,note,revenue_cagr_5y,profit_cagr_5y,cagr_source_period,updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(company_ref_id) DO UPDATE SET note=excluded.note,revenue_cagr_5y=excluded.revenue_cagr_5y,
            profit_cagr_5y=excluded.profit_cagr_5y,cagr_source_period=excluded.cagr_source_period,updated_at=excluded.updated_at""",
            (company_ref_id, before.get("added_at") if before else now, before.get("added_by") if before else actor, str(note or "").strip(), cg["revenue_cagr_5y"], cg["profit_cagr_5y"], cg["cagr_source_period"], now),
        )
        after_row = c.execute("SELECT * FROM checklist_watchlist WHERE company_ref_id=?", (company_ref_id,)).fetchone()
        repo._audit(c, company_ref_id=company_ref_id, actor=actor, action="add_watchlist" if before is None else "refresh_watchlist", entity_type="watchlist", entity_id=company_ref_id, before=before, after=dict(after_row) if after_row else None)


def refresh_watchlist_cagrs(repo, company_ref_id: int, *, provider, actor: str = "system") -> None:
    if is_watchlisted(repo, company_ref_id):
        set_watchlist(repo, company_ref_id, active=True, actor=actor, provider=provider)


def list_watchlist_rows(repo) -> list[dict[str, Any]]:
    """Return watchlist rows using Table 1.2 values associated with each company's latest review."""
    ensure_extension_schema(repo)
    out: list[dict[str, Any]] = []
    with repo._conn() as c:
        watch = [dict(r) for r in c.execute("SELECT * FROM checklist_watchlist ORDER BY added_at DESC")]
        for w in watch:
            co_row = c.execute("SELECT * FROM checklist_company_refs WHERE id=?", (w["company_ref_id"],)).fetchone()
            if not co_row:
                continue
            co = dict(co_row)
            rv_row = c.execute(
                "SELECT * FROM research_reviews WHERE company_ref_id=? ORDER BY as_of_date DESC,id DESC LIMIT 1",
                (w["company_ref_id"],),
            ).fetchone()
            rv = dict(rv_row) if rv_row else None
            inv_row = None
            if rv:
                inv_row = c.execute(
                    "SELECT * FROM opportunity_inventory_snapshots WHERE company_ref_id=? AND last_review_id=? ORDER BY as_of_date DESC,version_no DESC,id DESC LIMIT 1",
                    (w["company_ref_id"], rv["id"]),
                ).fetchone()
            if inv_row is None:
                inv_row = c.execute(
                    "SELECT * FROM opportunity_inventory_snapshots WHERE company_ref_id=? ORDER BY as_of_date DESC,version_no DESC,id DESC LIMIT 1",
                    (w["company_ref_id"],),
                ).fetchone()
            inv = dict(inv_row) if inv_row else {}
            row = {
                **inv,
                "company_ref_id": w["company_ref_id"],
                "ticker": co.get("ticker"),
                "company_name": co.get("company_name"),
                "exchange": co.get("exchange"),
                "latest_review_id": rv.get("id") if rv else None,
                "latest_review_as_of": rv.get("as_of_date") if rv else None,
                "latest_review_status": rv.get("status") if rv else None,
                "revenue_cagr_5y": w.get("revenue_cagr_5y"),
                "profit_cagr_5y": w.get("profit_cagr_5y"),
                "cagr_source_period": w.get("cagr_source_period"),
                "watchlist_added_at": w.get("added_at"),
            }
            out.append(row)
    return out


def save_table_override(
    repo,
    company_ref_id: int,
    *,
    table_key: str,
    period_key: str,
    metric_key: str,
    value: Any,
    reason: str,
    actor: str,
) -> int:
    ensure_extension_schema(repo)
    table_key = str(table_key or "").strip()
    period_key = str(period_key or "").strip()
    metric_key = str(metric_key or "").strip()
    reason = str(reason or "").strip()
    if not table_key or not period_key or not metric_key:
        raise ValidationError("Table, kỳ và chỉ tiêu điều chỉnh là bắt buộc.")
    if not reason:
        raise ValidationError("Lý do điều chỉnh là bắt buộc.")
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError("Giá trị điều chỉnh là bắt buộc.")
    numeric = None
    text = None
    try:
        if isinstance(value, bool):
            raise ValueError
        numeric = float(value)
        if pd.isna(numeric):
            raise ValueError
    except Exception:
        text = str(value).strip()
    now = _now()
    with repo._conn() as c:
        old = c.execute(
            "SELECT * FROM analyst_table_overrides WHERE company_ref_id=? AND table_key=? AND period_key=? AND metric_key=? ORDER BY version_no DESC LIMIT 1",
            (company_ref_id, table_key, period_key, metric_key),
        ).fetchone()
        old_d = dict(old) if old else None
        version = int(old_d.get("version_no") or 0) + 1 if old_d else 1
        c.execute(
            """INSERT INTO analyst_table_overrides(company_ref_id,table_key,period_key,metric_key,version_no,value_numeric,value_text,reason,actor,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (company_ref_id, table_key, period_key, metric_key, version, numeric, text, reason, actor, now),
        )
        after = {
            "company_ref_id": company_ref_id, "table_key": table_key, "period_key": period_key,
            "metric_key": metric_key, "version_no": version, "value_numeric": numeric,
            "value_text": text, "reason": reason, "actor": actor, "created_at": now,
        }
        repo._audit(c, company_ref_id=company_ref_id, actor=actor, action="append_table_override", entity_type="analyst_table_override", entity_id=f"{table_key}|{period_key}|{metric_key}|v{version}", before=old_d, after=after)
        return version


def latest_table_overrides(repo, company_ref_id: int, table_key: str) -> dict[tuple[str, str], dict[str, Any]]:
    ensure_extension_schema(repo)
    with repo._conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM analyst_table_overrides WHERE company_ref_id=? AND table_key=? ORDER BY period_key,metric_key,version_no",
            (company_ref_id, str(table_key)),
        )]
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        latest[(str(row["period_key"]), str(row["metric_key"]))] = row
    return latest


def table_override_history(repo, company_ref_id: int, table_key: str, limit: int = 200) -> list[dict[str, Any]]:
    ensure_extension_schema(repo)
    with repo._conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM analyst_table_overrides WHERE company_ref_id=? AND table_key=? ORDER BY created_at DESC,version_no DESC LIMIT ?",
            (company_ref_id, str(table_key), int(limit)),
        )]


def override_value(row: dict[str, Any]) -> Any:
    return row.get("value_numeric") if row.get("value_numeric") is not None else row.get("value_text")
