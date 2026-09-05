# Deep Company Analysis — Chapter 7 Methodology

Status: APPROVED SOURCE LOCK + Phase 7A implementation target.

## Purpose

Chapter 7 answers **Who are they?** for senior management. It is a background/classification research workspace, not a management-quality scoring model.

## Q33 manager classification

Source-locked options: OO1, OO2, OO3, LT1, LT2, HH1, HH2, plus Unknown/Mixed for analyst workflow.

No deterministic mapping is allowed. In particular:

- Founder does not automatically imply OO1.
- Internal promotion does not automatically imply LT1 without evidence.
- Outside appointment does not automatically imply HH1/HH2 or a negative conclusion.
- Suggested Classification is research support only; Analyst Classification is authoritative.

## Q34 outside management

The workspace captures internal/external origin, industry/customer overlap, organization-specific knowledge, support-network transferability, time to first major action, consultation/learning evidence, cost-cutting/growth actions, executive departures and early outcomes.

No historical statistic from Shearn is converted into a present-day probability-of-failure model.

## Q35 Lion / Hyena — Table 7.1

Exactly seven source-locked dimensions are preserved: Ethics, Time horizon, Shortcuts, Learning, Partnership, Employees and Persistence.

Evidence is stored on both Lion and Hyena sides. There is no score, weight or automatic overall classification.

## Q36 career chronology

Top-5 management chronology supports 5–10 years where disclosure permits. Functional background and customer/operating/employee/corporate-suite exposure are stored separately. Career gaps remain Unknown unless the source explicitly explains them.

## Q37 compensation and ownership

Compensation components and ownership forms remain separate. Actual shares/ownership are not silently combined with options, RSU/restricted awards, unvested awards or ESOP benefits.

ESOP is a Vietnam-market implementation extension, not a verbatim Shearn category.

## Q38 insider transactions

Transaction type distinguishes open-market buy/sell from option exercise, grant, vesting, ESOP, tax withholding, gift and other events. Insider activity is evidence only, never an automatic Buy/Sell Signal.

## Time convention

Chapter 7 is primarily event/as-of data. Therefore:

- no fabricated TTM for career history;
- no fabricated TTM ownership;
- no fabricated TTM manager classification;
- no fabricated TTM insider transaction row;
- compensation uses fiscal/disclosure year;
- a later rolling 12-month insider summary must be labelled Rolling 12M, not TTM financial data.

## Formatting

Phase 7A inherits the shared Deep Analysis table contract:

- VND amounts: tỷ đồng, 0 decimals;
- percentages/ratios/tenure: 1 decimal where numeric;
- read-only tables: shared `render_static_table` / `st.html` path;
- editable tables: shared sortable data editor;
- all production tables expose explicit sorting controls;
- long text wraps and static tables use fixed layout.

## Analyst boundary

Phase 7A does not implement automated research. Later AI/data layers may retrieve and organize evidence, but they may not alter Analyst Classification, Lion/Hyena conclusion, MOS, Research Gate or BUY/HOLD/SELL.

## Deferred phases

- Phase 7B: structured management data/disclosure bridge.
- Phase 7C: evidence/counter-evidence research assistant and management-event detection.
- Phase 7D: final source closure, change-review logic and Chapter 7 completion gate.
