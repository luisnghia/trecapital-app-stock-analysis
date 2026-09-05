# Chapter 6 — APPROVED Phase 6A Source-Locked Analytical Workspace

Status: **APPROVED by analyst/user on 2026-09-05**.

Primary source: Michael Shearn, *The Investment Checklist*, Chapter 6 — **Evaluating the Distribution of Earnings (Cash Flows)**.

## Core objective

Chapter 6 evaluates the **width / predictability of the future earnings and cash-flow distribution**, not a single-point forecast and not a mechanical quality score. The analyst asks:

> How predictable are this business's future earnings/cash flows, and what can make realized results deviate materially from expectations?

Questions remain exactly Q27–Q32:

- Q27 — Are the accounting standards that management uses conservative or liberal?
- Q28 — Does the business generate revenues that are recurring or from one-off transactions?
- Q29 — To what degree is the business cyclical, countercyclical, or recession-resistant?
- Q30 — To what degree does operating leverage impact the earnings of the business?
- Q31 — How does working capital impact the cash flows of the business?
- Q32 — Does the business have high or low capital-expenditure requirements?

## Q27 — Accounting quality / true operating earnings

The approved workspace keeps the following analytical areas separate:

1. Tax vs Book Earnings
2. CFO vs Net Income
3. Revenue recognition
4. Expense vs capitalization
5. Discretionary-cost behavior
6. Depreciation / estimate assumptions
7. Restructuring / one-offs
8. Reserve quality

Tables 6.1–6.2 are implemented as two complementary tools:

- **Accounting Quality Investigation Register** for policy/estimate evidence and counter-evidence.
- **Reserve / Provision Roll-forward** with Beginning Reserve, Provision, Write-offs/Usage, Adjustments, Ending Reserve, Actual Outcome and Provision/Actual.

The seven Shearn reserve areas remain seeded as research prompts: bad debts, sales returns, inventory obsolescence, warranties, product liability, litigation and environmental contingencies. They are not allegations. Deleted analyst rows are not silently restored after save/load.

Chapter 6 does **not** recompute Beneish M-Score, Dechow/Jones or REM. Phase 6C may receive read-only manipulation evidence from the existing module, while the Conservative/Mixed/Liberal conclusion remains analyst-owned.

## Q28 — Revenue durability

Revenue is not reduced to a binary recurring/one-off flag. The approved Revenue Durability Map distinguishes:

- Contractual recurring
- Behavioral recurring
- Repeat purchase
- One-off
- Mixed

It stores revenue share, contractual status, duration, renewal, churn/retention evidence, switching cost, replacement requirement, revenue at risk, customer dependency, evidence/counter-evidence and analyst assessment.

No recurring-revenue percentage is fabricated. Company disclosure is preferred; analyst estimates must be explicitly labelled and evidence-backed.

## Q29 — Cycle Exposure Map

The analyst must examine purchase deferrability, recurring-revenue protection, customer budget importance, customer economic-cycle exposure, supply/demand context, commodity exposure, historical downturn evidence and peak/trough behavior.

Sector cyclicality or one apparently resilient recession does not automatically classify a company as cyclical or recession-resistant.

## Q30 — Operating Leverage

Phase 6A stores the economic cost structure as Fixed / Variable / Semi-variable with driver, adjustment lag, capacity/utilization link, management flexibility, downturn behavior, evidence and counter-evidence.

Historical DOL belongs to Phase 6B and will use Trecapital canonical data. No single abnormal year may automatically set the analyst conclusion.

## Q31 — Working Capital

Phase 6A stores the operating mechanism and whether cash absorption/release is sustainable or temporary. The approved design explicitly rejects the rules:

- `lower CCC = automatically better`
- `negative working capital = automatically better`

Phase 6B will compute 5–10Y DSO/DIO/DPO/CCC and operating-working-capital cash impact from canonical fields only.

## Q32 — Capital expenditure requirements

