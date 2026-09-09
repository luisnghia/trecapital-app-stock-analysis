# Deep Company Analysis V99 — Financial Metric Semantics & TTM Provenance Hardening

## 1. Why V99 exists

A full DGC trial exposed a canonical-data ambiguity that is material to research quality:

- consolidated profit after tax and profit attributable to shareholders of the parent can be different;
- EPS belongs to the parent shareholders and must not be silently derived from consolidated-only profit;
- a raw `TTM` label is insufficient for research lineage unless the ending quarter is visible;
- a 1–3 quarter partial sum must never be presented as a 12-month flow.

V99 hardens the existing Trecapital financial SSOT. It does **not** create a second financial dataset, a new valuation engine, or an automatic investment conclusion.

## 2. Source / architecture boundary

Michael Shearn's checklist requires the analyst to understand the business and to identify unanswered questions rather than hide uncertainty. The book also stresses that cyclical earnings are more difficult to forecast. V99 does not add a book-derived valuation formula; it is an engineering/data-provenance control that supports those source-locked research questions.

The existing architecture remains:

`Public financial sources -> normalize/validate -> Trecapital canonical dataset -> Module 1 / Module 2 / Investment Checklist / Deep Company Analysis`

Deep Company Analysis remains a **consumer** of canonical financial facts.

## 3. Canonical field contract

V99 adds explicit semantic fields while retaining the legacy field for compatibility:

| Field | Meaning |
|---|---|
| `net_profit_consolidated_bil` | Consolidated profit after tax |
| `net_profit_parent_bil` | Profit after tax attributable to shareholders of the parent |
| `net_profit_bil` | Backward-compatible canonical/legacy profit alias |
| `net_profit_scope` | `parent_attributable`, `consolidated`, `unspecified`, or Unknown |
| `period_display` | Human-readable period label |
| `ttm_end_period` | Explicit ending quarter for a TTM row, e.g. `Q2/2026` |
| `comparability_status` | Source/analyst supplied comparability state; no AI inference |
| `comparability_note` | Source/analyst note explaining reclassification/restructuring issues |

Compatibility rule for `net_profit_bil`:

1. explicit parent-attributable PAT when available;
2. otherwise an existing legacy PAT value;
3. otherwise consolidated PAT.

If consolidated PAT is the only explicit scope, `net_profit_scope` remains `consolidated`; the value is never relabelled as parent-attributable.

## 4. FireAnt semantic mapping

For the exact FireAnt income statement parser used by Trecapital:

- line ID `19` -> `net_profit_consolidated_bil`;
- line ID `21` -> `net_profit_parent_bil`.

The generic FinancialInfo `ProfitAfterTax` / `ProfitAfterTax_MRQ` fields continue to map to the legacy `net_profit_bil` because their parent/consolidated scope is not asserted by V99. Exact statement facts take precedence where available.

No ticker-specific DGC hardcode is added.

## 5. EPS guardrail

EPS can be derived from:

- explicit parent-attributable PAT; or
- a legacy PAT whose scope is not explicitly consolidated.

If a row is explicitly `net_profit_scope == "consolidated"` and no parent-attributable PAT exists, derived EPS remains Unknown unless EPS is separately sourced.

The existing valuation formulas are unchanged. Their EPS fallback receives the same semantic guardrail so a consolidated-only PAT cannot be converted into a shareholder EPS proxy.

## 6. TTM contract

The raw compatibility field remains:

- `period = "TTM"`

The visible research period becomes, when the latest quarter is known:

- `period_display = "TTM đến Qn/YYYY"`
- `ttm_end_period = "Qn/YYYY"`

Example: `TTM đến Q2/2026`.

For flow fields, a TTM value is calculated only when **all four** component quarters are non-null. A partial 1–3 quarter sum remains Unknown.

Balance-sheet/stock fields continue to use the latest-quarter point-in-time values; existing trailing-average denominator logic remains unchanged.

## 7. Deep Company Analysis integration

Chapter 6 quantitative evidence now exposes, where available:

- LNST canonical/legacy;
- consolidated LNST;
- parent-attributable LNST;
- profit scope;
- dated TTM period;
- provenance table with source field, source module, source period and data origin;
- comparability metadata;
- semantic warnings when scope/as-of information is incomplete.

The V99 panel is read-only. Missing facts remain Unknown.

## 8. Investment-boundary guardrails

V99 does not add or change:

- overall checklist score;
- management/growth score;
- BUY/HOLD/SELL recommendation;
- automatic Research Gate;
- valuation formula;
- MOS formula;
- analyst assessment ownership;
- AI role (still Research Assistant).

The only valuation-adjacent change is an input-validity guardrail: an explicitly consolidated-only PAT is not allowed to masquerade as parent EPS.

## 9. Acceptance criteria

V99 is accepted only if all of the following pass:

1. FireAnt ID 19 and ID 21 remain separate canonical fields.
2. Legacy `net_profit_bil` prefers explicit parent PAT while keeping scope metadata.
3. Consolidated-only PAT cannot create a fake EPS or EPS-based MOS input.
4. TTM flow requires four complete quarters.
5. TTM display identifies the ending quarter when available.
6. Chapter 6 exposes semantic/provenance fields without automatic judgement.
7. Existing parser, TTM and Chapter 6 regressions pass.
8. Full Deep Company Analysis test suite passes in CI.
9. Production Streamlit health endpoint passes in CI.
10. Offline package and machine-readable acceptance report are produced.
