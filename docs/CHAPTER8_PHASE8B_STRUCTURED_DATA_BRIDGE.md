# Chapter 8 — Phase 8B Structured Data Bridge

Status: IMPLEMENTED in V43.

## Objective

Phase 8B connects the Chapter 8 source-lock (Q39–Q47) to existing Trecapital data without creating parallel masters or a second financial source of truth.

Two existing masters are authoritative:

1. **Manager identity/background:** Chapter 7 `management_profiles` (`Manager ID`, name, role, analyst classification/confidence).
2. **Financial data:** Trecapital canonical normalized financial rows / Module 1.

Chapter 8 consumes those records. It does not create replacement manager IDs and does not use web/disclosure numbers as an independent financial statement source.

## What Phase 8B implements

### Chapter 7 manager reference

`build_manager_reference()` reads the Chapter 7 manager master and exposes only the fields Chapter 8 needs for evidence linkage. If Chapter 7 has no manager master, Chapter 8 remains empty and emits a research warning; it does not manufacture a manager.

### Q41 — Guidance History

`normalize_guidance_rows()` accepts structured official-disclosure guidance rows and normalizes:

- issued date;
- metric;
- horizon;
- guidance low/high/point;
- event: issued/revised/withdrawn/no guidance/unknown;
- actual;
- arithmetic outcome: Beat / Meet / Miss / N/A / Unknown;
- source.

Beat/Meet/Miss is only an arithmetic comparison to the disclosed range/point. It does **not** infer sandbagging, manipulation, conservatism, competence or management quality.

### Q45 — Cost Discipline Context

`build_q45_cost_context()` uses canonical financial rows to expose:

- Revenue;
- COGS (derived only where canonical revenue and gross profit are both present);
- COGS/revenue;
- explicit SG&A, or explicit selling + admin expense where available;
- EBIT and EBIT margin;
- CFO and FCF;
- canonical provenance.

This table is context only. Lower cost is not automatically good. The analyst must determine whether a cost action removes waste or damages customer service, employees or core capability.

### Q46 — Capital Allocation History

The bridge preserves the **five uses of excess FCF in Shearn Chapter 8**:

1. Reinvest in the business / new projects — canonical CAPEX is shown only as a reinvestment proxy.
2. Hold cash — ending cash is shown as a balance-sheet stock, not a flow.
3. Pay dividends — only explicit canonical dividend cash fields.
4. Buy back stock — only explicit canonical repurchase cash fields.
5. Make acquisitions — only explicit canonical acquisition cash fields.

Debt paydown is not inserted into the source-locked Shearn five-bucket list. It can be added later only as a clearly labelled Trecapital extension outside the five source-locked buckets.

The five columns must never be blindly summed: ending cash is a stock and CAPEX is only a partial reinvestment proxy.

### Q47 — Buyback Context

`build_q47_buyback_context()` separates:

- explicit buyback cash;
- explicit shares repurchased;
- shares outstanding / average shares;
- share-count change;
- explicit-buyback-available flag.

A decline in share count **is not proof of a buyback**. It may reflect many corporate actions or data definitions. If an explicit repurchase field is absent, buyback remains unconfirmed.

## Data provenance

Financial context rows carry:

- `Source = Trecapital canonical financial data / Module 1`
- `Data Origin = Canonical Trecapital normalized statements`

Manager references carry:

- `Source = Chapter 7 manager master`

Structured guidance is disclosure evidence, not a replacement financial statement source.

## Missing-data policy

Missing fields remain `None`/Unknown. The bridge does not:

- convert share-count decline into a buyback;
- invent acquisitions or dividends from cash-flow residuals;
- infer SG&A when selling/admin components are unavailable;
- turn CAPEX into a complete measure of reinvestment;
- infer management competence from financial ratios;
- fabricate TTM for qualitative/event evidence.

## Analyst boundary

Phase 8B does not write:

- analyst assessment;
- management score;
- Q39–Q47 final qualitative answer;
- BUY/HOLD/SELL;
- MOS;
- Research Gate.

Its role is structured evidence/context only.

## Deferred

- Phase 8C — automated evidence/research assistant for Q39–Q47, with source hierarchy, counter-evidence and research-gap handling.
- Phase 8D — source closure, review-on-change and Chapter 8 completion gate.
- Full Chapter 8 analyst UI integration can be finalized after the research layer is stable.
