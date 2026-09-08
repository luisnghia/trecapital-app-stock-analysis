# Formula Explanation — Appendix A Phase C / V92

V92 introduces **no financial formula and no investment-scoring formula**.

The deterministic functions are research-record utilities only:

1. **Source baseline fingerprint** = SHA-256 of normalized Appendix A `sections`, `sources`, `interviews`, and `research_gaps`. It detects whether analyst-owned source-facing research state changed; it does not judge quality or freshness.
2. **Neutral delta** compares canonical before/after values. Equal → `Unchanged`; empty→non-empty → `Added`; non-empty→empty → `Removed`; otherwise → `Changed`.
3. **Interview lineage** reports persisted provenance fields: Interview ID, Source ID, date, statement type, Q01–Q59 references, whether source response exists, whether uncertainty is noted, and whether analyst commentary exists.
4. **Version lineage** reports snapshot metadata and counts of sources/interviews/open gaps. Counts are descriptive only and are never combined into a score.

No new financial formulas are added. No source/credibility score, weighted research score, forecast, intrinsic value, MOS, Research Gate, or BUY/HOLD/SELL state is calculated or changed.
