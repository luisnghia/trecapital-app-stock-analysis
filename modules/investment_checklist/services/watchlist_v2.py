from __future__ import annotations

"""Watchlist v2.1 — current financial-data semantics, independent from review chronology.

The Watchlist is an Opportunity Inventory, not a review archive. It therefore displays the latest
financial data loaded by the canonical Trecapital Data Layer for each ticker. Review history remains
available elsewhere and never determines which financial row the Watchlist shows.
"""

import json
from typing import Any

from .formulas import inventory_metrics
from .portfolio_extensions import compute_5y_cagrs, ensure_extension_schema, _now


WATCHLIST_FINANCIAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS checklist_watchlist_financials(
    company_ref_id BIGINT PRIMARY KEY REFERENCES checklist_company_refs(id),
    financial_as_of_date TEXT,
    source_module TEXT,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_BASE_DISPLAY_TO_FIELD = {
    "TEV": "tev",
    "EBIT": "ebit",
    "EBITDA": "ebitda",
    "Normalized earnings": "normalized_earnings",
    "Total Debt": "total_debt",
    "FCF": "fcf_current",
    "Market cap": "market_cap",
    "Giá": "market_price",
    "FCF est./share": "fcf_estimate",
    "Target": "target_price",
    "CCC": "ccc_days",
    "MOS": "mos",
}

_DERIVED_DISPLAY_TO_FIELD = {
    "TEV/EBIT": "tev_ebit",
    "TEV/EBITDA": "tev_ebitda",
    "TEV/Norm.E": "tev_normalized_earnings",
    "Pre-tax yield": "pretax_earnings_yield",
    "Debt/EBITDA": "debt_ebitda",
    "EBIT/Interest": "ebit_interest",
    "FCF Yield EV": "fcf_yield_ev",
    "FCF Yield Mkt": "fcf_yield_market",
}

_PERCENT_POINT_METRICS = {"Pre-tax yield", "FCF Yield EV", "FCF Yield Mkt", "MOS"}


def ensure_watchlist_financial_schema(repo) -> None:
    ensure_extension_schema(repo)
    with repo._conn() as c:
        c.execute(WATCHLIST_FINANCIAL_SCHEMA_SQL)


def _same_number(a: Any, b: Any, tol: float = 1e-12) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return str(a) == str(b)


def _provider_inventory(provider) -> dict[str, Any]:
    getter = getattr(provider, "get_inventory_source_data", None)
    data = getter(None) if callable(getter) else None
    if data is None:
        return {}
    row = {
        "as_of_date": getattr(data, "as_of_date", None),
        "tev": getattr(data, "tev", None),
        "ebit": getattr(data, "ebit", None),
        "ebitda": getattr(data, "ebitda", None),
        "normalized_earnings": getattr(data, "normalized_earnings", None),
        "total_debt": getattr(data, "total_debt", None),
        "interest_expense": getattr(data, "interest_expense", None),
        "fcf_current": getattr(data, "fcf_current", None),
        "market_cap": getattr(data, "market_cap", None),
        "dividend_per_share": getattr(data, "dividend_per_share", None),
        "market_price": getattr(data, "market_price", None),
        "fcf_estimate": getattr(data, "fcf_estimate", None),
        "target_price": getattr(data, "target_price", None),
        "ccc_days": getattr(data, "ccc_days", None),
        "mos": getattr(data, "mos", None),
        "source_module": getattr(data, "source_module", None),
    }
    row.update(
        inventory_metrics(
            tev=row.get("tev"),
            ebit=row.get("ebit"),
            ebitda=row.get("ebitda"),
            normalized_earnings=row.get("normalized_earnings"),
            total_debt=row.get("total_debt"),
            interest_expense=row.get("interest_expense"),
            fcf_current=row.get("fcf_current"),
            market_cap=row.get("market_cap"),
            dividend_per_share=row.get("dividend_per_share"),
            market_price=row.get("market_price"),
            target_price=row.get("target_price"),
        )
    )
    return row


def _latest_live_table12_overrides(c, company_ref_id: int, period_key: str) -> dict[str, dict[str, Any]]:
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM analyst_table_overrides WHERE company_ref_id=? AND table_key='Table 1.2' ORDER BY metric_key,version_no",
        (company_ref_id,),
    )]
    target = str(period_key or "").strip().upper()
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        pk = str(row.get("period_key") or "").strip()
        upper = pk.upper()
        matches = upper == target
        if target in {"TTM", "T12M"}:
            matches = upper in {"TTM", "T12M"}
        if matches:
            latest[str(row.get("metric_key"))] = row
    return latest


