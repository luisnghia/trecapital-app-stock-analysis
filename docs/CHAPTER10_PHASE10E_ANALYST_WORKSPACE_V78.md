# Chapter 10 Phase 10E / V78 — Analyst Workspace & Persistence

## Source boundary
Michael Shearn, *The Investment Checklist*, Chapter 10 — **Evaluating Growth Opportunities**, Q53–Q57, printed pages 281–303. Phase 10E does not alter the V74/V75 source lock or the 34 evidence dimensions.

## What V78 adds
- persistent analyst-owned workspace keyed by ticker;
- Streamlit workspace for Q53–Q57 and all 34 dimensions;
- explicit analyst status, confidence, assessment and Q53 growth-mode controls;
- Research Assistant candidate review and explicit evidence promotion;
- promoted-evidence provenance and UI dedupe via stable Candidate ID;
- open research-gap view;
- shared navigation entry for the Chapter 10 workspace.

## Hard boundaries
Research candidates remain suggestions until the analyst explicitly promotes them. Promotion does **not** change question status, confidence, dimension status, growth mode or analyst assessment. Saving persists only Chapter 10 analyst workspace data and promoted evidence; it does not copy or mutate canonical financial SSOT data. Missing evidence stays Unknown.

No Growth Score, weighted score, automatic growth forecast, intrinsic-value formula, MOS change, Investment Research Gate change or BUY/HOLD/SELL behavior is introduced.

## Persistence
`chapter10_store.py` uses a dedicated SQLite store for the Chapter 10 analyst payload. The database is not a financial data store. Canonical metrics such as revenue, CFO, margins, CCC/DIO/DSO/DPO, CapEx, debt and ROIC remain dependencies of the existing read-only data bridge and are not persisted as new Chapter 10 SSOT fields.

## UI
The V78 workspace is exposed through `pages/08_Phan_tich_tang_truong.py` and linked from the shared sidebar. The user can review each source-locked question/dimension, add Research Assistant candidates, select candidates and explicitly promote them, inspect promoted evidence and research gaps, and save the workspace.