Maintenance-capex evidence follows this hierarchy:

1. **Company-disclosed maintenance capex** — highest priority.
2. **Analyst estimate with explicit evidence/provenance**.
3. **Depreciation rough proxy — clearly labelled** when appropriate under Shearn's framework and accompanied by a written rationale/limitations.
4. Otherwise **Unknown**.

Total capex must never be silently relabelled as maintenance capex. A depreciation proxy is not canonical company disclosure and must remain visibly marked as a rough proxy.

## Earnings & Cash-flow Predictability Matrix

Q27–Q32 feed one analyst-owned matrix with six drivers:

- Accounting quality
- Revenue recurrence
- Cyclicality
- Operating leverage
- Working capital
- Capital intensity

Final distribution choices are:

- Narrow
- Moderately Narrow
- Medium
- Moderately Wide
- Wide
- Unknown

There is **no weighted score / 0–100 score**. The app also does not automatically change MOS or valuation assumptions from this classification.

## Data / AI / Analyst boundary

- **Data Engine:** canonical facts and transparent derived metrics only.
- **AI Research Assistant:** find disclosures, evidence, counter-evidence, anomalies and research gaps.
- **AI must not:** set Conservative/Liberal accounting, recurring quality, cyclicality class, operating-leverage risk, maintenance capex, distribution width, Research Gate or BUY/HOLD/SELL.
- **Analyst:** owns all Q27–Q32 conclusions and final distribution width.

Missing evidence remains `Unknown`; it is never interpreted as positive evidence.

## Persistence

Database: `data_cache/deep_company_analysis_chapter6.db`

Persistent child tables include:

- `chapter6_accounting_quality`
- `chapter6_reserve_rollforward`
- `chapter6_revenue_streams`
- `chapter6_cycle_drivers`
- `chapter6_cost_structure`
- `chapter6_working_capital`
- `chapter6_capex_register`
- `chapter6_distribution_matrix`
- `chapter6_evidence`
- `chapter6_research_gaps`
- `chapter6_current`
- `chapter6_snapshots`

Financial facts remain owned by the canonical Trecapital Data Layer.

## Display-format lock

Chapter 6 follows the project-wide display rules:

- financial amounts: **tỷ đồng, 0 decimals**;
- percentages: **1 decimal**;
- ratios: **1 decimal**;
- negative numeric values: **red heat intensity**;
- positive numeric values / positive growth: **emerald heat intensity**;
- larger absolute values use deeper heat intensity;
- read-only financial tables use `st.html()` with `table-layout: fixed`, `white-space: normal`, `overflow-wrap: anywhere`;
- editable research tables use `st.data_editor` with explicit numeric column formats and expose an `st.html()` formatted preview for tables containing financial numbers.

## Phase 6A acceptance rules

- Q27–Q32 exist and persist.
- Tables 6.1–6.2 logic includes a reserve roll-forward.
- Seven Shearn reserve areas seed only a new record and deletions persist.
- Q28 explicitly distinguishes Contractual recurring / Behavioral recurring / Repeat purchase / One-off.
- Q29 captures cycle and supply/demand evidence without auto-classification.
- Q30 cost structure is separate from future quantitative DOL.
- Q31 does not treat low/negative CCC as automatically positive.
- Q32 supports disclosed → analyst estimate → clearly-labelled depreciation rough proxy → Unknown hierarchy.
- Earnings Distribution Matrix contains Q27–Q32 and has no weighted score.
- Numeric display-format rules are tested.
- Save/load/snapshot persistence works.
- No automatic Research Gate or BUY/HOLD/SELL.

## Next phase — only after analyst review

**Phase 6B — Quantitative Bridge** from Trecapital canonical data: CFO/NI history, historical revenue/EBIT/margin behavior, DOL, DSO/DIO/DPO/CCC, operating-WC cash impact, total capex, capex/revenue, capex/D&A, FCF, PP&E age diagnostics and full provenance.
