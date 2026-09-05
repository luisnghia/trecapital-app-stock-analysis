# Chapter 6 — Phase 6D Final Source Closure V33

Status: **APPROVED by analyst/user and implemented after V32 review**.

Primary framework: Michael Shearn, *The Investment Checklist*, Chapter 6 — **Evaluating the Distribution of Earnings (Cash Flows)**.

## Purpose

Phase 6D closes the remaining source-derived gaps before Chapter 6 can be marked `Complete / Source-Closed`. It does not add a quality score and it does not create an investment recommendation.

## Q27 — Income-tax Footnote Analyzer

The source asks the analyst to compare Current Tax with the Income-Tax Provision over approximately 5–10 years where disclosed.

Implementation lock:

- Current Tax must come from an explicit current-tax/current-income-tax disclosure.
- `tax_paid_bil`, cash taxes paid, or a cash-flow tax-payment line may **not** be substituted for Current Tax expense.
- Table: `Period | Tax Provision | Current Tax | Difference | Difference % | Source | Disclosure Status | Analyst Note`.
- `Difference = |Current Tax| - |Tax Provision|`.
- `Difference % = |Difference| / |Tax Provision| × 100` when the denominator is valid.
- Missing disclosure remains `N/A`; no synthetic TTM tax-footnote value is created.
- Phase 6C focused research expands to Current Tax, Income-Tax Provision and tax-footnote disclosures.

Phase 6D also adds an **Unsustainable Earnings / One-off Register** covering source-relevant items such as debt-retirement/extinguishment gains or losses, restructuring/write-offs and temporary reductions in advertising, R&D or maintenance when evidence exists.

## Q30 — Operating Leverage × Debt Bridge

The source warns that high operating leverage becomes more consequential when combined with a material debt burden.

Implementation lock:

- DOL comes from the existing Phase 6B Chapter-6 calculation.
- Net Debt, Debt/EBITDA, EBIT/Interest and CFO/Interest reuse the Chapter-5 shared balance-sheet diagnostic path.
- Chapter 6 does not duplicate the leverage formulas.
- No distress score or automatic risk classification is produced.
- The analyst decides whether the combination materially widens the earnings/cash-flow distribution.

## Q32 — Asset Replacement / PP&E Age Register

Phase 6D adds a source-locked research register for:

- asset class;
- Gross PP&E and Net PP&E;
- Net/Gross PP&E diagnostic;
- depreciable vs non-depreciable assets;
- explicit land/non-depreciable exclusion;
- estimated age / remaining life;
- replacement timing;
- accelerated-depreciation/comparability issue;
- maintenance / growth / regulatory classification;
- expected replacement burden;
- supporting evidence, counter-evidence and analyst assessment.

`Net/Gross PP&E` is a diagnostic only. It is never relabelled as maintenance capex or an automatic replacement forecast.

## Distribution Width → Valuation Method Bridge

The chapter's central concept is that valuation precision depends on the width of the future earnings/cash-flow distribution.

Implementation:

- `Narrow / Moderately Narrow`: point-estimate / normalized earnings or FCF review may be more useful.
- `Medium`: hybrid point estimate plus explicit downside/upside review.
- `Moderately Wide / Wide`: Bear/Base/Bull scenario analysis is preferred.
- `Unknown`: valuation-method selection remains open.

All assumptions remain analyst-owned. The app does not set probabilities, revenue, margins, normalized earnings/FCF, fair value, MOS or BUY/HOLD/SELL.

## Final Source Checklist

The final checklist covers:

1. Current Tax vs Tax Provision.
2. CFO vs Net Income and accounting-policy/estimate quality.
3. Unsustainable earnings / one-offs.
4. Revenue recurrence/durability.
5. Cyclicality and supply/demand context.
6. Operating leverage plus debt interaction.
7. Working-capital/CCC mechanism.
8. Maintenance/growth/regulatory capex and asset replacement.
9. Distribution Width → valuation-method review.

Allowed checklist status:

`Unknown / Covered / Evidence weak / N/A`.

## Completion Gate

`Chapter 6 Complete / Source-Closed` is analyst-confirmed only.

Blocking conditions include:

- any Q27–Q32 research status is not `Answered/N/A`;
- Distribution Width remains `Unknown`;
- analyst summary is blank;
- any Final Source Checklist item is not `Covered/N/A`;
- any research gap is not `Closed/Resolved/Accepted/N/A`;
- for `Moderately Wide/Wide`, Bear/Base/Bull scenarios do not each contain analyst assumption + evidence.

Critical unknowns remain visible as a warning and require an analyst residual-uncertainty note; they do not automatically become a Buy/Sell signal.

## TTM boundary

- Canonical financial tables continue to valid TTM when available.
- Chapter-5 leverage bridge uses latest valid TTM where available.
- Annual-only tax-footnote analysis does not fabricate TTM.
- Asset-replacement register is `as-of` evidence, not a TTM calculation.
- Annual-only manipulation models remain latest annual + explicit `TTM = N/A` methodology guardrail.

## Analyst boundary

Phase 6D must not automatically set or modify:

- Conservative/Liberal accounting;
- recurring-revenue quality/share;
- cyclical/countercyclical/recession-resistant classification;
- operating-leverage risk conclusion;
- maintenance capex;
- Distribution Width;
- valuation assumptions;
- MOS;
- Research Gate;
- BUY/HOLD/SELL.
