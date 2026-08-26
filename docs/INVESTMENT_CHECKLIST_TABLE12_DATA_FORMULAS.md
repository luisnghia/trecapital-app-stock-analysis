# Investment Checklist — Table 1.2 Data & Formula Rules

## Single Source of Truth

Investment Checklist consumes Trecapital's normalized data. It must not create an independent financial-data stack. The temporary FireAnt debt enricher reads only the raw FireAnt audit payload already downloaded by Trecapital; it does not make an additional external request. The long-term target is to move the debt aliases into the canonical Trecapital mapper and remove the compatibility layer.

## Total Debt

`Total Debt` means gross interest-bearing debt, not total liabilities.

Priority:
1. validated `interest_bearing_debt_bil` when positive and source-supported;
2. aggregate short-term borrowing / finance-lease debt + aggregate long-term borrowing / finance-lease debt;
3. detailed debt components only when aggregate rows are unavailable.

A synthetic `interest_bearing_debt_bil = 0` without supporting debt components is treated as **unknown**, not as a debt-free company. Aggregate short/long borrowing rows must not be added together with bond detail if that would double-count the same debt.

## TEV

When all inputs are source-supported:

`Net Debt = Gross Interest-Bearing Debt - Cash - Short-Term Investments`

`TEV = Market Capitalization + Net Debt`

If gross debt is unknown, TEV is also unknown. The app must not silently assume zero debt merely to produce a TEV value.

## EBIT / EBITDA / FCF

Checklist first consumes the Trecapital canonical fields. Allowed proxies are only used when the required Trecapital statement components exist and are explicitly disclosed in the UI/source note.

## Cash Conversion Cycle (CCC)

Prefer Trecapital's direct CCC/DSO/DIO/DPO fields. If direct CCC is unavailable and statement inputs exist:

`CCC = DIO + DSO - DPO`

Historical proxy calculations use average Inventory / Accounts Receivable / Accounts Payable when prior-period balances are available.

## 10Y + TTM + Review History

Table 1.2 combines:
- up to 10 latest fiscal years from Trecapital;
- current TTM;
- actual saved analyst review/snapshot versions.

All rows are sorted on one timeline, newest to oldest. For equal as-of dates, saved review/snapshot versions are ordered by version number, newest first. Current Target/MOS must never be backfilled into historical years; historical Target/MOS appear only when an actual historical review/snapshot exists.

## Mandatory Review Reasons

Production UI requires an explicit reason before:
- creating a review;
- saving Table 1.1 changes;
- saving an automatic Table 1.2 snapshot;
- saving an analyst-adjusted Table 1.2 snapshot;
- saving a Q01-Q59 assessment version;
- finalizing and locking a review.

Review creation and finalization reasons are persisted on `research_reviews` as `review_reason` and `finalize_reason`. Legacy/imported records remain readable and are labelled as legacy when no historical reason existed.
