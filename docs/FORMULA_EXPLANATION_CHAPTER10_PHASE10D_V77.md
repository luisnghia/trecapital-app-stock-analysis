# Formula / Logic Explanation — Chapter 10 Phase 10D V77

Phase 10D introduces **research-routing logic only**. It deliberately does not introduce a new financial formula, forecast engine, weighted score, valuation method, or investment signal.

## Candidate matching

For each source-locked evidence dimension, V77 derives operational matching terms from the dimension label, source anchor, and declared SSOT dependency. A candidate source is routed to dimensions whose research vocabulary overlaps the source title/evidence text. This overlap is only a retrieval aid; it is not evidence strength, probability, confidence, or a score.

## Source grades

- **A — Official**: company official domain, regulator, or exchange disclosure.
- **B — Independent**: an identifiable external web source.
- **C — Context**: source cannot be reliably classified from a URL/file reference.

The grade reflects source family/provenance, not whether the underlying claim is true.

## Stable candidate ID

A candidate ID is a deterministic SHA-256 prefix over dimension ID + source reference + title + evidence text. This supports de-duplication only; it has no analytical meaning.

## Explicit promotion boundary

`promote_selected_candidates()` requires an explicit set of candidate IDs. Without a selected ID, no evidence is promoted. With explicit selection, only evidence rows are appended. Question status, confidence, analyst assessment, growth mode and dimension status remain unchanged until the analyst changes them in a later workspace phase.

## Financial SSOT boundary

Phase 10D does not recompute financial metrics. In particular, the book-defined cash conversion cycle relation

`CCC = DIO + DSO - DPO`

is **not calculated by V77**. Chapter 10 continues to consume canonical CCC only through the V76 data bridge. Likewise, acquisition-spend/CFO, margins, unit economics, R&D/sales and other metrics remain canonical-data dependencies rather than new Chapter 10 formula engines.

## Investment boundary

V77 does not create or modify Growth Score, future-growth forecast, intrinsic value, MOS, Investment Research Gate, portfolio action, or BUY/HOLD/SELL.
