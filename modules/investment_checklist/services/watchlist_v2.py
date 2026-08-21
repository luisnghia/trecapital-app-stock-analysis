from __future__ import annotations

"""Watchlist v2: no write-on-rerun, strict latest-review semantics, effective Table 1.2 overlays."""

from typing import Any

from .portfolio_extensions import compute_5y_cagrs, ensure_extension_schema


_DISPLAY_TO_FIELD = {
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


def _same_number(a: Any, b: Any, tol: float = 1e-12) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return str(a) == str(b)


def refresh_watchlist_cagrs_if_changed(repo, company_ref_id: int, *, provider, actor: str = "system") -> bool:
    """Refresh CAGR cache only when endpoints/source changed; normal reruns are read-only."""
    ensure_extension_schema(repo)
    cg = compute_5y_cagrs(provider)
    with repo._conn() as c:
        row = c.execute("SELECT * FROM checklist_watchlist WHERE company_ref_id=?", (company_ref_id,)).fetchone()
        if row is None:
            return False
        old = dict(row)
        unchanged = (
            _same_number(old.get("revenue_cagr_5y"), cg.get("revenue_cagr_5y"))
            and _same_number(old.get("profit_cagr_5y"), cg.get("profit_cagr_5y"))
            and str(old.get("cagr_source_period") or "") == str(cg.get("cagr_source_period") or "")
        )
        if unchanged:
            return False
        from .portfolio_extensions import _now
        now = _now()
        c.execute(
            "UPDATE checklist_watchlist SET revenue_cagr_5y=?,profit_cagr_5y=?,cagr_source_period=?,updated_at=? WHERE company_ref_id=?",
            (cg.get("revenue_cagr_5y"), cg.get("profit_cagr_5y"), cg.get("cagr_source_period"), now, company_ref_id),
        )
        after = dict(c.execute("SELECT * FROM checklist_watchlist WHERE company_ref_id=?", (company_ref_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, actor=actor, action="refresh_watchlist_cagr", entity_type="watchlist", entity_id=company_ref_id, before=old, after=after)
        return True


def _effective_latest_review_inventory(c, company_ref_id: int, review: dict[str, Any] | None) -> dict[str, Any]:
    """Never silently substitute a prior review's Table 1.2 when the latest review has none."""
    if not review:
        return {}
    row = c.execute(
        "SELECT * FROM opportunity_inventory_snapshots WHERE company_ref_id=? AND last_review_id=? ORDER BY as_of_date DESC,version_no DESC,id DESC LIMIT 1",
        (company_ref_id, review["id"]),
    ).fetchone()
    inv = dict(row) if row else {}
    if not inv:
        return {}

    # Apply generic analyst corrections made to the exact latest-review Table 1.2 row.
    prefix = f"{inv.get('as_of_date')} | Review/snapshot #{review['id']}"
    overrides = [dict(r) for r in c.execute(
        "SELECT * FROM analyst_table_overrides WHERE company_ref_id=? AND table_key='Table 1.2' AND period_key LIKE ? ORDER BY metric_key,version_no",
        (company_ref_id, prefix + "%"),
    )]
    latest: dict[str, dict[str, Any]] = {}
    for ov in overrides:
        latest[str(ov.get("metric_key"))] = ov
    for display_metric, ov in latest.items():
        field = _DISPLAY_TO_FIELD.get(display_metric)
        if not field:
            continue
        value = ov.get("value_numeric") if ov.get("value_numeric") is not None else ov.get("value_text")
        if field == "mos" and value is not None:
            # Table display/editor uses percentage points, snapshot storage uses decimal MOS.
            try:
                value = float(value) / 100.0
            except Exception:
                pass
        inv[field] = value
    return inv


def list_watchlist_rows_v2(repo) -> list[dict[str, Any]]:
    """Watchlist = latest review + that review's effective Table 1.2, never stale prior-review substitution."""
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
            inv = _effective_latest_review_inventory(c, w["company_ref_id"], rv)
            out.append({
                **inv,
                "company_ref_id": w["company_ref_id"],
                "ticker": co.get("ticker"),
                "company_name": co.get("company_name"),
                "exchange": co.get("exchange"),
                "latest_review_id": rv.get("id") if rv else None,
                "latest_review_as_of": rv.get("as_of_date") if rv else None,
                "latest_review_status": rv.get("status") if rv else None,
                "latest_review_has_inventory": bool(inv),
                "revenue_cagr_5y": w.get("revenue_cagr_5y"),
                "profit_cagr_5y": w.get("profit_cagr_5y"),
                "cagr_source_period": w.get("cagr_source_period"),
                "watchlist_added_at": w.get("added_at"),
            })
    return out
