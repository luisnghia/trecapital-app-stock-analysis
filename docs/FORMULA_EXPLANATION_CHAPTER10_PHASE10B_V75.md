# Formula Explanation — Chapter 10 Phase 10B / V75

Phase 10B does **not** introduce a new financial engine. Michael Shearn's Chapter 10 names several calculations that later phases may need, but V75 only source-locks their meaning and records which canonical SSOT fields a data bridge should consume.

## Source-named calculations

- Acquisition intensity: acquisition cash spend as a percentage of cash flow from operations, reviewed over 5-10 years.
- Historical profitable growth: compare unit growth with gross margin and operating margin over 3-5 years; compare operating-income growth and operating profit per unit/transaction.
- R&D commitment: R&D expense divided by sales/revenue over time.
- R&D effectiveness: sales from recently introduced/new products divided by total sales, when the company discloses a comparable measure.
- Dividend payout ratio: dividends paid divided by earnings.
- Cash-conversion cycle: **CCC = DIO + DSO - DPO**.

## V75 implementation boundary

V75 does not calculate any of the formulas above. It does not calculate CCC, dividend payout, P/E, R&D ratios, margin trends, acquisition intensity, operating profit per unit, CAGR, sustainable growth, intrinsic value, or MOS.

Instead, every source dimension can expose an `ssot_dependency` string. A later Chapter 10 data-bridge phase must map those dependency names to the canonical financial and operating data already maintained by Trecapital. Missing canonical fields must remain unavailable/Unknown rather than being silently rebuilt from an alternative source inside Chapter 10.

## No scoring formula

The 34 source dimensions are not weighted. There is no arithmetic that turns dimension completion, evidence direction, or analyst status into a growth score. Research completeness and growth quality remain distinct concepts.

## Valuation boundary

Chapter 10 discusses the risk of paying a high multiple for expected growth. V75 preserves that subject as a research dimension (`q56_price_expectation_risk`) but does not calculate a target multiple, target price, intrinsic value, margin of safety, or investment signal.

## Analyst boundary

Quantitative evidence may later be generated deterministically from canonical data, but qualitative interpretation remains analyst-owned. AI may organize and summarize evidence only.