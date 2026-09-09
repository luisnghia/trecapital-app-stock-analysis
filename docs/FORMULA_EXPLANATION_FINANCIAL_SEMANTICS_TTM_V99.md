# Formula Explanation — Financial Semantics & TTM V99

## A. Profit-scope compatibility alias

V99 preserves three concepts:

- `PAT_consolidated = net_profit_consolidated_bil`
- `PAT_parent = net_profit_parent_bil`
- `PAT_legacy = net_profit_bil`

The compatibility alias is selected as:

`PAT_legacy = PAT_parent, if explicit; else existing PAT_legacy; else PAT_consolidated`

This selection exists so legacy formulas keep operating while the dataset separately preserves the economic/accounting scope.

Scope is set as:

- `parent_attributable` if `PAT_parent` exists;
- else `consolidated` if `PAT_consolidated` exists;
- else `unspecified` if only the legacy field exists;
- else Unknown.

A consolidated value may populate the legacy compatibility field, but it is **not** renamed or inferred as parent-attributable.

## B. EPS derivation

When EPS is not separately sourced:

`EPS = PAT_parent × 1,000 / Shares_outstanding_million`

because PAT is in billion VND and shares are in million shares.

If only a legacy PAT exists and its scope is not explicitly consolidated, the prior compatibility behavior is retained:

`EPS = PAT_legacy × 1,000 / Shares_outstanding_million`

If the only explicit fact is consolidated PAT:

`EPS = Unknown`

until parent-attributable PAT or EPS is separately sourced.

This is a data-validity guardrail, not a new valuation formula.

## C. TTM flow calculation

For a flow metric `F` and the latest four quarterly observations `Q1..Q4` in chronological order:

`TTM(F) = F(Q1) + F(Q2) + F(Q3) + F(Q4)`

**only if all four quarterly values are non-null.**

If the number of available component quarters is less than four:

`TTM(F) = Unknown`

V99 explicitly rejects the old behavior of summing 1–3 available quarters and labelling that partial sum `TTM`.

## D. TTM stock / balance fields

Point-in-time balance-sheet fields retain the latest available quarter:

`TTM_balance = LatestQuarter(balance)`

Existing trailing-average denominator fields remain calculated from the trailing quarterly balances according to their pre-V99 logic.

## E. TTM period provenance

Compatibility storage:

`period = "TTM"`

Research display when latest quarter/year are available:

`ttm_end_period = "Q{quarter}/{year}"`

`period_display = "TTM đến " + ttm_end_period`

Example:

`period = TTM`, `ttm_end_period = Q2/2026`, `period_display = TTM đến Q2/2026`.

If the end quarter cannot be determined, the legacy display stays `TTM` and a semantic warning is emitted. The app does not invent an ending period.

## F. Comparability metadata

`comparability_status` and `comparability_note` are metadata only. V99 does not infer a corporate restructuring, accounting reclassification, or restatement automatically from the numbers. They remain source/analyst supplied.

## G. Source boundary

The Investment Checklist source supports uncertainty-aware research and careful treatment of cyclical/variable earnings. The exact field mapping, four-quarter completeness rule and provenance schema in this document are Trecapital engineering controls; they are not represented as formulas quoted from Michael Shearn.
