# Chapter 6 — Phase 6A Source Lock

Status: **IMPLEMENTED for analyst review** (2026-09-05). This document is not marked APPROVED until the analyst/user reviews the Phase 6A behavior.

Primary source: Michael Shearn, *The Investment Checklist*, Chapter 6 — **Evaluating the Distribution of Earnings (Cash Flows)**, pp. 137–172 in the original book pagination.

## Source objective

Chapter 6 asks the analyst to understand the **range / distribution of future earnings and cash flows**, rather than pretending the future can be forecast as a single precise number. A wider distribution makes a business harder to value. Recurring revenue, lower cyclicality, lower operating leverage, sustainable working-capital economics and lower maintenance-capex burden generally make future cash flows easier to understand, but Chapter 6 does not provide a mechanical investment score.

Questions:

- Q27 — Are the accounting standards that management uses conservative or liberal?
- Q28 — Does the business generate revenues that are recurring or from one-off transactions?
- Q29 — To what degree is the business cyclical, countercyclical, or recession-resistant?
- Q30 — To what degree does operating leverage impact the earnings of the business?
- Q31 — How does working capital impact the cash flows of the business?
- Q32 — Does the business have high or low capital-expenditure requirements?

## Q27 — Accounting quality / true operating earnings

Shearn's stated purpose is to get closer to the business's **true operating earnings**. Phase 6A therefore keeps separate investigation fields for:

- income-tax / book-income differences;
- CFO versus Net Income;
- timing of revenue recognition;
- expensing versus capitalization;
- temporary cuts in discretionary costs such as advertising, R&D and maintenance;
- depreciation assumptions / useful lives;
- restructuring charges;
- reserve accounts and the match between provisions and actual outcomes.

### Tables 6.1–6.2 conversion

Tables 6.1 and 6.2 compare **allowance/provision for doubtful accounts** with **actual charge-offs**. The app therefore includes an Accounting / Reserve Quality Register.

Shearn explicitly lists reserves for:

1. Bad debts
2. Sales returns
3. Inventory obsolescence
4. Warranties
5. Product liability
6. Litigation
7. Environmental contingencies

These rows are seeded only when a Chapter-6 record is first created. They are research prompts, not allegations. After first save the analyst owns the register and may delete or add rows; the app must not silently restore deleted rows.

The Sysco / Krispy Kreme examples teach the comparison method, not a universal numeric fraud rule. Phase 6A therefore does **not** auto-label manipulation.

## Q28 — Recurring versus one-off revenue

Shearn says businesses with recurring revenue are easier to forecast because the next period begins with a base greater than zero instead of having to replace all prior sales.

Source examples include:

- subscription businesses;
- razor / razorblade models;
- franchisors earning license fees;
- service businesses with recurring contracts.

Phase 6A stores a Revenue Stream Map. Revenue share, retention, contract duration and at-risk revenue remain `Unknown` unless the company discloses them or the analyst explicitly enters an estimate with evidence.

## Q29 — Cyclicality / recession resistance

The source directs the analyst to consider:

- whether customers can defer purchases, and for how long;
- recurring-revenue protection;
- the share of the customer's budget spent on the product/service;
- how exposed the customer base itself is to the economic cycle;
- historical downturn evidence;
- supply/demand imbalances that may have made a past recession look less severe than it really was.

A prior period of resilience does not justify an automatic `recession-resistant` label. Phase 6A therefore requires a Cycle Driver / Downturn Evidence Map.

## Q30 — Operating leverage

Shearn defines operating leverage as the impact of sales changes on earnings. Businesses with large fixed costs can turn relatively small sales changes into much larger earnings changes and are therefore harder to forecast.

The book's Tables 6.3–6.5 combine:

- historical revenue / operating-income behavior; and
- economic cost structure: fixed, variable and semi-variable costs.

Phase 6A implements only the analyst cost-structure map. Historical DOL and any stress scenarios are reserved for Phase 6B, where they must use canonical Trecapital data and remain research aids rather than conclusions.

## Q31 — Working capital / cash conversion cycle

