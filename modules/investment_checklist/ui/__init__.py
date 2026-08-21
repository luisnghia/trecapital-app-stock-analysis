from . import page as _page


def _ttm_first_period_sort_date(period, current_as_of=None):
    """Sort Table 1.2 with TTM/T12M as the absolute first row.

    Review/snapshot and annual rows are then sorted newest-to-oldest by their real date.
    This package-level override keeps the deployed Phase 1C page behavior explicit without
    treating the literal label ``TTM`` as a parseable calendar date.
    """
    text = str(period or "").strip()
    upper = text.upper()
    if "TTM" in upper or "T12M" in upper:
        return _page.pd.Timestamp.max.normalize()
    if text.isdigit() and len(text) == 4:
        text = f"{text}-12-31"
    dt = _page.pd.to_datetime(text, errors="coerce")
    return dt if _page.pd.notna(dt) else _page.pd.Timestamp.min


_page._period_sort_date = _ttm_first_period_sort_date
render_investment_checklist = _page.render_investment_checklist

__all__ = ["render_investment_checklist"]
