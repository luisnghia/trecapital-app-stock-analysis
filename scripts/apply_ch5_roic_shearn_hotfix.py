from __future__ import annotations

"""Idempotent Chapter 5 Q26 methodology hotfix.

Source lock: Michael Shearn, The Investment Checklist, Chapter 5, "Methods of Calculating ROIC".
The canonical Trecapital ROIC remains untouched. Only rows labelled Shearn analytical are changed
from the earlier NOPAT/financing-capital implementation to Adjusted EBIT / average adjusted
investment base.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "modules" / "deep_company_analysis" / "chapter5_quant.py"
SUPPORT = ROOT / "modules" / "deep_company_analysis" / "chapter5_page_support.py"

quant = QUANT.read_text(encoding="utf-8")

replacement = r'''def _included_flag(row: dict[str, Any]) -> bool:
    included = str(row.get("Included?") or "").strip().casefold()
    return included in {"1", "true", "yes", "y", "x", "✓", "included", "có", "co"}


def _adjustment_sum(
    adjustments: Iterable[dict[str, Any]] | None,
    needles: tuple[str, ...],
    *,
    absolute: bool = True,
) -> Optional[float]:
    """Sum explicitly included named adjustments.

    Denominator adjustments such as excess cash and off-BS capital are treated as magnitudes.
    The engine never invents an adjustment when the analyst has not explicitly included it.
    """
    values: list[float] = []
    for row in adjustments or []:
        if not isinstance(row, dict) or not _included_flag(row):
            continue
        name = str(row.get("Adjustment") or "").casefold()
        if not any(needle.casefold() in name for needle in needles):
            continue
        value = _safe_float(row.get("Amount"))
        if value is not None:
            values.append(abs(value) if absolute else value)
    return sum(values) if values else None


def _numerator_adjustment_sum(adjustments: Iterable[dict[str, Any]] | None) -> float:
    """Return analyst-confirmed *signed* EBIT adjustments.

    Positive amounts add to EBIT; negative amounts subtract from EBIT. The app does not decide the
    sign of restructuring, impairment, amortization or any other non-recurring item for the analyst.
    A row must explicitly target the Numerator (or Both) to be used.
    """
    total = 0.0
    for row in adjustments or []:
        if not isinstance(row, dict) or not _included_flag(row):
            continue
        target = str(row.get("Numerator / Denominator") or "").strip().casefold()
        if not ("numerator" in target or target in {"both", "cả hai", "ca hai"}):
            continue
        value = _safe_float(row.get("Amount"))
        if value is not None:
            total += value
    return total


def _adjusted_ebit(
    row: dict[str, Any],
    adjustments: Iterable[dict[str, Any]] | None = None,
) -> tuple[Optional[float], str]:
    """Shearn numerator: operating earnings before interest and taxes, plus signed analyst adjustments."""
    ebit = _metric(row, "ebit")
    if ebit is None:
        return None, "Adjusted EBIT unavailable — canonical EBIT/operating profit missing"
    signed_adjustment = _numerator_adjustment_sum(adjustments)
    if abs(signed_adjustment) > 1e-12:
        return ebit + signed_adjustment, f"Canonical EBIT + analyst-confirmed signed numerator adjustments ({signed_adjustment:,.2f})"
    return ebit, "Canonical EBIT / operating profit; no analyst numerator adjustment included"


def _non_interest_bearing_current_liabilities(row: dict[str, Any]) -> tuple[Optional[float], str]:
    """Return NIBCL without guessing financing liabilities.

    Prefer an explicit normalized NIBCL field. Otherwise use Current Liabilities minus explicit
    short-term interest-bearing debt. If neither route is supportable, remain Unknown.
    """
    explicit = _pick(
        row,
        "non_interest_bearing_current_liabilities_bil",
        "nibcl_bil",
        "operating_current_liabilities_bil",
    )
    if explicit is not None:
        return explicit, "Canonical/normalized non-interest-bearing current liabilities"

    current_liabilities = _metric(row, "current_liabilities")
    short_debt = _metric(row, "short_debt")
    if current_liabilities is not None and short_debt is not None:
        return max(0.0, current_liabilities - abs(short_debt)), "Proxy = Current Liabilities − short-term interest-bearing debt"

    total_debt = _debt(row)
    if current_liabilities is not None and total_debt is not None and abs(total_debt) < 1e-12:
        return current_liabilities, "Current Liabilities treated as NIBCL because canonical interest-bearing debt = 0"
    return None, "NIBCL unavailable — app does not assume all current liabilities are non-interest-bearing"


def _shearn_net_asset_base(row: dict[str, Any]) -> tuple[Optional[float], str]:
    assets = _metric(row, "assets")
    nibcl, nibcl_source = _non_interest_bearing_current_liabilities(row)
    if assets is None or nibcl is None:
        return None, f"Net investment base unavailable: Total Assets={assets}; {nibcl_source}"
    return assets - nibcl, f"Total Assets − NIBCL; {nibcl_source}"


def _average_strict(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Shearn explicitly asks the analyst to use average investment-base amounts."""
    if current is None or previous is None:
        return None
    return (current + previous) / 2.0


