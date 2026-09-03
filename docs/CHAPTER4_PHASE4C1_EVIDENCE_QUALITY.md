# Chapter 4 — Phase 4C.1 Evidence Retrieval Quality

Status: implemented architecture / acceptance context.

## Why Phase 4C.1 exists

Phase 4C correctly prevented placeholder navigation links from being promoted to evidence, but live DGC CI could still return zero qualified evidence candidates when public search engines were blocked or empty. Phase 4C.1 fixes retrieval quality without weakening analyst-control guardrails.

## Source-first order

The Chapter 4 Research Assistant now uses this order:

1. trusted company/IR HTML pages already registered in Trecapital;
2. trusted annual-report PDFs already registered in Trecapital and cached locally after parsing;
3. independent/search-engine results for supporting and counter-evidence;
4. prior real-evidence cache only when the current run produces no usable candidates.

Navigation placeholders are never evidence. Cache fallback may recover only previously stored rows whose status was already a real search or direct-source extraction result.

## Official direct extraction

The official-source layer extracts contextual passages for:

- Q15 — competitive-advantage mechanisms: brand, patents, licences, switching costs, scale/location/unique assets, self-supplied raw material, vertical integration and similar mechanisms;
- Q16 — actual price/pricing passages; Pricing Power remains unproven unless price evidence also contains customer/volume/retention/demand evidence;
- Q17 — industry economics, margins, ROIC, cyclicality, barriers, supply-demand and capacity;
- Q18 — industry evolution/regime change, preferably with a year/timeline or explicit technology/regulation/capacity/structure change;
- Q19 — competitors, substitutes, low-cost/foreign competition, market share and price competition;
- Q20 — suppliers, raw materials, concentration/dependence, commodity exposure, supply-chain disruption and hedging.

Keyword extraction only surfaces candidate passages. It does not set Shearn conclusions.

## Evidence quality

Candidates are classified into:

- `A — Company/Official disclosure`
- `B — Independent financial source`
- `C — Other candidate source`

The UI now shows a per-question Evidence Quality / Coverage Audit with candidate count, A/B source counts, supporting/counter counts, and Q16 explicit price+customer/volume count.

Coverage status is diagnostic only:

- `Khá — có nguồn A`
- `Mỏng — cần bổ sung`
- `Mỏng — chưa có price + customer/volume`
- `Gap`

It is not an investment score and does not change Research Gate.

## Research gaps

The engine explicitly lists gaps for Q15–Q20 when coverage is thin or absent. Examples include missing moat erosion/copyability evidence, missing Q16 customer-response evidence, insufficient long-term industry timeline, weak competitor evidence, or missing supplier-concentration evidence.

## Persistence / provenance

Automatically appended Evidence Matrix rows use:

- `Status = Candidate — Analyst verify`
- `Data Origin = Chapter 4 Research Assistant Evidence Bridge Phase 4C.1`
- source title, URL, snippet, source quality and source method

Source methods distinguish search snippets from official HTML/PDF direct extraction and cache fallback.

Automated source refresh continues to save with `create_snapshot=False`; analyst saves retain normal version history.

## Locked guardrails

All remain false:

- synthetic peer fallback
- auto moat conclusion
- auto pricing-power conclusion
- auto industry-quality conclusion
- auto competition-intensity conclusion
- auto supplier-quality conclusion
- auto ideal-company selection
- fabricated interviews
- fabricated supplier concentration
- pricing power inferred from margin-only data
- navigation links promoted to evidence

Phase 4C.1 never changes Research Gate and never emits BUY/HOLD/SELL.

## Acceptance

Required acceptance checks:

- official HTML/PDF passages are admitted as source-A candidates;
- navigation placeholders remain excluded;
- Q16 direct-source extraction still requires price + customer/volume evidence for an explicit Pricing Power candidate;
- Q15/Q20 official passages remain candidate evidence, not conclusions;
- evidence-quality summary and gap diagnostics behave deterministically;
- existing analyst assessments/conclusions are preserved during merge;
- full Chapter 1–4 regression passes;
- DGC live diagnostic reports real peer discovery, canonical financial refresh, source-method distribution, candidate coverage and gaps without synthetic evidence;
- unified Streamlit page starts successfully.
