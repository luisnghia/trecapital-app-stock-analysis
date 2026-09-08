# Deep Company Analysis — Chapter 11 Phase 11D / V85

## Scope

Source lock remains Michael Shearn, *The Investment Checklist*, Chapter 11 — **Evaluating Mergers & Acquisitions**, printed pages 305–322, questions Q58–Q59.

- Q58 — How does management make M&A decisions?
- Q59 — Have past acquisitions been successful?
- Source-locked evidence dimensions: 15 total (Q58 = 8, Q59 = 7).

V85 adds a deterministic Research Assistant bridge. It converts each source-locked dimension into a research plan, accepts raw research records as candidate evidence, grades source family at a basic provenance level, identifies open research gaps, and requires explicit analyst selection before evidence is promoted into the Chapter 11 workspace.

## Analyst ownership

Research Assistant output is not a conclusion. Candidate evidence cannot automatically change question status, confidence, analyst assessment, dimension status, acquisition-success judgment, or any investment output. Promotion requires the selected Candidate ID to be supplied explicitly by the analyst/UI.

## Source hierarchy

The bridge labels company/regulator/exchange domains as `A — Official`, other URL-backed sources as `B — Independent`, and non-URL context as `C — Context`. This is provenance organization only; it does not make the evidence true or sufficient. Analyst verification remains required.

## Source-locked framing

Q58 research queries preserve Shearn's framing around how and why management made an acquisition decision, including merits, prospects, costs, risks, motives, revenue/cost synergy assumptions, customer overlap, roll-up economics and the predictive value of reasoning used on smaller historical deals.

Q59 research queries preserve the seven evaluation lenses already locked in V83: core competency fit; management understanding of the target; customer retention; employee/talent retention; price discipline and willingness to walk away; price paid/post-deal economics; and financing/risk tolerance.

## Boundaries

V85 introduces no M&A score or weighted score, no automatic declaration that an acquisition succeeded or failed, no synergy forecast, no BUY/HOLD/SELL signal, no intrinsic-value/MOS change, and no Investment Research Gate change. It does not duplicate canonical financial SSOT. Quantitative dependencies remain read-only and belong to the V84 canonical data bridge/upstream SSOT.

## Next phase

The next additive phase should integrate the Chapter 11 research candidates, open gaps and explicit promotion flow into a persistent analyst workspace/Streamlit workflow while preserving the same source lock and analyst ownership boundaries.