def build_roic_variants(
    annual_df: pd.DataFrame,
    adjustments: Iterable[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Build canonical ROIC plus source-locked Shearn analytical views.

    Trecapital Canonical ROIC remains the Single Source of Truth and is read, not recalculated.
    Every row whose Origin is ``Shearn analytical`` uses:

        Adjusted EBIT / Average Adjusted Invested Capital

    following Shearn's Chapter-5 basic equation. The investment base starts from Total Assets,
    subtracts non-interest-bearing current liabilities, and then applies the specific cash,
    goodwill, gross-asset or off-balance-sheet view. Missing/unsupported inputs remain Unknown.
    """
    rows = _annual_rows(annual_df)
    current = rows[-1] if rows else _current_row(annual_df)
    previous = rows[-2] if len(rows) >= 2 else {}
    if not current:
        return pd.DataFrame()

    canonical = _metric(current, "roic")
    adjusted_ebit, numerator_source = _adjusted_ebit(current, adjustments)

    base_cur, base_cur_source = _shearn_net_asset_base(current)
    base_prev, base_prev_source = _shearn_net_asset_base(previous) if previous else (None, "Prior-period investment base unavailable")
    avg_with_cash = _average_strict(base_cur, base_prev)
    base_source = f"Average of period-end [Total Assets − NIBCL]. Current: {base_cur_source}. Prior: {base_prev_source}."

    roic_with_cash = _ratio(adjusted_ebit, avg_with_cash, 100.0)

    excess_cash = _adjustment_sum(adjustments, ("excess cash", "tiền dư thừa", "tien du thua"), absolute=True)
    base_ex_excess = None
    if avg_with_cash is not None and excess_cash is not None:
        candidate = avg_with_cash - excess_cash
        base_ex_excess = candidate if candidate > 1e-12 else None
    roic_ex_excess = _ratio(adjusted_ebit, base_ex_excess, 100.0)

    goodwill_cur = _metric(current, "goodwill")
    goodwill_prev = _metric(previous, "goodwill") if previous else None
    avg_goodwill = _average_strict(goodwill_cur, goodwill_prev)

    # Total Assets already includes goodwill/intangibles. Thus the ex-excess-cash base is the
    # "including goodwill" view unless the analyst explicitly removes goodwill below.
    roic_incl_goodwill = _ratio(adjusted_ebit, base_ex_excess, 100.0)
    ex_goodwill_den = None
    if base_ex_excess is not None and avg_goodwill is not None:
        candidate = base_ex_excess - avg_goodwill
        ex_goodwill_den = candidate if candidate > 1e-12 else None
    roic_ex_goodwill = _ratio(adjusted_ebit, ex_goodwill_den, 100.0)

    gross_cur, net_cur = _metric(current, "gross_ppe"), _metric(current, "net_ppe")
    gross_prev = _metric(previous, "gross_ppe") if previous else None
    net_prev = _metric(previous, "net_ppe") if previous else None
    avg_gross = _average_strict(gross_cur, gross_prev)
    avg_net = _average_strict(net_cur, net_prev)
    accumulated_dep_proxy = None
    if avg_gross is not None and avg_net is not None:
        accumulated_dep_proxy = max(0.0, avg_gross - avg_net)
    gross_den = (base_ex_excess + accumulated_dep_proxy) if base_ex_excess is not None and accumulated_dep_proxy is not None else None
    roic_gross = _ratio(adjusted_ebit, gross_den, 100.0)

    off_bs = _adjustment_sum(
        adjustments,
        ("off-bs", "off balance", "off-balance", "ngoài bảng", "ngoai bang"),
        absolute=True,
    )
    off_den = (base_ex_excess + off_bs) if base_ex_excess is not None and off_bs is not None else None
    roic_off = _ratio(adjusted_ebit, off_den, 100.0)

    period = _period(current)
    common = {
        "Kỳ": period,
        "Numerator (tỷ)": adjusted_ebit,
        "Numerator Source": numerator_source,
    }
    return pd.DataFrame([
        {
            **common,
            "ROIC View": "Trecapital Canonical ROIC",
            "Origin": "Trecapital canonical",
            "Value %": canonical,
            "Denominator (tỷ)": None,
            "Denominator Source": "Canonical Trecapital normalized invested-capital methodology",
            "Status / Requirement": "Single Source of Truth",
            "Formula / Note": "Read directly from canonical normalized data; this row is not recalculated by Chapter 5.",
        },
        {
            **common,
            "ROIC View": "ROIC with cash",
            "Origin": "Shearn analytical",
            "Value %": roic_with_cash,
            "Denominator (tỷ)": avg_with_cash,
            "Denominator Source": base_source,
            "Status / Requirement": "Computed from Adjusted EBIT + average asset-based investment base" if roic_with_cash is not None else "Requires EBIT + two-period Total Assets + NIBCL",
            "Formula / Note": "Adjusted EBIT / Average[Total Assets − non-interest-bearing current liabilities]. Cash remains in the asset base.",
        },
        {
            **common,
            "ROIC View": "ROIC ex excess cash",
            "Origin": "Shearn analytical",
            "Value %": roic_ex_excess,
            "Denominator (tỷ)": base_ex_excess,
            "Denominator Source": base_source,
            "Status / Requirement": "Computed from analyst-confirmed excess cash" if roic_ex_excess is not None else "Requires analyst-confirmed Excess Cash adjustment + average investment base",
            "Formula / Note": "Adjusted EBIT / [Average asset-based investment base − analyst-confirmed excess cash]. App never assumes all cash is excess cash.",
        },
        {
            **common,
            "ROIC View": "ROIC including goodwill",
            "Origin": "Shearn analytical",
            "Value %": roic_incl_goodwill,
            "Denominator (tỷ)": base_ex_excess,
            "Denominator Source": base_source,
            "Status / Requirement": "Computed; goodwill retained in Total Assets" if roic_incl_goodwill is not None else "Requires analyst-confirmed excess cash + average investment base",
            "Formula / Note": "Adjusted EBIT / ex-excess-cash investment base with goodwill/intangibles retained.",
        },
        {
            **common,
            "ROIC View": "ROIC ex goodwill",
            "Origin": "Shearn analytical",
            "Value %": roic_ex_goodwill,
            "Denominator (tỷ)": ex_goodwill_den,
            "Denominator Source": base_source,
            "Status / Requirement": "Computed from average goodwill" if roic_ex_goodwill is not None else "Requires goodwill + analyst-confirmed excess cash + average investment base",
            "Formula / Note": "Adjusted EBIT / [ex-excess-cash investment base − Average Goodwill]. Use alongside the including-goodwill view; do not erase acquisition economics.",
        },
        {
            **common,
            "ROIC View": "ROIC gross-asset adjusted",
            "Origin": "Shearn analytical",
            "Value %": roic_gross,
            "Denominator (tỷ)": gross_den,
            "Denominator Source": base_source,
            "Status / Requirement": "Computed using gross-vs-net PP&E depreciation proxy" if roic_gross is not None else "Requires Gross PP&E + Net PP&E + analyst-confirmed excess cash + average investment base",
            "Formula / Note": "Adjusted EBIT / [ex-excess-cash base + max(0, Average Gross PP&E − Average Net PP&E)]. Diagnostic proxy for accumulated depreciation/asset aging.",
        },
        {
            **common,
            "ROIC View": "ROIC off-BS adjusted",
            "Origin": "Shearn analytical",
            "Value %": roic_off,
            "Denominator (tỷ)": off_den,
            "Denominator Source": base_source,
            "Status / Requirement": "Computed from analyst-confirmed off-BS capital" if roic_off is not None else "Requires analyst-confirmed Off-Balance-Sheet adjustment + excess-cash base",
            "Formula / Note": "Adjusted EBIT / [ex-excess-cash investment base + analyst-confirmed material off-BS capital]. No lease/pension/other obligation is invented.",
        },
    ])
'''

pattern = re.compile(
    r"def _adjustment_amount\(.*?\n\ndef build_roic_distortion_diagnostics",
    re.S,
)
if pattern.search(quant):
    quant = pattern.sub(replacement + "\n\ndef build_roic_distortion_diagnostics", quant, count=1)
elif "def _adjusted_ebit(" not in quant or "Adjusted EBIT / Average[Total Assets" not in quant:
    raise SystemExit("chapter5_quant.py: expected legacy ROIC block not found")

# Add an explicit guardrail signal while preserving the all-False convention.
old_guard = '            "auto_compounder_conclusion": False,\n            "assume_all_cash_is_excess": False,'
new_guard = '            "auto_compounder_conclusion": False,\n            "shearn_variants_use_nopat": False,\n            "assume_all_cash_is_excess": False,'
if old_guard in quant:
    quant = quant.replace(old_guard, new_guard, 1)
elif '"shearn_variants_use_nopat": False' not in quant:
    raise SystemExit("chapter5_quant.py: quantitative guardrail marker not found")

QUANT.write_text(quant, encoding="utf-8")

support = SUPPORT.read_text(encoding="utf-8")

support = support.replace(
    "adjustments_signature: tuple[tuple[str, str, str], ...],",
    "adjustments_signature: tuple[tuple[str, str, str, str], ...],",
)
support = support.replace(
    '''    adjustments = [\n        {"Adjustment": name, "Amount": amount, "Included?": included}\n        for name, amount, included in adjustments_signature\n    ]''',
    '''    adjustments = [\n        {"Adjustment": name, "Numerator / Denominator": target, "Amount": amount, "Included?": included}\n        for name, target, amount, included in adjustments_signature\n    ]''',
)
support = support.replace(
    "def _adjustment_signature(record: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:",
    "def _adjustment_signature(record: dict[str, Any]) -> tuple[tuple[str, str, str, str], ...]:",
)
support = support.replace(
    "    out: list[tuple[str, str, str]] = []",
    "    out: list[tuple[str, str, str, str]] = []",
)
support = support.replace(
    '''        out.append((\n            str(row.get("Adjustment") or ""),\n            str(row.get("Amount") or ""),\n            str(row.get("Included?") or ""),\n        ))''',
    '''        out.append((\n            str(row.get("Adjustment") or ""),\n            str(row.get("Numerator / Denominator") or ""),\n            str(row.get("Amount") or ""),\n            str(row.get("Included?") or ""),\n        ))''',
)

old_info = (
    '                "Canonical ROIC là Single Source of Truth. Các dòng Shearn analytical chỉ là góc nhìn điều chỉnh. "\n'
    '                "ROIC ex excess cash KHÔNG được tính nếu analyst chưa xác nhận lượng excess cash; off-BS adjusted cũng vậy."'
)
new_info = (
    '                "Canonical ROIC là Single Source of Truth và giữ nguyên methodology của Trecapital. "\n'
    '                "Các dòng Shearn analytical dùng Adjusted EBIT / Average Adjusted Invested Capital theo Chương 5 — KHÔNG dùng NOPAT. "\n'
    '                "ROIC ex excess cash chỉ tính khi analyst xác nhận excess cash; off-BS adjusted cũng chỉ dùng adjustment đã xác nhận."'
)
if old_info in support:
    support = support.replace(old_info, new_info, 1)
elif "Các dòng Shearn analytical dùng Adjusted EBIT" not in support:
    raise SystemExit("chapter5_page_support.py: Q26 info marker not found")

SUPPORT.write_text(support, encoding="utf-8")
print("Applied Chapter 5 source-locked Shearn ROIC methodology hotfix")
