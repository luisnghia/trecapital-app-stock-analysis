# Chapter 4 — Phase 4C Research Assistant Evidence Bridge

Status: implementation specification / acceptance context.

## Scope

Phase 4C extends the approved Shearn Chapter 4 workspace without changing the analyst-control contract.

### Q17/Q19 automatic same-industry peer workflow

The manual `Peer tickers` input and the separate `Đưa canonical peer snapshot vào Q17` step are removed from the normal workflow.

The app now:
1. resolves the target ticker to its real Simplize same-industry page using the same `PublicSimplizeCrawler` already used by Trecapital's company-comparison page;
2. reads the actual listed tickers; no synthetic peer fallback is allowed;
3. orders the target first and peers by available market cap; the automatic universe accepts up to 60 actual same-industry tickers per run, enough for the current DGC/Hóa chất universe returned by the source, while still bounding network fan-out;
4. refreshes the discovered peer universe with a deliberately small maximum of 3 concurrent workers to reduce waiting time without hammering public data sources;
5. on `Tự động lấy cùng ngành + BCTC và cập nhật Q17/Q19`, refreshes each peer through Module 1's existing `FireAnt + Vietstock` source and normalization/cache pipeline using low-level fetch/export functions, so the active ticker is not changed and `st.rerun` is not triggered for every peer;
6. rebuilds canonical Chapter 4 snapshots and writes the quantitative rows directly into `q17_industry_peers` while preserving analyst `Comment` fields;
7. uses the same peer table for Q19 Table 4.2 quantitative benchmark.

If peer discovery fails, the app may use the previously saved peer set only. It must not invent peers. If a discovered peer cannot obtain canonical statements, that peer remains missing/Unknown rather than being replaced with another data source or fabricated values.

## Phase 4C evidence architecture

Research Assistant searches four focused evidence groups:
- Q15/Q16 — competitive-advantage sources, erosion/threat evidence, and actual pricing/customer-response evidence;
- Q17/Q18 — industry economics and >10-year/evolution/regime-change evidence;
- Q19 — competitors, substitutes, low-cost foreign competition, price wars and competitor failures;
- Q20 — suppliers, raw materials, supplier concentration, supply-chain disruption, commodity exposure and hedging.

The agent reuses `WebEvidenceAgent`, official/company IR navigation sources and Trecapital's existing web-evidence cache. Search results are mapped to Chapter 4 evidence candidates.

Direct-source navigation placeholders such as `Link nguồn ưu tiên` are **not evidence** and cannot enter the Evidence Matrix. Only actual search findings marked `Tìm thấy` may become evidence candidates.

### Q15 source mapping

Candidate subtopics follow the approved Shearn structure:
- Network Economics
- Brand Loyalty
- Patents
- Regulatory Licenses
- Switching Costs
- Cost Advantages — Scale / Location / Unique Asset
- generic competitive-advantage candidate when the mechanism is not yet clear

Research Assistant may suggest the mechanism but may not set Copyability, Time to Copy/Replace, Structural Character, Strength, Trend or overall Sustainable Advantage.

### Q16 explicitness guardrail

A price mention is not sufficient for Pricing Power.

`Explicit price + customer/volume candidate` requires both:
- an explicit price/pricing change term; and
- customer/volume/retention/churn/demand evidence.

Otherwise the evidence remains `Price mention only — insufficient for Pricing Power`.

Historical margins from Phase 4B remain supporting context only.

### Evidence Matrix merge

Phase 4C is allowed to append rows automatically to the Chapter 4 Evidence Matrix with:
- `Status = Candidate — Analyst verify`
- `Direction = Supporting/Contradicting/Neutral — Candidate`
- source title, URL, snippet, source quality and data origin

It does not overwrite analyst-created evidence rows or analyst assessments.

System peer/evidence refresh uses `save_record(..., create_snapshot=False)` so analyst version history is not polluted by automated data/evidence refreshes. Analyst saves still create normal snapshots.

## DGC live diagnostic — 03/09/2026

The Phase 4C live CI diagnostic resolved DGC to `Hóa chất` and returned 31 same-industry listed tickers from the live source in that run. The diagnostic refreshed a representative canonical sample `DGC, VAF, NFC`; all 3/3 returned canonical bundles with 12 annual periods and 22 quarterly periods. No synthetic fallback was used.

The same CI run returned zero qualified web evidence candidates for Q15–Q20. This is intentionally reported as zero rather than promoting source-navigation placeholders or fabricating evidence. It proves the no-fabrication guardrail; it does **not** mean the company has no relevant evidence. In the app, Research Assistant evidence coverage depends on reachable web/search sources and previously cached Trecapital evidence.

## Locked guardrails

All must remain false:
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

Phase 4C never changes Research Gate and never emits BUY/HOLD/SELL.

## Acceptance

Required tests:
- real peer discovery is deduplicated and target-first;
- no synthetic peer fallback;
- peer refresh uses existing Trecapital normalization/cache pipeline without `search_and_bind` reruns;
- Q15 brand/cost evidence remains candidate, not moat conclusion;
- Q16 explicit pricing requires price + customer/volume evidence;
- supplier risk remains evidence, not supplier rating;
- direct source-navigation placeholders are not promoted to evidence;
- evidence merge preserves saved analyst assessments/conclusions;
- Chapter 1–4 full regression passes;
- unified Streamlit deep-analysis page starts successfully.
