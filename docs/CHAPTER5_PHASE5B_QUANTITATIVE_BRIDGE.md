# Chapter 5 — Phase 5B Quantitative Bridge

Status: implementation candidate pending CI at creation time.

## Scope

Phase 5B connects existing Trecapital canonical data to:

- Q22: 10-year financial/operating context supporting the analyst's Operating Metric Registry.
- Q25: debt, liquidity and debt-service context when canonical fields exist.
- Q26: canonical ROIC plus explicitly labelled Shearn analytical views, distortion diagnostics and descriptive incremental-return context.

It does **not** automate the analyst's conclusions.

## User amendments included

1. Chapter 5 has no Confidence fields.
2. Q23 defaults are seeded only for a brand-new record and may be deleted permanently afterward.
3. Q23 `Origin` remains internal provenance but is hidden from the editable Risk table to reduce clutter.

## Chapter 4 peer workflow amendment

Q17/Q19 quantitative peer analysis now separates discovery from download:

1. Load broad same-industry candidate list.
2. Analyst removes, unchecks, or manually adds comparable companies.
3. Analyst presses Confirm & Update.
4. Only that curated ticker set is sent through the existing FireAnt + Vietstock canonical refresh.
5. Q17 and Table 4.2 Q19 are rebuilt from the confirmed set; removed peers are not silently restored.

The target company is always kept as the benchmark anchor. Newly discovered companies never silently enter an already-confirmed peer set.

## Guardrails

- no synthetic peers;
- no canonical refresh before analyst confirmation;
- no automatic Good/Bad Industry conclusion;
- no automatic Ideal Company selection;
- no automatic operating-metric criticality;
- no automatic Strong/Weak Balance Sheet conclusion;
- no automatic ROIC-quality or compounder conclusion;
- no assumption that all cash is excess cash;
- no fabricated off-balance-sheet obligations;
- no Research Gate changes;
- no BUY/HOLD/SELL.