def _override_raw_value(row: dict[str, Any]) -> Any:
    return row.get("value_numeric") if row.get("value_numeric") is not None else row.get("value_text")


def _effective_current_financial(c, company_ref_id: int, provider) -> dict[str, Any]:
    """Latest canonical financial row plus analyst overlay for that live period."""
    row = _provider_inventory(provider)
    if not row:
        return {}
    period_key = str(row.get("as_of_date") or "")
    overrides = _latest_live_table12_overrides(c, company_ref_id, period_key)
    adjusted: list[str] = []

    # First apply base inputs, then recompute dependent ratios.
    for display, field in _BASE_DISPLAY_TO_FIELD.items():
        ov = overrides.get(display)
        if ov is None:
            continue
        value = _override_raw_value(ov)
        if display in _PERCENT_POINT_METRICS and value is not None:
            try:
                value = float(value) / 100.0
            except Exception:
                pass
        row[field] = value
        adjusted.append(display)

    row.update(
        inventory_metrics(
            tev=row.get("tev"),
            ebit=row.get("ebit"),
            ebitda=row.get("ebitda"),
            normalized_earnings=row.get("normalized_earnings"),
            total_debt=row.get("total_debt"),
            interest_expense=row.get("interest_expense"),
            fcf_current=row.get("fcf_current"),
            market_cap=row.get("market_cap"),
            dividend_per_share=row.get("dividend_per_share"),
            market_price=row.get("market_price"),
            target_price=row.get("target_price"),
        )
    )

    # A direct analyst correction to a displayed ratio has final precedence.
    for display, field in _DERIVED_DISPLAY_TO_FIELD.items():
        ov = overrides.get(display)
        if ov is None:
            continue
        value = _override_raw_value(ov)
        if display in _PERCENT_POINT_METRICS and value is not None:
            try:
                value = float(value) / 100.0
            except Exception:
                pass
        row[field] = value
        adjusted.append(display)

    row["analyst_adjusted_metrics"] = sorted(set(adjusted))
    return row


def has_watchlist_financial_cache(repo, company_ref_id: int) -> bool:
    ensure_watchlist_financial_schema(repo)
    with repo._conn() as c:
        return c.execute(
            "SELECT company_ref_id FROM checklist_watchlist_financials WHERE company_ref_id=?",
            (company_ref_id,),
        ).fetchone() is not None


