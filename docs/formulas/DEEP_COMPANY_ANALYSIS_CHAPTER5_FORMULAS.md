# Deep Company Analysis — Chapter 5 Formula Reference

## Boundary

Chapter 5 consumes **Trecapital canonical normalized statements**. It does not create a second financial source-of-truth.

Two ROIC methodologies are intentionally kept separate:

1. **Trecapital Canonical ROIC** — authoritative app-wide metric from the canonical Data Layer. Chapter 5 reads it directly and never recalculates or overwrites it.
2. **Shearn Analytical ROIC Views** — source-locked Chapter-5 analytical views based on Michael Shearn's basic equation: **Adjusted EBIT / Average Adjusted Invested Capital**.

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

# Q26 — ROIC methodology

## 1. Trecapital Canonical ROIC

`Trecapital Canonical ROIC` is read directly from the canonical normalized Data Layer. Chapter 5 does not alter its numerator or denominator.

The canonical metric may use NOPAT / Average Invested Capital according to the app-wide canonical methodology. That is deliberately separate from the Shearn analytical views below.

## 2. Michael Shearn source-locked basic equation

In Chapter 5, **Methods of Calculating ROIC**, Shearn states the basic equation as:

`ROIC = Earnings Before Interest and Taxes / Invested Capital`

The app therefore uses **Adjusted EBIT**, not NOPAT, for every row whose `Origin = Shearn analytical`.

Shearn's investment-base framework is represented as:

`Invested Capital = Total Assets − Excess Cash ± Accumulated Amortization and Depreciation ± Goodwill / Other Intangibles + Off-Balance-Sheet Items − Non-Interest-Bearing Current Liabilities`

The `±` items depend on the analytical view selected. Shearn explicitly notes that there is no single universally accepted ROIC calculation and that the calculation should be adapted to the business being analyzed.

### Average investment base is mandatory

Shearn warns against using one quarter-end snapshot and asks the analyst to use **average amounts for the investment base**. Therefore the source-locked analytical rows use two-period average investment-base amounts when the necessary inputs exist.

If the prior-period investment base is unavailable, the Shearn analytical row remains `Unknown`; the engine does not silently replace an average with a single-period denominator.

## 3. Shearn numerator — Adjusted EBIT

Base numerator:

`Adjusted EBIT = Canonical EBIT / Operating Profit + Analyst-confirmed signed numerator adjustments`

The goal is to isolate earnings from core operations before financing and tax effects.

The app does **not** use an effective-tax-rate/NOPAT proxy for Shearn analytical rows.

### Analyst numerator adjustments

The Q26 adjustment register may contain explicitly included numerator adjustments for non-recurring/restructuring/impairment/amortization or other analyst-identified items.

- Positive `Amount` **adds** to EBIT.
- Negative `Amount` **subtracts** from EBIT.
- The app does not decide the sign for the analyst.
- A row must explicitly target `Numerator` or `Both` and be marked Included before it affects Adjusted EBIT.

This preserves auditability and avoids automatic normalization guesses.

## 4. Non-interest-bearing current liabilities (NIBCL)

The Shearn investment base deducts non-interest-bearing current liabilities.

The engine uses the following order:

1. explicit canonical/normalized NIBCL field, when available;
2. otherwise: `Current Liabilities − Short-term Interest-bearing Debt`, but only when both fields are explicitly available;
3. if canonical interest-bearing debt is explicitly zero, Current Liabilities may be treated as NIBCL;
4. otherwise NIBCL remains Unknown.

The app does **not** assume all current liabilities are non-interest-bearing.

## 5. ROIC with cash

This is the comparison view before removing excess cash:

`ROIC with cash = Adjusted EBIT / Average[Total Assets − NIBCL]`

Cash remains inside Total Assets.

## 6. ROIC ex excess cash — Shearn core operating view

`ROIC ex excess cash = Adjusted EBIT / [Average(Total Assets − NIBCL) − Analyst-confirmed Excess Cash]`

**The app never assumes all cash is excess cash.** If the analyst has not explicitly included an Excess Cash adjustment, this row remains Unknown.

## 7. ROIC including goodwill

Total Assets already includes goodwill/intangibles. Therefore:

`ROIC including goodwill = Adjusted EBIT / Ex-excess-cash investment base with goodwill retained`

This view preserves acquisition capital in the denominator.

## 8. ROIC ex goodwill

`ROIC ex goodwill = Adjusted EBIT / [Ex-excess-cash investment base − Average Goodwill]`

This is a tangible operating-return view. It must be considered alongside the including-goodwill view so acquisition overpayment is not hidden.

## 9. Gross-asset adjusted ROIC

When both Gross PP&E and Net PP&E are available, the bridge uses the diagnostic proxy:

`Accumulated Depreciation Proxy = max(0, Average Gross PP&E − Average Net PP&E)`

`Gross-asset Adjusted Capital Base = Ex-excess-cash investment base + Accumulated Depreciation Proxy`

`Gross-asset adjusted ROIC = Adjusted EBIT / Gross-asset Adjusted Capital Base`

This is a diagnostic implementation of Shearn's gross-vs-net-asset discussion. It is not a new canonical ROIC.

## 10. Off-balance-sheet adjusted ROIC

`Off-BS Adjusted Capital Base = Ex-excess-cash investment base + Analyst-confirmed material Off-Balance-Sheet Capital`

`ROIC off-BS adjusted = Adjusted EBIT / Off-BS Adjusted Capital Base`

The adjustment is used only when the analyst explicitly includes it. No lease, pension, securitized receivable or other obligation is invented.

## ROIC distortion diagnostics

The bridge surfaces **review diagnostics only**:

- Cash materiality: Cash / Total Assets.
- Goodwill materiality: Goodwill / Total Assets.
- Aging-asset candidate: over a three-year comparison, canonical ROIC rises by at least 3 percentage points while EBIT changes by no more than 15% and Net PP&E falls by at least 10%, when all inputs exist.

The last rule is a **Trecapital diagnostic heuristic**, not a rule stated by Shearn and not an automatic quality conclusion.

## Reinvestment / incremental-return context — Trecapital extension

The separate reinvestment context remains a Trecapital analytical extension and is **not the Shearn basic ROIC formula**:

- `ΔNOPAT = NOPAT(t) − NOPAT(t-1)`.
- `ΔInvested Capital = Invested Capital(t) − Invested Capital(t-1)`.
- `Incremental ROIC = ΔNOPAT / ΔInvested Capital`, only when ΔInvested Capital > 0.

Invested Capital uses a canonical normalized invested-capital field when available; otherwise the bridge may use the descriptive proxy `Equity + Debt − Cash` and labels the output as a proxy.

Incremental ROIC is highly sensitive to cyclicality and base effects. It is analyst context only and never a compounder score.

## Hard boundary

The app must never:

- replace Trecapital Canonical ROIC with a Shearn analytical variant;
- use NOPAT in a row labelled `Shearn analytical`;
- assume all cash is excess cash;
- invent NIBCL, goodwill, off-BS capital or numerator adjustments;
- infer High-quality ROIC, Compounder, Research Gate, BUY/HOLD/SELL from any ROIC threshold.
