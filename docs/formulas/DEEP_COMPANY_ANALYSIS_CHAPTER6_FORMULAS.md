# Deep Company Analysis — Chapter 6 Formula & Methodology Notes

Source framework: Michael Shearn, *The Investment Checklist*, Chapter 6 — **Evaluating the Distribution of Earnings (Cash Flows)**.

Status: **APPROVED Phase 6A source lock + IMPLEMENTED Phase 6B canonical quantitative bridge (V31), with Q32 explicit-PP&E source guardrail added after V38 regression review**.

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

If the canonical Trecapital dataset does not separately contain current tax paid/current tax expense and total income-tax provision, the app must display `N/A / insufficient source data` rather than synthesize the figures.

### Reserve / provision roll-forward

For disclosed reserve categories, Phase 6A stores:

- Beginning Reserve
- Provision
- Write-offs / Usage
- Adjustments
- Ending Reserve
- Actual Outcome

Phase 6B may calculate:

`Provision gap = Provision - Actual Outcome`

and, where economically meaningful:

`Provision / Actual = Provision / Actual Outcome`

A large difference alone is not a manipulation verdict. The source asks the analyst to inspect multi-year patterns and the underlying reason.

## Q28 — Recurring revenue

No universal formula is source-locked for recurring-revenue share.

If the company directly discloses recurring/contracted revenue, the app may display the disclosed percentage with provenance.

If the analyst enters an estimate:

`Recurring revenue share = Analyst-supported recurring revenue / Total revenue`

it must be clearly marked `Analyst estimate with evidence`, never `Trecapital canonical`.

The analyst workspace distinguishes **Contractual recurring / Behavioral recurring / Repeat purchase / One-off / Mixed** because these have different durability characteristics.

## Q29 — Cyclicality

Phase 6B may display historical:

- Revenue growth
- EBIT / operating-profit growth
- Operating margin
- Gross margin where available
- Drawdowns from local revenue/EBIT peaks

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
- distinguish downside and upside observations where useful;
- a high DOL observation is evidence, not an automatic conclusion.

### Trecapital stress extension

A revenue stress such as -5%, -10% or -20% is an **app extension**, not a table copied from Shearn. It must be labelled clearly as a scenario tool and may only use analyst-confirmed cost-structure assumptions or transparent historical sensitivities.

## Q31 — Working capital / CCC

### Cash conversion cycle

`CCC = DIO + DSO - DPO`

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

A falling CCC or negative working capital is not automatically positive. Supplier-stretch or reversal of customer prepayments can create future cash demands.

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

The approved hierarchy is:

1. use company disclosure where available;
2. allow an analyst estimate only with explicit evidence and provenance;
3. when neither is available, allow **depreciation as a rough proxy only when the analyst explicitly selects that method and documents why it is reasonable and its limitations**;
4. otherwise show `Unknown`.

Never silently set `maintenance capex = total capex`. Never use depreciation as a hidden proxy or relabel a depreciation proxy as company-disclosed maintenance capex.

### Asset-age diagnostic

Shearn discusses net assets versus gross assets as a way to investigate whether older assets may require higher future replacement expenditure. Phase 6B may expose such a ratio when gross and net PP&E are available, but it is a diagnostic rather than a maintenance-capex formula.

#### Explicit PP&E source guardrail

For this diagnostic, **Net PP&E is accepted only from fields that explicitly mean net property, plant and equipment**:

- `net_ppe_bil`
- `ppe_net_bil`
- `property_plant_equipment_net_bil`

Gross PP&E is accepted only from:

- `gross_ppe_bil`
- `ppe_gross_bil`
- `property_plant_equipment_gross_bil`

`fixed_assets_bil`, total long-term assets, total non-current assets and other broad asset aggregates are **not** valid substitutes for PP&E. They can contain land-use rights, construction in progress, investment property, intangibles or other assets and therefore would distort the Net/Gross PP&E diagnostic.

If explicit Net PP&E or Gross PP&E is unavailable, the corresponding Q32 field and Net/Gross PP&E ratio must remain `N/A / Unknown`, with a coverage warning. The app must not fabricate a value from a broader balance-sheet category.

## Earnings & Cash-flow Distribution

The final Chapter-6 distribution width is analyst-owned and must be one of:

`Unknown / Narrow / Moderately Narrow / Medium / Moderately Wide / Wide`

There is no weighted score. Q27–Q32 may be summarized in a Predictability Matrix, but the engine may not calculate a 0–100 score or automatically change MOS/valuation assumptions.

## Formatting and provenance

For every computed Chapter-6 metric, production UI should retain:

- `source_field`
- `source_module`
- `source_period`
- `data_origin`
- formula / methodology note

Display format follows Trecapital project rules:

- billion VND: **0 decimal places**;
- percentages: **1 decimal place**;
- ratios: **1 decimal place**;
- negative values: **red heat intensity**;
- positive / positive-growth values: **emerald heat intensity**;
- larger absolute values use deeper heat intensity;
- read-only financial tables use `st.html()` with fixed layout and wrapped text;
- editable numeric research tables use explicit Streamlit `NumberColumn` formatting and expose an `st.html()` formatted preview.

## Missing-data rule

Missing inputs must produce `Unknown`, `N/A`, or a documented coarse proxy. Missing data must never be interpreted as evidence of quality. A proxy may only be used when its economic meaning is explicitly documented and approved for that metric; broad balance-sheet asset categories are not approved PP&E proxies.

