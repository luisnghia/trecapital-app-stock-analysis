# Formula Explanation — Chapter 10 Phase 10H / V81

V81 adds **no new financial formula**.

The phase integrates version history and analyst re-review only. Chapter 10 continues to consume canonical financial evidence through the existing read-only data bridge. It does not recalculate or own revenue growth, margins, ROIC, cash conversion cycle, debt, CapEx or any other financial SSOT.

The neutral delta engine is a record-comparison rule rather than an investment formula:

- identical canonicalized values → `Unchanged`
- empty before / populated after → `Added`
- populated before / empty after → `Removed`
- otherwise → `Changed`

A `Changed` result does **not** mean growth improved or deteriorated. No weight, score or direction is attached to it.

The source-baseline fingerprint is SHA-256 over Chapter 10 research-facing workspace state (question status, confidence, dimension status, promoted evidence and research gaps). It deliberately excludes canonical financial SSOT values and is used only to identify whether the research baseline changed.

No Growth Score, weighted score, automatic forecast, valuation formula, intrinsic value, MOS adjustment, Investment Research Gate or BUY/HOLD/SELL logic is introduced by V81.
