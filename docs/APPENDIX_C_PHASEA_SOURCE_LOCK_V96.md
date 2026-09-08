# Appendix C — Phase A / V96 — Source Lock & Full-Book Checklist Architecture Mapping

## Source

Michael Shearn, *The Investment Checklist*, Appendix C — **Your Investment Checklist**, printed pages 335–338.

Appendix C is the book's consolidated checklist of the 59 research questions developed in the preceding chapters. V96 preserves the printed ordering and the ten section groups without adding questions, weights, scores, recommendations, or unsupported interpretation.

## Source-locked coverage

| Appendix C group | DCA reference range | Count | Owning chapter |
|---|---:|---:|---:|
| Understanding the Business—The Basics | Q01–Q06 | 6 | 2 |
| Understanding the Business—from the Customer Perspective | Q07–Q14 | 8 | 3 |
| Evaluating the Strengths and Weaknesses of a Business and Industry | Q15–Q20 | 6 | 4 |
| Measuring the Operating and Financial Health of the Business | Q21–Q26 | 6 | 5 |
| Evaluating the Distribution of Earnings (Cash Flows) | Q27–Q32 | 6 | 6 |
| Assessing the Quality of Management—Background and Classification: Who Are They? | Q33–Q38 | 6 | 7 |
| Assessing the Quality of Management—Competence: How Management Operates the Business | Q39–Q47 | 9 | 8 |
| Assessing the Quality of Management—Positive and Negative Traits | Q48–Q52 | 5 | 9 |
| Evaluating Growth Opportunities | Q53–Q57 | 5 | 10 |
| Evaluating Mergers & Acquisitions | Q58–Q59 | 2 | 11 |
| **Total** | **Q01–Q59** | **59** | — |

## Architecture decision

Appendix C is implemented as a **referential consolidated checklist contract**. Each row contains only source metadata and a canonical `Qxx` reference to the existing Deep Company Analysis owner. It does **not** copy the owning chapter's answer, evidence, financial data, formulas, confidence, snapshot, research status, valuation state, or analyst conclusion.

This is deliberate SSOT preservation: Chapter 2–11 remain the owners of Q01–Q59 research state. Appendix C is a source-locked index/view layer over those owners.

## AI and analyst boundary

AI remains **Research Assistant** only. It may later help organize or navigate referenced research, but it may not fill missing answers, infer unsupported conclusions, or promote its own output into analyst-owned conclusions. The analyst remains the owner of interpretation and conclusions.

## Explicit non-goals

V96 creates no weighted checklist score, management score, growth score, automatic completeness-to-quality conversion, BUY/HOLD/SELL signal, intrinsic-value calculation, Margin of Safety change, Investment Research Gate change, or duplicate financial/company/question SSOT.

## Formatting contract

When Appendix C is presented in later UI/report phases, existing DCA formatting remains authoritative: retain source order; preserve table headings and question wording; financial values must come from canonical SSOT and use existing number/unit/negative-value presentation rules rather than being reformatted or recalculated inside Appendix C.

## Acceptance contract

V96 is accepted only when deterministic QA confirms:

1. exactly 59 unique questions exist in continuous Q01–Q59 book order;
2. all ten Appendix C sections exist in source order with counts `6, 8, 6, 6, 6, 6, 9, 5, 5, 2`;
3. source anchor wording is preserved;
4. every item references its own existing `Qxx` SSOT owner;
5. no answer/evidence/financial/valuation/scoring/recommendation state is added;
6. full DCA regression and production Streamlit health remain green.
