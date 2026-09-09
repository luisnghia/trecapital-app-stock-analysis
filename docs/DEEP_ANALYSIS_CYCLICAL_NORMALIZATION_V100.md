# Deep Company Analysis V100 — Cyclical Normalization & Historical Comparability

## Purpose
V100 adds a read-only 5–10 year cycle-normalization layer on top of the existing Trecapital canonical financial dataframe. It does not fetch or persist a second financial dataset and does not alter Module 2 valuation/MOS.

## Normalized metrics
- Revenue
- Gross margin
- EBIT / operating margin
- ROIC
- Canonical net income

For each metric the engine exposes annual observation count, median, trimmed mean, 25th/75th percentile scenario range, observed trough/peak, latest annual value, latest TTM overlay, latest-vs-median delta, source field, source module, source period and data origin.

## Formula policy
Median and percentile ranges are descriptive cycle statistics. The trimmed mean drops one highest and one lowest observation only when at least seven valid annual observations are present; otherwise it equals the ordinary arithmetic mean. TTM is excluded from annual baselines to avoid overlap double-counting and is shown only as a current overlay.

## Peak / trough flags
Each historical annual observation is compared against the 25th and 75th percentile of its own metric window. Values at/below P25 are labelled `trough-zone`; values at/above P75 are labelled `peak-zone`. These are descriptive flags, not investment signals.

## Historical comparability
Rows carrying a non-comparable status or a comparability note are surfaced explicitly in `comparability_breaks()`. They are not silently removed. This preserves the analyst's ability to judge accounting changes, structural changes, extraordinary disruptions and other basis breaks.

## Guardrails
- Financial SSOT remains the Trecapital Data Layer / Module 1 canonical dataframe.
- No duplicate normalized statement store is introduced.
- No intrinsic-value, MOS or valuation formula is modified.
- No weighted management/growth/checklist score is created.
- No automatic BUY/HOLD/SELL or Research Gate change is created.
- AI remains `Research Assistant`; the analyst owns interpretation and conclusions.
- Fewer than five valid annual observations is explicitly low-confidence.
- TTM never enters the annual cycle baseline.

## Intended downstream use
V100 is the normalization engine to be consumed by later evidence-rich reporting/UI phases. Downstream consumers should display the normalized range beside canonical historical values and provenance rather than copying data into a new SSOT.
