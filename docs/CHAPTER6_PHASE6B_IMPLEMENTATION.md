# Chapter 6 — Phase 6B Quantitative Bridge V31

Status: **IMPLEMENTED — approved specification**.

## Scope

Phase 6B connects Q27–Q32 to the existing Trecapital canonical Data Layer. It does not create a new data-fetching pipeline and does not write quantitative evidence back into analyst-owned conclusions automatically.

## Delivered

- Q27: CFO/NI, CFO−NI, annual cumulative cash conversion, current-tax vs provision only when separately disclosed.
- Q28: explicit recurring/contracted/subscription revenue share only; no inference.
- Q29: 10-year + valid TTM revenue/EBIT/margins/peak-drawdown context.
- Q30: period-by-period historical DOL with visible invalid rows plus median/downside/upside summaries.
- Q31: AR/Inventory/AP, DSO/DIO/DPO/CCC, OWC, ΔOWC, cash absorbed/released and CFS reconciliation; financial-sector N/A guardrail.
- Q32: Total Capex, Capex/Revenue, Capex/D&A, CFO/FCF, FCF margin and Net/Gross PP&E when available.
- Provenance audit table: source fields, source module, source period, data origin and formula boundary.

## Critical guardrails

1. `tax_paid_bil` is not current-tax expense.
2. TTM is not double-counted in cumulative annual CFO/NI.
3. Invalid DOL observations stay visible and do not enter summary medians.
4. `Cash impact from ΔOWC = -ΔOWC` is displayed explicitly; reconciliation differences are not hidden.
5. CCC/OWC is N/A for identified banks/insurers/securities/financial-services models.
6. Module-1 `maintenance_capex_bil` is not imported into Chapter 6 because a generic Owner-Earnings proxy must not be relabelled as maintenance capex evidence.
7. No 0–100 score, no automatic Distribution Width, no automatic MOS change, no BUY/HOLD/SELL.

## Display contract

The V30 global format lock remains active: VND amounts are shown in tỷ đồng with 0 decimals; percentages and ratios use 1 decimal; read-only tables use the shared `st.html()` renderer with fixed layout/wrap; signed performance/cash-flow heat is contextual rather than a quality verdict.
