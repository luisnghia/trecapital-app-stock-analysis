# Deep Company Analysis — Chapter 5 Formula Reference

## Boundary

Chapter 5 Phase 5B **consumes Trecapital canonical normalized statements**. It does not create a second financial source-of-truth. `Trecapital Canonical ROIC` remains the authoritative canonical ROIC. All other ROIC rows are explicitly analytical views inspired by the issues Michael Shearn asks the analyst to examine.

No formula in this document is a BUY/HOLD/SELL rule or an automatic quality score.

## Q22 — quantitative context

The bridge displays up to 10 annual observations of Revenue, Revenue Growth, Gross Margin, EBIT Margin, CFO, CAPEX, FCF and canonical ROIC. These are financial/operating context only. They **do not automatically become the critical operating KPIs** required by Q22.

- Revenue Growth = Revenue(t) / Revenue(t-1) − 1, when canonical YoY growth is unavailable.
- Gross Margin = Gross Profit / Revenue, only when the canonical margin field is unavailable.
- EBIT Margin = EBIT / Revenue, only when the canonical operating-margin field is unavailable.

## Q25 — balance-sheet context

- Net Debt = Interest-bearing Debt − Cash and Cash Equivalents.
- Debt / EBITDA = Interest-bearing Debt / EBITDA.
- EBIT / Interest = EBIT / absolute Interest Expense.
- CFO / Interest = CFO / absolute Interest Expense.
- Current Ratio = Current Assets / Current Liabilities.

A missing input produces `Unknown/—`; the app does not fill it with an estimate. Debt maturity, recourse, covenants and off-balance-sheet obligations remain disclosure/analyst fields.

**No fixed leverage threshold is an automatic Strong/Weak Balance Sheet conclusion.** Business cyclicality and cash-flow stability still matter.

## Q26 — canonical and analytical ROIC views

### 1. Trecapital Canonical ROIC

Read directly from Trecapital canonical normalized data. Phase 5B does not recalculate or overwrite it.

### 2. Analytical NOPAT proxy

When canonical/normalized NOPAT is present, use it. Otherwise, and only when EBIT, tax expense and pretax profit are all available:

`Effective Tax Rate = |Tax Expense| / Pretax Profit`, capped to 0%–60% for data-error containment.

`Analytical NOPAT Proxy = EBIT × (1 − Effective Tax Rate)`.

If those inputs are absent, NOPAT stays unknown. The engine does not assume a tax rate.

### 3. ROIC with cash

`ROIC with cash = NOPAT / Average(Equity + Interest-bearing Debt)`.

This is an analytical total-financing-capital view.

### 4. ROIC ex excess cash

`ROIC ex excess cash = NOPAT / [Average Total Financing Capital − Analyst-confirmed Excess Cash]`.

**The app never assumes all cash is excess cash.** If the analyst has not explicitly included an `Excess cash` adjustment in the Q26 adjustment register, this variant is not calculated.

### 5. ROIC including goodwill

Uses the ex-excess-cash capital base **without removing goodwill**. It is only computed when the excess-cash base is available.

### 6. ROIC ex goodwill

`ROIC ex goodwill = NOPAT / [Ex-excess-cash capital base − Average Goodwill]`.

This is a tangible operating-return view. It does not erase the economic fact that management may have paid goodwill in an acquisition; both views must be considered.

### 7. Gross-asset adjusted ROIC

When both Gross PP&E and Net PP&E are available:

`Adjusted capital base = Ex-excess-cash capital base + max(0, Average Gross PP&E − Average Net PP&E)`.

`Gross-asset adjusted ROIC = NOPAT / Adjusted capital base`.

This is a diagnostic for depreciation/aging-asset distortion, not a new canonical ROIC.

### 8. Off-balance-sheet adjusted ROIC

`Adjusted capital base = Ex-excess-cash capital base + Analyst-confirmed Off-Balance-Sheet Obligations`.

The adjustment is only used if the analyst explicitly marks it Included in Q26. No lease/pension/other obligation is invented.

## ROIC distortion diagnostics

The bridge surfaces **review diagnostics only**:

- Cash materiality: Cash / Total Assets.
- Goodwill materiality: Goodwill / Total Assets.
- Aging-asset candidate: over a three-year comparison, canonical ROIC rises by at least 3 percentage points while EBIT changes by no more than 15% and Net PP&E falls by at least 10%, when all inputs exist.

The last rule is a **Trecapital diagnostic heuristic**, not a rule stated by Shearn and not an automatic quality conclusion.

## Reinvestment / incremental-return context

Trecapital extension:

- `ΔNOPAT = NOPAT(t) − NOPAT(t-1)`.
- `ΔInvested Capital = Invested Capital(t) − Invested Capital(t-1)`.
- `Incremental ROIC = ΔNOPAT / ΔInvested Capital`, only when ΔInvested Capital > 0.

Invested Capital uses a canonical normalized invested-capital field when available; otherwise the bridge may use the descriptive proxy `Equity + Debt − Cash` and labels the output as a proxy. Incremental ROIC is highly sensitive to cyclicality and base effects, so it is analyst context only and never a compounder score.