def refresh_watchlist_cagrs_if_changed(repo, company_ref_id: int, *, provider, actor: str = "system") -> bool:
    """Refresh both current financial values and 5Y CAGR only when their effective values changed."""
    ensure_watchlist_financial_schema(repo)
    cg = compute_5y_cagrs(provider)
    now = _now()
    with repo._conn() as c:
        watch_row = c.execute("SELECT * FROM checklist_watchlist WHERE company_ref_id=?", (company_ref_id,)).fetchone()
        if watch_row is None:
            return False
        old_watch = dict(watch_row)
        financial = _effective_current_financial(c, company_ref_id, provider)
        payload = json.dumps(financial, ensure_ascii=False, sort_keys=True, default=str, allow_nan=False)
        old_fin_row = c.execute(
            "SELECT * FROM checklist_watchlist_financials WHERE company_ref_id=?",
            (company_ref_id,),
        ).fetchone()
        old_fin = dict(old_fin_row) if old_fin_row else None
        old_payload = str(old_fin.get("payload_json") or "") if old_fin else ""
        cagr_same = (
            _same_number(old_watch.get("revenue_cagr_5y"), cg.get("revenue_cagr_5y"))
            and _same_number(old_watch.get("profit_cagr_5y"), cg.get("profit_cagr_5y"))
            and str(old_watch.get("cagr_source_period") or "") == str(cg.get("cagr_source_period") or "")
        )
        financial_same = old_payload == payload
        if cagr_same and financial_same:
            return False

        c.execute(
            "UPDATE checklist_watchlist SET revenue_cagr_5y=?,profit_cagr_5y=?,cagr_source_period=?,updated_at=? WHERE company_ref_id=?",
            (cg.get("revenue_cagr_5y"), cg.get("profit_cagr_5y"), cg.get("cagr_source_period"), now, company_ref_id),
        )
        c.execute(
            """INSERT INTO checklist_watchlist_financials(company_ref_id,financial_as_of_date,source_module,payload_json,updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(company_ref_id) DO UPDATE SET financial_as_of_date=excluded.financial_as_of_date,
            source_module=excluded.source_module,payload_json=excluded.payload_json,updated_at=excluded.updated_at""",
            (company_ref_id, financial.get("as_of_date"), financial.get("source_module"), payload, now),
        )
        after = {
            "financial_as_of_date": financial.get("as_of_date"),
            "source_module": financial.get("source_module"),
            "revenue_cagr_5y": cg.get("revenue_cagr_5y"),
            "profit_cagr_5y": cg.get("profit_cagr_5y"),
            "cagr_source_period": cg.get("cagr_source_period"),
            "analyst_adjusted_metrics": financial.get("analyst_adjusted_metrics", []),
        }
        repo._audit(
            c,
            company_ref_id=company_ref_id,
            actor=actor,
            action="refresh_watchlist_financials",
            entity_type="watchlist_financials",
            entity_id=company_ref_id,
            before=old_fin,
            after=after,
        )
        return True


def list_watchlist_rows_v2(repo) -> list[dict[str, Any]]:
    """Return Watchlist from cached latest Trecapital financial data, never from latest review."""
    ensure_watchlist_financial_schema(repo)
    out: list[dict[str, Any]] = []
    with repo._conn() as c:
        watch = [dict(r) for r in c.execute("SELECT * FROM checklist_watchlist ORDER BY added_at DESC")]
        for w in watch:
            co_row = c.execute("SELECT * FROM checklist_company_refs WHERE id=?", (w["company_ref_id"],)).fetchone()
            if not co_row:
                continue
            co = dict(co_row)
            fin_row = c.execute(
                "SELECT * FROM checklist_watchlist_financials WHERE company_ref_id=?",
                (w["company_ref_id"],),
            ).fetchone()
            fin = dict(fin_row) if fin_row else None
            payload: dict[str, Any] = {}
            if fin and fin.get("payload_json"):
                try:
                    payload = json.loads(fin["payload_json"])
                except Exception:
                    payload = {}
            out.append({
                **payload,
                "company_ref_id": w["company_ref_id"],
                "ticker": co.get("ticker"),
                "company_name": co.get("company_name"),
                "exchange": co.get("exchange"),
                "financial_as_of_date": (fin or {}).get("financial_as_of_date"),
                "financial_source_module": (fin or {}).get("source_module"),
                "financial_updated_at": (fin or {}).get("updated_at"),
                "has_financial_cache": bool(fin),
                "revenue_cagr_5y": w.get("revenue_cagr_5y"),
                "profit_cagr_5y": w.get("profit_cagr_5y"),
                "cagr_source_period": w.get("cagr_source_period"),
                "watchlist_added_at": w.get("added_at"),
            })
    return out
