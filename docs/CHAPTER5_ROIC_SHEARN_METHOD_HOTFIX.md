# Chapter 5 Q26 — Shearn ROIC Methodology Hotfix

## Why this hotfix exists

The earlier Phase 5B implementation used NOPAT over financing-capital style denominators for rows labelled `Shearn analytical`. That is a legitimate general finance ROIC variant, but it is **not** the basic equation Michael Shearn states in Chapter 5 of *The Investment Checklist*.

The source-locked correction is therefore:

- keep **Trecapital Canonical ROIC** unchanged as the app-wide Single Source of Truth;
- change only `Shearn analytical` rows to **Adjusted EBIT / Average Adjusted Invested Capital**;
- use the asset-based investment-base framework Shearn describes;
- require explicit analyst confirmation for excess cash and off-balance-sheet adjustments;
- never infer a qualitative investment conclusion from any ROIC threshold.

## Source basis

Michael Shearn, Chapter 5, “Methods of Calculating ROIC”, states the basic equation as:

`Return on invested capital = earnings before interest and taxes / invested capital`

and frames invested capital as:

`Total assets − excess cash ± accumulated amortization/depreciation ± goodwill/intangibles + off-balance-sheet items − non-interest-bearing current liabilities`.

He also explicitly instructs the analyst to use **average amounts for the investment base**, because a single quarter can create misleading ROIC, especially for seasonal businesses.

The chapter then separately discusses:

- removing excess cash;
- gross versus net PP&E;
- including versus excluding goodwill;
- including material off-balance-sheet assets/liabilities.

## Implementation boundary

### Trecapital Canonical ROIC

Unchanged. Chapter 5 reads the canonical normalized ROIC field and does not recalculate it.

### Shearn analytical numerator

`Adjusted EBIT = canonical EBIT/operating profit + analyst-confirmed signed numerator adjustments`.

Positive adjustment adds to EBIT; negative adjustment subtracts. The app never chooses the sign.

### Base investment capital

`Net Asset Investment Base = Total Assets − Non-interest-bearing Current Liabilities`.

NIBCL is taken from an explicit normalized field when available. Otherwise the app may use `Current Liabilities − Short-term Interest-bearing Debt` only when both inputs are explicit. No unsupported NIBCL is invented.

### Average base

All Shearn analytical views require a two-period average investment base. A single period does not silently substitute for the average.

### Excess cash

Only analyst-confirmed excess cash is deducted. Cash is never automatically classified as excess cash.

### Goodwill

Both including-goodwill and ex-goodwill views remain visible so acquisition economics are not hidden.

### Gross assets

The current implementation uses `Average Gross PP&E − Average Net PP&E` as a transparent accumulated-depreciation proxy for the gross-asset diagnostic.

### Off-balance-sheet capital

Only analyst-confirmed material off-BS capital is added. No lease, pension or securitized-receivable amount is fabricated.

## Acceptance criteria

The hotfix is accepted only if:

1. canonical ROIC remains unchanged;
2. every `Shearn analytical` row uses Adjusted EBIT, not NOPAT;
3. the denominator starts from average asset-based invested capital rather than Equity + Debt;
4. excess cash is never assumed automatically;
5. NIBCL is not guessed when inputs are insufficient;
6. numerator adjustments are signed and explicitly analyst-controlled;
7. prior-period data is required for the Shearn average investment base;
8. full Chapter 5 and Deep Analysis regressions pass;
9. DGC Phase 5D lock diagnostic still passes;
10. Streamlit smoke test passes.
