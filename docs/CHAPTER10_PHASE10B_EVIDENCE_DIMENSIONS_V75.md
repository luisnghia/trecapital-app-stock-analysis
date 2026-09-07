# Deep Company Analysis — Chapter 10 Phase 10B / V75

## Scope

Phase 10B source-locks the research dimensions explicitly supported by Michael Shearn, *The Investment Checklist*, Chapter 10, **Evaluating Growth Opportunities**, printed pages 281-303. The Chapter 10 question boundary remains exactly **Q53-Q57**; Q52 and Q58 are excluded.

This phase is deliberately schema-only. It does not add web research, Streamlit UI, a database/store, a financial data bridge, valuation logic, portfolio actions, a growth score, or an automatic investment conclusion.

## Source coverage

| Question | Printed pages | Locked dimensions |
|---|---:|---:|
| Q53 | 281-282 | 4 |
| Q54 | 282-283 | 4 |
| Q55 | 283-284 | 4 |
| Q56 | 284-296 | 15 |
| Q57 | 296-303 | 7 |
| **Total** | **281-303** | **34** |

### Q53 — Growth route

The schema captures acquisition spend relative to CFO over 5-10 years, the organic/selective/serial-acquirer continuum, acquisition risks (overpayment, leverage, integration), and whether reported growth is material relative to the existing revenue base.

### Q54 — Motivation to grow

The schema captures pressure to grow top-line or support the stock price, evidence that core growth is slowing, expansion outside the core business / area of expertise, and management distraction or later reversal of non-core growth initiatives.

### Q55 — Historical profitable growth

The schema captures unit growth versus gross margin and operating margin over 3-5 years, operating-profit-per-unit economics, and whether the historical profitability pattern appears persistent. It does not decide whether the pattern is good or bad for the analyst.

### Q56 — Future growth prospects

The schema captures management-disclosed opportunity, runway duration, replicability/saturation, operating drivers versus EPS, secular versus cyclical demand, commodity price versus unit growth, measurable secular evidence, R&D commitment, R&D output success, transformational-product customer validation, market-size/share integrity, effective-market distortions, slowing-growth signals, valuation-expectation risk, and continuity of the management team responsible for historical growth.

### Q57 — Growth discipline

The schema captures disciplined pace, internal versus external funding, CCC evidence, payback/profitability timing of growth investments, human-capital capacity, corporate infrastructure capacity, and location/return discipline.

## Analyst ownership

All 34 dimensions default to `Unknown`. Status options are only `Unknown`, `Evidence found`, `Not found`, and `N/A`. No direction or status is converted into a score, forecast, BUY/HOLD/SELL signal, MOS change, or Research Gate outcome.

## Financial SSOT boundary

The book names several financial calculations. Phase 10B stores only dependency labels so a later data bridge can reuse canonical financial data. It does **not** implement duplicate calculations for CFO, acquisition spend, margins, EPS, R&D/sales, dividend payout, P/E, CCC, capex, or return on capital.

## Next phase

**Phase 10C / V76 — Canonical Data Bridge & deterministic evidence extraction for source-supported quantitative dimensions**, with strict reuse of existing financial SSOT and no automatic qualitative conclusion.