## Phase 6B implementation lock — V31

The production bridge reads only the active Trecapital canonical overview/year/quarter bundle and appends TTM through the existing Module-1 path. It does not fetch a second financial dataset.

### Q27 implementation

- Annual and valid TTM rows may display `CFO/NI` and `CFO - NI`.
- Cumulative CFO/NI is **annual-only**; an overlapping TTM row is never added on top of annual history.
- Current-tax comparison is calculated only from a separately mapped current-tax-expense field. `tax_paid_bil` is **not** substituted for current-tax expense.
- Missing current-tax expense therefore remains `N/A`.

### Q28 implementation

Phase 6B exposes only explicit canonical fields such as `recurring_revenue_pct`, `contracted_revenue_pct` or `subscription_revenue_pct` if such fields truly exist in the canonical row. Otherwise the table remains empty/Unknown. No observed repeat-sales pattern is converted into a recurring-revenue percentage.

### Q29 implementation

Historical context includes revenue, EBIT, revenue growth, EBIT growth, gross/EBIT margins, and drawdown from the running historical peak. These are variability diagnostics only.

### Q30 implementation

`Historical DOL = %Δ EBIT / %Δ Revenue`

A row is retained but marked `Invalid` when revenue growth is undefined, absolute revenue change is below 1.0%, or current/prior EBIT is non-positive/sign-shifted. Invalid rows do not enter median, downside-median or upside-median DOL.

### Q31 implementation

`OWC = Operating Current Assets - Operating Current Liabilities`

`ΔOWC = OWC_t - OWC_(t-1)`

`Cash impact from ΔOWC = -ΔOWC`

Therefore positive cash impact means cash released and negative cash impact means cash absorbed. The bridge displays the canonical CFS working-capital change beside the balance-sheet-derived cash impact and exposes the reconciliation gap rather than silently forcing them to match.

DSO/DIO/DPO prefer average current/prior balances. Canonical day metrics are used only as a labelled fallback when average-balance inputs are insufficient. Banks, insurers, securities firms and other identified financial-service businesses are marked `N/A — not economically applicable` for CCC/OWC analysis rather than being forced through an industrial-company formula.

### Q32 implementation

- Total Capex is displayed as expenditure magnitude.
- `Capex/Revenue`, `Capex/D&A`, canonical/transparent FCF and Net/Gross PP&E are diagnostics.
- Net/Gross PP&E uses only explicit PP&E fields. `fixed_assets_bil` and broader fixed/non-current asset aggregates are never substituted; missing explicit PP&E remains `N/A / Unknown`.
- Chapter 6 **does not import Module-1 `maintenance_capex_bil`** because upstream Owner-Earnings logic may contain a generic proxy. That proxy is not allowed to become a Chapter-6 maintenance-capex fact.
- Chapter-6 maintenance capex remains: company disclosure → analyst estimate with evidence → explicitly selected D&A rough proxy → Unknown.

### Analyst boundary

Phase 6B never changes Q27–Q32 analyst assessments, final Earnings/Cash-flow Distribution Width, MOS, Research Gate or BUY/HOLD/SELL. Quantitative context is evidence only.

## Phase 6C evidence boundary

Phase 6C may retrieve and classify candidate evidence for Q27–Q32 and surface counter-evidence/research gaps. A/B/C is a source-quality/coverage grade, not a company-quality score. Module 2 Beneish/Sloan/Modified Jones/REM diagnostics are consumed read-only; Chapter 6 does not recompute them. Evidence candidates never auto-set analyst conclusions, Distribution Width, MOS, Research Gate, or BUY/HOLD/SELL.

Financial time-series tables extend to a valid canonical TTM when available. Annual-only methodologies show TTM as N/A rather than fabricate a value.

## Phase 6D final source closure — V33

Phase 6D adds five source-closure controls before Chapter 6 may be analyst-confirmed Complete:

1. **Income-tax footnote history:** explicit Current Tax vs Income-Tax Provision over 5–10 years where disclosed. Cash taxes paid are not a substitute. Difference % = |Current Tax − Tax Provision| / |Tax Provision| × 100. Missing disclosure remains N/A; annual-only footnotes do not receive fabricated TTM values.
2. **Unsustainable earnings register:** debt-retirement/extinguishment gains/losses, restructuring/write-offs and temporary cuts to advertising/R&D/maintenance are evidence items, not automatic manipulation findings.
3. **Operating leverage × debt bridge:** Phase-6B historical DOL is displayed beside the Chapter-5 shared Net Debt, Debt/EBITDA and interest-coverage context. No distress score is computed.
4. **Asset replacement register:** Net/Gross PP&E is a diagnostic only and must be interpreted with asset class, land/non-depreciable items, remaining life, replacement timing and depreciation-method comparability. Net PP&E must come from an explicit PP&E field; broad fixed/non-current assets are not accepted substitutes.
5. **Distribution → valuation bridge:** narrow distributions may support a point-estimate review; wide distributions prefer analyst-owned Bear/Base/Bull scenarios. No scenario assumption, probability, fair value, MOS or recommendation is auto-generated.

The final Completion Gate is a source/research-completion control only. It does not set Research Gate or BUY/HOLD/SELL.
