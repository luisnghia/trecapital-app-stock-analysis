# Appendix A — Phase C / V92

## Scope

Implements immutable snapshot/history, interview lineage, neutral delta and closure audit for Michael Shearn, *The Investment Checklist*, Appendix A — **Building a Human Intelligence Network**.

Source lock remains the four Appendix A sections: Evaluating Information Sources; How to Locate Human Sources; How to Contact Human Sources—and Get the Information You Want; Create a Database of Your Interviews for Future Reference.

## Architecture

- `appendix_a_store.py` persists current analyst-owned workspace plus immutable normalized snapshots.
- `appendix_a_history.py` provides version lineage, interview lineage, source-baseline fingerprint and neutral comparison.
- `pages/10_Mang_nguon_tin.py` exposes lineage and snapshot-to-current comparison.
- Q01–Q59 links remain references only; chapter-owned research state is never copied or mutated.

## Source-locked interpretation

Appendix A instructs the investor to preserve interview details, avoid silently adding personal interpretation to what a source said, and explicitly note uncertainty. V92 therefore preserves `Source Response / Observation`, `Uncertainty Noted`, and `Analyst Commentary` as separate lineage fields.

## Closure boundary

Appendix A history is not a scoring model. There is no source score, credibility score, weighted research score, automated truth judgement, BUY/HOLD/SELL, valuation/MOS change or Investment Research Gate change. Snapshot deltas use only `Unchanged`, `Added`, `Removed`, and `Changed`.

Appendix A is considered implementation-complete after V92 closure QA. The next source section is Appendix B — **How to Interview the Management Team**.
