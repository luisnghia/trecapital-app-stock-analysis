# Chapter 4 — LOCKED Acceptance

Status: **LOCKED — Phase 4D final acceptance passed on 2026-09-04**.

Source framework: Michael Shearn, *The Investment Checklist*, Chapter 4 — Q15 to Q20.

## Meaning of LOCKED

`LOCKED` means the Chapter-4 implementation has passed final acceptance for architecture, persistence, provenance, evidence hygiene, analyst ownership and regression safety. It does **not** mean every ticker has complete evidence, a moat, Pricing Power, a good industry, low competition, good suppliers, or an investment recommendation.

Stock-specific unknowns remain Research Gaps. A missing evidence item is preferable to fabricated evidence.

## Locked architecture

- Q15 — Sustainable Competitive Advantage
  - 6 Shearn sources: Network Economics; Brand Loyalty; Patents; Regulatory Licenses; Switching Costs; Cost Advantages from Scale / Location / Unique Asset.
  - 1 explicit `Analyst-defined` extension.
  - Each specific advantage keeps mechanism, supporting evidence, counter-evidence, copyability, time to copy/replace, structural character, current strength, trend, erosion threat, reinvestment runway, confidence and analyst conclusion.
- Q16 — Pricing Power
  - Retention, price sensitivity, customer economics, quality-vs-price, actual pricing events, segment scope and price-transparency risk.
  - Price-only, margin-only and commodity/cost-pass-through evidence cannot become Pricing Power automatically.
  - A non-confirmed corroboration row is explicitly kept as a Q16 Research Gap; it can never be mistaken for confirmed multi-source corroboration.
- Q17 — Good or Bad Industry
  - Automatic same-industry peer discovery and canonical ROIC/EBIT/CCC bridge.
  - Analyst alone selects Good / Mixed / Bad.
- Q18 — Industry Evolution
  - Long-run timeline, Then-vs-Now, management claims vs history, regime/inflection analysis.
- Q19 — Competitive Landscape
  - Eight workspace buckets: Limited/Direct Competition; How Competitors Compete; Fierceness/Price Competition; Substitute Products; Low-cost Country Competition; Industry Standard/Market Position; Industry Change/Capacity Competition; Why Competitors Failed.
  - Same-industry peer is candidate context only, never automatic direct competitor.
- Q20 — Supplier Relationships
  - Supply reliability, supplier innovation, concentration, supply-chain operating evidence and commodity dependence.

## Final Phase 4D hardening

1. Low-relevance search noise is quarantined rather than silently deleted.
2. Source-C candidates require both Chapter-4 semantic relevance and target/company/industry anchoring.
3. A/B evidence retained for lock must have URL, excerpt, source-quality classification and source method.
4. `Why Competitors Failed` requires an explicit failure/exit event plus a causal clue; source C alone cannot close this gap.
5. Q19 lock coverage counts A/B evidence; source C never closes a Shearn bucket.
6. A stock-specific `Why Competitors Failed` gap may remain open at module lock if it is explicitly surfaced as a Research Gap. This prevents fabrication.
7. Q16 period-level corroboration is only confirmed when the corroboration status explicitly meets the multi-source rule; otherwise Q16 remains a visible Research Gap.
8. Chapter-4 lock metadata is persisted without modifying analyst-owned Q15–Q20 conclusions.
9. Snapshot/restart/persistence are regression-tested.
10. All Chapter 4 and Chapters 1–3 tests must remain green.
11. Streamlit unified-page smoke test must pass.

## Immutable analyst boundary

Research Assistant / Data Suggested may find, classify and organize candidate evidence and quantitative context. They may not automatically set or overwrite:

- Sustainable Competitive Advantage / moat conclusion;
- Pricing Power;
- Good / Mixed / Bad Industry;
- Competition Intensity;
- Supplier Quality / Supplier Relationship;
- Ideal Company selection;
- Analyst Trend / Confidence / Conclusion;
- Research Gate;
- BUY / HOLD / SELL.

## DGC final acceptance result

DGC remains the acceptance ticker because its commodity/chemical economics stress-test the distinction between real Pricing Power and commodity/pass-through, and between same-industry peers and meaningful competitors.

Final Phase 4D live result:

- Industry: Hóa chất; automatic peer universe: 31 rows; no synthetic peer fallback.
- Retained evidence after hygiene filter: 76 candidate rows.
- Quarantined low-relevance/noise rows: 3; retained Source-C rows used for lock coverage: 0.
- Q19 A/B evidence coverage: 7/8 workspace buckets.
- `Why Competitors Failed`: no legitimate A/B evidence was found, therefore it remains an explicit Research Gap rather than being fabricated.
- Q16: explicit pricing candidates exist, but the final live run did not have confirmed period-level multi-source corroboration; Q16 therefore remains an explicit Research Gap and no Pricing Power conclusion is produced.
- 29 Research-Assistant guardrail flags remain `False`.
- Phase 4D lock tests plus Q16 semantic regression passed.
- Full `modules/deep_company_analysis` regression: **113 tests passed**.
- DGC live lock diagnostic: PASS.
- Unified Streamlit page smoke test: PASS.

The DGC acceptance run therefore proves the intended policy: the Chapter-4 implementation can be locked while legitimate ticker-specific Research Gaps remain visible, provided no synthetic, unrelated or inferred evidence is used to hide them.

## Version

Final locked package: **Offline V22 — CHAPTER4_LOCKED_FINAL**.
