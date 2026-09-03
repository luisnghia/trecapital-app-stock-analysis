# Trecapital — Deep Company Analysis Chapter 4 — Formula & Data Notes

## Scope

This document explains the quantitative formulas used by **Chapter 4 Phase 4B**. These are Trecapital implementation aids for Michael Shearn's qualitative framework. They are not new Shearn questions and they do not create a Moat Score, Pricing Power Score, Industry Score, Competition Score, or Supplier Score.

**Core rule:** canonical Trecapital financial data is the source of truth. Chapter 4 consumes normalized metrics and does not create a separate financial-data parser/source.

---

## 1. Gross Margin

When canonical `gross_margin_pct` is available, Chapter 4 consumes it directly.

Fallback only when normalized revenue and gross profit are present:

`Gross Margin % = Gross Profit / Revenue × 100`

Use: Q16 historical operating context and Q19 peer comparison.

Guardrail: a rising Gross Margin **does not prove a price increase or Pricing Power**. Mix, raw-material cost, utilization, FX, accounting classification, or temporary shortages may also move margin.

---

## 2. EBIT / Core Operating Margin

Priority: canonical `core_operating_margin_pct`; otherwise normalized operating margin if supplied.

Fallback:

`EBIT Margin % = Core Operating Profit / Revenue × 100`

The normalized core operating profit in Module 1 excludes financial-income distortion where data permits.

Use: Q16 historical context and Q19 peer economics.

Guardrail: EBIT Margin is evidence, not an automatic moat/pricing conclusion.

---

## 3. Free Cash Flow Margin

`FCF Margin % = Free Cash Flow / Revenue × 100`

FCF itself remains the canonical Module 1 definition. Chapter 4 does not rebuild FCF.

Use: Table 4.2-style peer context only.

---

## 4. ROIC used in Chapter 4

Chapter 4 consumes canonical `roic_pct`, with normalized fallback priority already implemented in Module 1 (`roic_standard_pct`, then source/FireAnt where applicable).

Canonical standard ROIC logic in Module 1:

`ROIC = NOPAT / Average Capital Employed × 100`

where:

`NOPAT = Core Operating Profit × (1 - effective tax rate)`

and average capital employed is calculated from normalized balance-sheet values.

Chapter 4 does **not** recalculate ROIC independently.

Use:
- Q17 industry ROIC distribution
- Q19 peer benchmark

Guardrails:
- high target-company ROIC does not imply a good industry;
- one exceptional peer does not represent industry economics;
- analyst decides `Good / Mixed / Bad / Unknown`.

---

## 5. Historical ROIC medians

Historical peer statistics use annual rows only; TTM is excluded from 5-year/10-year medians.

`ROIC 5Y Median = median(last up to 5 annual ROIC observations)`

`ROIC 10Y Median = median(last up to 10 annual ROIC observations)`

`ROIC Min / Max = min / max(last up to 10 annual ROIC observations)`

Latest operating snapshot may use the canonical TTM row when available.

---

## 6. Industry ROIC distribution

For the analyst-selected peer set with available canonical ROIC:

- `Median ROIC = median(peer latest ROIC)`
- `P25 = 25th percentile(peer latest ROIC)`
- `P75 = 75th percentile(peer latest ROIC)`
- `ROIC Spread = Max ROIC - Min ROIC`
- `% Positive ROIC = peers with ROIC > 0 / peers with valid ROIC × 100`

These are descriptive statistics only. The bridge intentionally emits no `industry_quality` conclusion.

Small peer sets are explicitly warned in the UI.

---

## 7. Receivables Turnover and DSO

Canonical Module 1 logic:

`Receivables Turnover = Revenue / Average Accounts Receivable`

`DSO Days = 365 / Receivables Turnover`

If accounts receivable is missing or economically invalid, the metric remains unavailable rather than being fabricated.

---

## 8. Inventory Turnover and DIO

Canonical Module 1 logic:

`Inventory Turnover = COGS / Average Inventory`

`DIO Days = 365 / Inventory Turnover`

If direct COGS is absent but revenue and gross profit are present, Module 1 may normalize:

`COGS ≈ Revenue - Gross Profit`

Chapter 4 consumes the already-normalized metric.

Guardrail: higher inventory turnover alone does not prove supplier quality or a collaborative supplier relationship.

---

## 9. Payables Turnover and DPO

Canonical Module 1 logic:

`Payables Turnover = COGS / Average Accounts Payable`

`DPO Days = 365 / Payables Turnover`

Guardrail: an increase in DPO **must not** be interpreted automatically as improved supplier economics. It can also reflect supplier pressure, weaker payment behavior, mix, or contract changes.

---

## 10. Cash Conversion Cycle

Canonical Module 1 logic:

`CCC Days = DSO Days + DIO Days - DPO Days`

Use:
- Q17 industry economics context
- Q19 Table 4.2 peer benchmark
- Q20 supply-chain operating context

Guardrail: CCC is an operating metric, not a Supplier Relationship rating.

---

## 11. Pricing Power quantitative bridge

There is deliberately **no formula** that converts margins into Pricing Power.

Phase 4B shows historical:
- Revenue growth
- Gross Margin
- EBIT Margin
- FCF Margin

An actual Pricing Event requires explicit evidence of price/volume/customer behavior before analyst classification as:
- True Pricing Power
- Cost Pass-through
- Commodity / Shortage Pricing
- Promotional / Mix Effect
- Unknown

Therefore:

`Margin increase ≠ inferred price increase ≠ Pricing Power conclusion`

---

## 12. Table 4.2 peer benchmark

For each available metric, Phase 4B presents:
- Target
- Peer Median
- Peer Min
- Peer Max

`Peer Min/Max` are descriptive and are **not automatically labelled Best or Ideal**. The analyst selects the Ideal Business source/characteristic after considering economics and operating context.

---

## 13. Provenance

Every Phase 4B company snapshot carries:
- ticker
- company name
- data period
- source label
- source module
- data origin

Default source module:

`Trecapital canonical financial data / Module 1`

Default data origin:

`Canonical Trecapital normalized statements`

This prevents Chapter 4 from becoming a parallel financial-data system.
