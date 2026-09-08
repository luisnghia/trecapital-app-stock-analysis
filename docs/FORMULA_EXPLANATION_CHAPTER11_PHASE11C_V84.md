# Formula / SSOT Explanation — Chapter 11 Phase 11C / V84

Phase 11C intentionally introduces **no new financial formula**.

Chapter 11 mentions valuation and financing concepts such as EV/EBIT, EV/EBITDA, EV/FCF, premium to book value, debt burden, debt coverage and dilution. V84 does not calculate any of them. It only reads canonical facts that already exist elsewhere in the application.

Illustrative formulas are listed here solely to make the boundary explicit:

- EV/EBIT = Enterprise Value / EBIT
- EV/EBITDA = Enterprise Value / EBITDA
- EV/FCF = Enterprise Value / Free Cash Flow
- Book-value premium = Acquisition consideration / Book value - 1
- Equity dilution depends on shares issued relative to the pre-deal share base

**Chapter 11 does not calculate these formulas.** If a ratio or derived metric is required later, it must come from the existing canonical SSOT or another explicitly approved upstream engine. Chapter 11 may surface canonical components and provenance, but it must not reconstruct the metric locally.

Likewise, V84 does not calculate acquisition return, synergy value, post-deal ROIC, leverage, debt-service coverage, or earnings accretion/dilution. Missing values remain Unknown / research gaps.

This keeps the financial SSOT singular and preserves Shearn's framing: Q58-Q59 are research questions about management's M&A decision process and the historical success of acquisitions, not an automated valuation or scoring engine.
