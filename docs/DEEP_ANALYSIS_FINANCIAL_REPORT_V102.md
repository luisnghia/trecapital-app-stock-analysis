# Deep Company Analysis V102 — 10Y + TTM Financial Evidence

## Purpose
V102 extends the V101 evidence-rich Investment Checklist DOCX with quantitative financial evidence while preserving the existing architecture boundaries. It is a read-only presentation layer over the Trecapital Data Layer / canonical financial dataframe.

## Coverage
The report renders at most 10 annual periods plus one latest TTM overlay for:

- Revenue, Gross Profit, GPM
- EBIT, EBITDA
- Consolidated LNST, NPAT-MI, Net Margin
- CFO, Capex, FCF, CFO/LNST, FCF/LNST
- Cash, Debt, Net Cash, Equity, Debt/Equity
- ROIC, ROCE
- Accounts Receivable, Inventory, Accounts Payable, CCC
- V100 growth / cyclical-normalization context

Charts are quantitative and include visible values where data exist. Missing values remain blank/unknown; V102 does not synthesize missing source facts.

## Display-only fallback formulas
Canonical explicit fields are always preferred. When a canonical ratio/derived field is absent, V102 may derive the following solely for presentation, with `source_field` recording the exact input aliases used:

- `GPM = Gross Profit / Revenue × 100`
- `Net Margin = LNST canonical / Revenue × 100`
- `FCF = CFO − abs(Capex)`
- `CFO/LNST = CFO / LNST canonical × 100`
- `FCF/LNST = FCF / LNST canonical × 100`
- `Net Cash = Cash − Debt`
- `Debt/Equity = Debt / Equity`

These derived values do not become a second financial SSOT and do not write back to the canonical dataframe.

## Period semantics
TTM/T12M is a current overlay. It does not replace an annual period and is not included in annual cycle baselines. V100 continues to own median, trimmed mean, P25/P75, peak/trough and comparability-break context.

## Provenance contract
Every available metric-period observation can be traced through:

- `source_field`
- `source_module`
- `source_period`
- `data_origin`

Derived presentation values expose compound `source_field` expressions rather than disguising them as source facts.

## Architecture boundaries
- Trecapital Data Layer remains the financial SSOT.
- V101 remains the checklist/report owner for exact Q01–Q59 wording and answer rendering; V102 composes V101 by reference.
- Michael Shearn source-locked question wording is not edited in V102.
- Q33–Q52 still remain `Unknown` when evidence is absent.
- Module 2 remains the only owner of valuation / intrinsic value / MOS.
- AI remains `Research Assistant`; the analyst owns interpretation and conclusions.
- No weighted management/growth/checklist score is introduced.
- No BUY/HOLD/SELL recommendation is introduced.
- No automatic intrinsic-value/MOS or Investment Research Gate change is introduced.

## QA / acceptance
The dedicated V102 workflow compiles the implementation, runs deterministic tests and acceptance QA, audits SSOT/investment boundaries, runs the full `modules/deep_company_analysis/test_*.py` regression, verifies Streamlit health, and builds an offline ZIP + GitHub artifact.
