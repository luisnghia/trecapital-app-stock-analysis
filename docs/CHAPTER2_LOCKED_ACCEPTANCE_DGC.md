# Chapter 2 — Locked Acceptance after DGC End-to-End

## Status

**LOCKED for Phase 2A/2B.** Chapter 2 is accepted as the baseline implementation for `feature/deep-company-analysis-checklist` after the final DGC live end-to-end diagnostic and regression suite.

The lock means: data model, analyst-controlled guardrails, source-first evidence bridge, unified-page integration and offline persistence are stable enough to continue to Chapter 3. It does **not** mean every Q3–Q6 field must be auto-filled.

## Final acceptance run

GitHub Actions run: `33659544228` — **PASS**.

Acceptance results:

- full deep-analysis suite: **37 passed**;
- Chapter 1 final DGC acceptance: PASS;
- Chapter 2 Phase 2A: PASS;
- Chapter 2 Phase 2B / auto bridge: PASS;
- Chapter 2 source-first evidence tests: PASS;
- live DGC end-to-end diagnostic: PASS;
- unified Deep Analysis page smoke test: PASS;
- legacy Chapter 2 compatibility page smoke test: PASS;
- Windows offline package V11: built and uploaded successfully.

## Final DGC live result

Ticker: `DGC` — CTCP Tập đoàn Hóa chất Đức Giang.

Canonical financial context loaded successfully:

- annual rows: 12;
- quarterly rows: 22;
- TTM rows: 13;
- source-first evidence rows: 62.

Evidence classification from the final live run:

- Q3: 12 candidates;
- Q4: 11 candidates;
- Q5: 34 candidates;
- Q6: 9 candidates.

### Eligible Research Assistant outputs

| Output | Final DGC result |
|---|---|
| Q3 Business Flow | Filled |
| Q4 Money Summary | Filled |
| Q5 Evolution table | Filled |
| Q6 Foreign Strategy Summary | Filled |
| Q6 Foreign Markets table | **Unknown / not filled** |
| Q6 Currency Evidence | **Unknown / not filled** |

Final coverage of eligible auto-fill outputs: **4/6 = 66.7%**.

## Why 66.7% is the correct acceptance result

An earlier diagnostic appeared to reach 83.3%, but it falsely interpreted the word `Đức` in the company name `Đức Giang` as the country Germany. That was an evidence-quality defect, not useful coverage.

The final implementation rejects that false positive. If the collected sources do not provide sufficiently specific country-level operating/export exposure or currency evidence, Chapter 2 leaves those fields **Unknown** rather than fabricating a market, revenue share, FX exposure or hedging conclusion.

For DGC, the final run therefore correctly returns:

- `q6_foreign_markets = []`;
- `q6_currency_evidence = []`.

This is an intentional guardrail and is consistent with the project principle that unanswered questions are research gaps, not permission to infer data.

## Analyst-controlled fields remain locked

Research Assistant must not automatically fill or overwrite:

- Q1 Research Interest / Circle of Competence;
- Q2 CEO Lens;
- Q3 `Own Words`;
- Q5 `Skill vs Luck`;
- analyst Research Gate from Chapter 1.

The final DGC run confirmed all four Chapter 2 auto-fill guardrails were false for automatic overwrite.

## Q4 financial context in the final DGC run

TTM context from the canonical Trecapital bundle used by the diagnostic:

- revenue: approximately 10,097 tỷ đồng;
- revenue growth vs prior annual context: approximately -10.3%;
- gross margin: approximately 25.1%;
- EBIT: approximately 2,651 tỷ đồng;
- EBIT margin: approximately 26.3%;
- CFO: approximately 826 tỷ đồng;
- Capex: approximately -968 tỷ đồng, about 9.6% of revenue;
- FCF: approximately -141 tỷ đồng;
- FCF margin: approximately -1.4%.

These figures provide financial-economics context only. They do not replace analyst work on payer, volume/price drivers, segment economics or business-model understanding.

## Lock decision

Chapter 2 is accepted and locked as the current baseline. Further changes should be bug fixes or cross-chapter integration only; new methodological work proceeds to **Chapter 3 — Understanding the Business from the Customer Perspective**.
