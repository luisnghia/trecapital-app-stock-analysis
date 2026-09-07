# Chapter 8 Phase 8P / V61 — Official Document Expansion + Section-Directed Retrieval

## Why V61 exists

V59 recovered one additional real DGC source-locked dimension through OCR. V60 then re-OCR'd gap-relevant pages at higher resolution but did not close another dimension. That result indicates that the limiting factor is no longer OCR resolution alone; the official-document corpus itself must be expanded.

## V61 research loop

1. Start from the currently open source-locked Q39–Q47 dimensions.
2. Map those dimensions to six management-research sections: stakeholders; people/culture/hiring; strategy/operating model; guidance/accountability; cost discipline; capital allocation/buyback.
3. Map each section to likely official document families such as annual reports, governance reports, AGM materials, board resolutions, business-plan disclosures, M&A and dividend/buyback disclosures.
4. Crawl only bounded same-domain issuer/IR archive and landing pages. Search-engine snippets are not evidence inputs.
5. Discover and rank official PDF links by section relevance, year and document family.
6. Prefer documents with a usable text layer. Only a small bounded number of scanned PDFs are allowed into the expensive V60 OCR path.
7. Reuse the existing Chapter 8 candidate extraction/gap engine and recompute remaining gaps.

## Source and analyst boundaries

- Trecapital canonical remains the financial SSOT.
- Chapter 7 remains the manager identity/background SSOT.
- Only company/IR URLs that pass the existing official-source allow-list are accepted.
- Every extracted row remains `Candidate — analyst verify`, `Select=False`.
- No evidence is auto-promoted.
- No Analyst Assessment, Confidence or question Status is written.
- No management score, MOS, Research Gate or BUY/HOLD/SELL is produced.
- Q43 remains exactly 14 dimensions.
- Q46 remains exactly five Shearn capital-allocation actions; discipline/hurdle context is not a sixth action.
- Q47 still requires explicit buyback/repurchase evidence; share-count decline is not proof.

## Runtime controls

Discovery, landing-page traversal, downloads and OCR are all bounded. V61 diversifies selected documents across sections and prioritizes PDFs with a native text layer so that expanding the historical evidence set does not reproduce V59's long all-page OCR runtime.

## Acceptance philosophy

Live acceptance must prove that V61 can discover and fetch real historical official issuer documents and preserve all source/analyst boundaries. It does not require a fixed number of gaps to close: if official documents do not support a dimension, that dimension remains open.
