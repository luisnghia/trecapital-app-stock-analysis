# Chapter 4 — LOCKED Acceptance

Status: **LOCK CANDIDATE until Phase 4D CI passes**.

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
7. Chapter-4 lock metadata is persisted without modifying analyst-owned Q15–Q20 conclusions.
8. Snapshot/restart/persistence are regression-tested.
9. All Chapter 4 and Chapters 1–3 tests must remain green.
10. Streamlit unified-page smoke test must pass.

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

## DGC final acceptance policy

DGC remains the acceptance ticker because its commodity/chemical economics stress-test the distinction between real Pricing Power and commodity/pass-through, and between same-industry peers and meaningful competitors.

The DGC acceptance run may finish with legitimate stock-specific Research Gaps. The module is lockable only if those gaps are visible and no synthetic or unrelated evidence is used to hide them.

## Version

Phase 4D package: **Offline V22** after CI success.
