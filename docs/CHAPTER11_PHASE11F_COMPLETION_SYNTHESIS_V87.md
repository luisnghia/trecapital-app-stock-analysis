# Chapter 11 — Phase 11F / V87

## Scope

Source lock remains Michael Shearn — *The Investment Checklist*, Chapter 11, **Evaluating Mergers & Acquisitions**, Q58–Q59, printed pages 305–322.

- Q58 — How does management make M&A decisions?
- Q59 — Have past acquisitions been successful?
- Evidence dimensions remain source-locked at Q58 = 8 and Q59 = 7 (15 total).

## Research Completion Gate

V87 adds a deterministic research-completion gate. A question is research-ready only when:

1. Research Status is `Answered` or `N/A`.
2. Confidence is not `Unknown`.
3. Analyst Assessment is present and is not `Unknown`.
4. Every source-locked evidence dimension for that question has been explicitly resolved by the analyst (not `Unknown`).

The gate measures **completeness only**. It is not an M&A quality score and does not infer whether an acquisition was successful.

## Analyst M&A Synthesis

V87 adds an analyst-owned synthesis with neutral fields covering decision process, motivation/fit, synergy/integration, historical acquisitions, price/financing, strengths, concerns, unknowns, final synthesis, analyst note, and review status/timestamp.

AI/Data remain Research Assistant only. No synthesis field is filled automatically from evidence and no analyst conclusion is overwritten.

## Persistence and SSOT

`ma_synthesis` is the only new analyst extension preserved by the Chapter 11 store. Canonical financial/market data remains in the existing SSOT. V87 does not copy or recompute debt, EBITDA, EBIT, FCF, book value, cash, shares, EV/EBIT, EV/EBITDA, EV/FCF, leverage, debt coverage, dilution, or other upstream metrics.

## Explicit boundaries

V87 creates no weighted M&A score, no automatic acquisition-success conclusion, no automatic synergy forecast, no BUY/HOLD/SELL output, no intrinsic-value/MOS change, and no Investment Research Gate change.
