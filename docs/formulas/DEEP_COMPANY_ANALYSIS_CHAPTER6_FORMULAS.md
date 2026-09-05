# Deep Company Analysis — Chapter 6 Formula & Methodology Notes

Source framework: Michael Shearn, *The Investment Checklist*, Chapter 6 — **Evaluating the Distribution of Earnings (Cash Flows)**.

Status: Phase 6A source lock. Computed metrics are deferred to Phase 6B unless explicitly noted.

## Core rule

Chapter 6 is not a scoring model. Quantitative metrics are evidence for Q27–Q32; they do not automatically create analyst conclusions.

Canonical financial values must come from the Trecapital Data Layer. Chapter 6 may calculate transparent derived metrics from canonical fields, but may not maintain a parallel financial data source.

## Q27 — Accounting quality

### CFO versus Net Income

Phase 6B may show, by period:

`CFO / Net Income`

and:

`CFO - Net Income`

Interpretation is contextual. A persistent gap is a research trigger, not proof of manipulation.

### Current tax vs income-tax provision

Shearn's Key Points state that a difference below 10% is associated with conservative accounting in his framework. This is a **source-specific heuristic**, not a universal accounting rule.

If the canonical Trecapital dataset does not separately contain current tax paid / current tax expense and total income-tax provision, the app must display `N/A / insufficient source data` rather than synthesize the figures.

### Provision versus actual charge-off

For reserve categories with disclosed data, Phase 6B may calculate:

`Provision gap = Provision / Estimate - Actual Outcome / Charge-off`

and optionally:

`Provision coverage = Provision / Actual Outcome`

A large difference alone is not a manipulation verdict. The source asks the analyst to inspect multi-year patterns and the underlying reason.

## Q28 — Recurring revenue

No universal formula is source-locked for recurring-revenue share.

If the company directly discloses recurring/contracted revenue, the app may display the disclosed percentage with provenance.

If the analyst enters an estimate:

`Recurring revenue share = Analyst-supported recurring revenue / Total revenue`

it must be clearly marked `Analyst estimate`, never `Trecapital canonical`.

## Q29 — Cyclicality

Phase 6B may display historical:

- Revenue growth
- EBIT / operating-profit growth
- operating margin
- gross margin where available
- drawdowns from local revenue/EBIT peaks

These measures describe historical earnings variability. They do **not** prove that GDP, commodity prices or a recession caused the change unless evidence establishes that causal link.

No automatic `Cyclical / Countercyclical / Recession-resistant` label is permitted.

## Q30 — Operating leverage

A transparent historical diagnostic consistent with the source concept is:

`DOL ≈ %Δ Operating Income / %Δ Revenue`

Implementation guardrails:

- use operating income / EBIT from the canonical Trecapital dataset;
- do not compute when prior-period revenue or EBIT makes the percentage change undefined or economically meaningless;
- do not average extreme/invalid observations without displaying them;
- show period-by-period history before any summary statistic;
- a high DOL observation is evidence, not an automatic conclusion.

### Trecapital stress extension

A revenue stress such as -5%, -10% or -20% is an **app extension**, not a table copied from Shearn. It must be labelled clearly as a scenario tool and may only use analyst-confirmed cost-structure assumptions or transparent historical sensitivities.

## Q31 — Working capital / CCC

### Cash conversion cycle

`CCC = DIO + DSO - DPO`

where the component definitions should be held consistently through time.

Typical transparent forms, subject to canonical field availability:

`DSO = Average Accounts Receivable / Revenue × Days`

`DIO = Average Inventory / COGS × Days`

`DPO = Average Accounts Payable / COGS × Days`

For annual periods use the appropriate day count consistently. For TTM, use a consistent TTM convention and label it.

The book requires the analyst to examine at least five years of CCC history and explain movements in DIO, DSO and DPO.

### Operating working capital

Chapter 6 must use **operating** working capital, excluding cash, investments and financing debt when building a derived OWC measure.

A transparent form is:

`OWC = Operating Current Assets - Operating Current Liabilities`

The cash impact of a period change depends on the cash-flow sign convention. The app must label the convention explicitly and reconcile it to the canonical cash-flow statement where available.

A falling CCC or negative working capital is not automatically positive. Supplier-stretch or a reversal of customer prepayments can create future cash demands.

## Q32 — Capital expenditure requirements

### Total capex intensity

`Capex intensity = Total Capex / Revenue`

Shearn notes that many capital-intensive examples in the chapter exceed approximately 0.20 capex per 1.00 of revenue. Do not convert this observation into a universal hard cutoff.

### Capex versus depreciation

Phase 6B may display:

`Capex / D&A`

as an asset-investment diagnostic. It does not by itself identify maintenance capex.

### Free cash flow

When using the canonical Trecapital definition:

`FCF = CFO - Total Capex`

This is a total-capex cash-flow measure, not maintenance-capex distributable cash flow.

### Maintenance capex

Source concept:

**Maintenance capex** = investment necessary to keep the business in a steady state and maintain current cash flows / operating capability.

There is no single source-locked formula in Chapter 6 that mechanically extracts maintenance capex from reported total capex.

Therefore:

- use company disclosure where available;
- allow analyst input/estimate only with explicit evidence and provenance;
- otherwise show `Unknown`;
- never silently set `maintenance capex = total capex`;
- never use depreciation alone as a hidden maintenance-capex proxy.

### Asset-age diagnostic

Shearn discusses net assets versus gross assets as a way to investigate whether older assets may require higher future replacement expenditure. Phase 6B may expose such a ratio when gross and net PP&E are available, but it is a diagnostic rather than a maintenance-capex formula.

## Formatting and provenance

For every computed Chapter-6 metric, production UI should retain:

- `source_field`
- `source_module`
- `source_period`
- `data_origin`
- formula / methodology note

Display format follows Trecapital project rules:

- billion VND: no decimal places;
- percentages: 1 decimal place;
- ratios: 1 decimal place;
- negative values: red heat intensity;
- positive / positive-growth values: emerald heat intensity.

## Missing-data rule

Missing inputs must produce `Unknown`, `N/A`, or a documented coarse proxy. Missing data must never be interpreted as evidence of quality.
