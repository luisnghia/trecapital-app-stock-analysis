# Chapter 7 — Phase 7A Source Lock

Status: APPROVED by user on 2026-09-05.

## Scope

Chapter 7 is **Assessing the Quality of Management — Background and Classification: Who Are They?** from Michael Shearn, *The Investment Checklist*.

Phase 7A implements only the source-locked analyst workspace for Q33–Q38. It does **not** implement automated web/disclosure research, structured management data ingestion, or final source-closure completion gate; those are reserved for Phase 7B/7C/7D.

## Exact questions

- Q33 — What type of manager is leading the company?
- Q34 — What are the effects on the business of bringing in outside management?
- Q35 — Is the manager a lion or a hyena?
- Q36 — How did the manager rise to lead the business?
- Q37 — How are senior managers compensated, and how did they gain their ownership interest?
- Q38 — Have the managers been buying or selling the stock?

## Source-locked manager continuum

The workspace preserves: **OO1 / OO2 / OO3 / LT1 / LT2 / HH1 / HH2**.

These classes organize background/execution evidence. They are not a numerical quality scale. Founder does not imply OO1. Outside manager does not imply HH2 or a negative conclusion. Suggested classification is never the analyst conclusion.

## Table 7.1 — Lion / Hyena

Phase 7A preserves exactly seven conceptual dimensions:

1. Ethics
2. Time horizon
3. Shortcuts
4. Learning
5. Partnership
6. Employees
7. Persistence

The app stores Lion evidence, Hyena evidence and analyst interpretation for each dimension. There is no Lion score, weighted score or automatic overall classification.

## Q36 career chronology

The workspace supports a top-5 management career timeline with 5–10 years of history where disclosure permits. Functional background, operating/customer/employee exposure, internal/external promotion and known career gaps are stored separately. Unknown career-gap reasons remain Unknown; the app must not infer dismissal, failure or misconduct.

## Q37 compensation and ownership

The workspace separates:

- salary / cash bonus / stock awards / options / restricted stock / ESOP / pension-other / severance;
- actual shares / ownership % / options / RSU-restricted / unvested awards;
- ownership origin such as founder, open-market purchase, grant, option exercise, ESOP, inheritance, other or Unknown.

Actual shares must not be silently combined with options, RSU or ESOP into one ownership number.

## Q38 insider transactions

Insider transactions distinguish open-market buy/sell from option exercise, grant, vesting, ESOP, tax withholding, gift and other transaction types. Insider activity is research evidence only; it never becomes an automatic Buy/Sell Signal. Source-specific heuristics from Shearn remain heuristics, not Trecapital universal thresholds.

## Data-time convention

Chapter 7 data is primarily **event/as-of** data:

- career timeline: event/history dates;
- ownership: as-of date;
- compensation: fiscal/disclosure year;
- insider transactions: transaction/disclosure date;
- management classification: analyst-reviewed as-of evidence.

The app does **not** fabricate TTM rows for these tables. A later rolling 12-month insider summary, if added, must be labelled as a rolling transaction window rather than TTM financial data.

## Analyst boundary

AI/Data may later retrieve, organize, summarize and challenge evidence. It may not:

- set Analyst Classification;
- set Lion/Hyena conclusion;
- infer hidden career-gap causes;
- merge potential equity awards into actual ownership;
- turn insider transactions into BUY/HOLD/SELL;
- change MOS, Research Gate or investment recommendation.

## Phase 7A persistence

Phase 7A stores current record + snapshots and dedicated child tables for management profiles, outside transitions, Lion/Hyena matrix, career timeline, compensation, ownership, compensation design, insider transactions, evidence, research gaps and management events.

## Deferred to later approved phases

- Phase 7B — structured management/disclosure data bridge and Vietnam source mapping.
- Phase 7C — evidence/research assistant, counter-evidence and management-event detection.
- Phase 7D — final source closure, review-on-change logic and Chapter 7 completion gate.