Shearn instructs the analyst to calculate the **cash conversion cycle (CCC) for at least five years** and explain changes in its components:

- DIO — days inventory outstanding;
- DSO — days sales outstanding;
- DPO — days payable outstanding.

Table 6.6 demonstrates that very different business models can have negative or very long CCCs. The source emphasizes that the analyst must determine whether changes are **sustainable or temporary**. For example, cash released by stretching supplier payments may later reverse and should be normalized if it is not sustainable.

Negative working capital can be favorable when suppliers/customers fund the operating model, but it can also create liquidity risk if a reversal must be funded and the company lacks cash. Therefore Phase 6A never implements `lower CCC = better` as a rule.

## Q32 — Capital-expenditure requirements

Shearn links high capital requirements to lower distributable cash flow because the business must recycle cash into existing assets merely to maintain operations.

The source distinguishes:

- capital-intensive businesses;
- capital-light businesses;
- **maintenance capital expenditures** required to keep the business in steady state;
- growth capex;
- regulatory / non-discretionary required investment;
- deferred-maintenance and asset-age replacement risk.

Shearn notes that many capital-intensive examples have capex/sales above roughly 0.20, but this is an observation about the examples in the book, not a universal classification rule. The app must not use 20% as a hard automatic cutoff.

Most importantly: **maintenance capex must not be invented.** If it is not separately disclosed and cannot be supported by evidence, the field remains `Unknown`. Phase 6B may present total capex, capex/sales, capex/D&A and asset-age diagnostics, but it may not silently equate total capex with maintenance capex.

## Phase 6A persistence

Database: `data_cache/deep_company_analysis_chapter6.db`

Tables:

- `chapter6_current`
- `chapter6_accounting_quality`
- `chapter6_revenue_streams`
- `chapter6_cycle_drivers`
- `chapter6_cost_structure`
- `chapter6_working_capital`
- `chapter6_capex_register`
- `chapter6_evidence`
- `chapter6_research_gaps`
- `chapter6_snapshots`

SQLite stores analyst workspace, evidence and snapshots. Financial facts remain owned by the canonical Trecapital Data Layer.

## Immutable analyst boundary

AI/Data must not automatically set:

- conservative/liberal accounting conclusion;
- fraud/manipulation conclusion;
- recurring-revenue classification or share;
- cyclical/countercyclical/recession-resistant conclusion;
- operating-leverage risk conclusion;
- whether a CCC improvement is sustainable;
- maintenance capex;
- capital-intensity conclusion;
- width of the earnings distribution;
- Research Gate;
- BUY/HOLD/SELL.

Missing evidence is `Unknown`, never positive evidence.

## Phase 6A acceptance rules

- Q27–Q32 all exist and persist.
- Seven Shearn reserve areas are seeded for a brand-new Q27 record.
- Analyst can delete default reserve rows and they do not silently reappear after save/load.
- Evidence and counter-evidence can be stored for every research area.
- Q28 recurring-revenue share is not fabricated.
- Q29 requires explicit cycle/downturn evidence before a strong analyst conclusion is well supported.
- Q30 keeps cost structure distinct from Phase-6B quantitative DOL.
- Q31 does not treat low/negative CCC as automatically good.
- Q32 does not infer maintenance capex from total capex without evidence.
- Save/load/snapshot persistence works.
- No automatic BUY/HOLD/SELL or Research Gate is created.

## Next phase

**Phase 6B — Quantitative Bridge** from canonical Trecapital data:

- Q27: CFO vs NI history and selected accounting-quality diagnostics where canonical fields exist;
- Q29: revenue / EBIT / margin behavior through available history, without claiming macro causality;
- Q30: historical DOL diagnostics and clearly-labelled Trecapital stress extension;
- Q31: 5–10Y DIO / DSO / DPO / CCC, ΔOperating WC and cash absorbed/released;
- Q32: total capex, capex/sales, capex/D&A, FCF and asset-age diagnostics;
- dedicated provenance (`source_field`, `source_period`, `data_origin`) for every computed metric.
