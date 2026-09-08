# Formula Explanation — Chapter 11 Phase 11F / V87

## Research-ready formula

For each question Q58 or Q59:

`Research Ready = Status in {Answered, N/A} AND Confidence != Unknown AND Analyst Assessment present AND Unknown Dimensions = 0`

Chapter 11 is research-ready only when both Q58 and Q59 are research-ready.

This is a boolean completeness rule, not a weighted formula. No evidence dimension receives a weight and no dimension order implies importance.

## What V87 does not calculate

V87 does **not calculate** EV/EBIT, EV/EBITDA, EV/FCF, acquisition IRR, premium-to-book, leverage, debt coverage, dilution, synergy value, acquisition-success probability, M&A score, intrinsic value, or margin of safety. Any relevant financial facts remain read-only dependencies on the existing canonical SSOT.

## Analyst synthesis

The M&A synthesis is free-form analyst-authored text plus a workflow status (`Unknown`, `Draft`, `Reviewed`, `Final`). Research Assistant evidence can inform the analyst but never writes or changes the synthesis automatically.

## Investment boundary

Research readiness does not alter the Investment Research Gate, MOS, portfolio action, or BUY/HOLD/SELL state. It only states whether the Chapter 11 research checklist has been explicitly completed.
