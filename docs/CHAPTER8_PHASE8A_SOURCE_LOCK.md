# Chapter 8 — Phase 8A Source Lock

Status: APPROVED by user on 2026-09-06.

## Scope

Chapter 8 is **Assessing the Quality of Management—Competence: How Management Operates the Business** from Michael Shearn, *The Investment Checklist*.

Chapter 7 asks who the managers are. Chapter 8 asks how senior management actually operates the business: daily operations versus long-term strategy, stakeholder orientation, employees and hiring, cost discipline, capital allocation and share repurchases.

Phase 8A implements only the source-locked analyst-workspace contract for Q39–Q47. It does **not** yet implement automated disclosure research, canonical numeric ingestion, final evidence closure, or a Chapter 8 completion gate. Those are deferred to later phases.

## Exact questions

- Q39 — Does the CEO manage the business to benefit all stakeholders?
- Q40 — Does the management team improve its operations day-to-day or does it use a strategic plan to conduct its business?
- Q41 — Do the CEO and CFO issue guidance regarding earnings?
- Q42 — Is the business managed in a centralized or decentralized way?
- Q43 — Does management value its employees?
- Q44 — Does the management team know how to hire well?
- Q45 — Does the management team focus on cutting unnecessary costs?
- Q46 — Are the CEO and CFO disciplined in making capital allocation decisions?
- Q47 — Do the CEO and CFO buy back stock opportunistically?

## Q39 — Stakeholder orientation

Shearn's framing is not a mechanical ESG score. The research question is whether management operates for the durable benefit of customers, employees, suppliers, shareholders, business partners and other relevant stakeholders rather than optimizing one constituency at the expense of the enterprise.

The app stores evidence and counter-evidence by stakeholder group. Evidence that management benefits one group must not be generalized into an automatic overall conclusion. Analyst assessment remains manual.

## Q40 — Continuous improvement versus strategic-plan dependence

The source warns against assuming that a charismatic CEO, a single transformational act or a rigid multi-year strategic plan is what creates a great business. The workspace therefore separates:

- continuous day-to-day improvement;
- many small operating decisions;
- frontline/customer feedback;
- adaptation as facts change;
- evidence of rigid strategic-plan dependence or transformational bets.

Having a strategic plan is not automatically negative. The app is to document how the business is actually operated, not label the existence of planning as a defect.

## Q41 — Earnings guidance

Guidance is stored as an event/history series with issued date, metric, horizon, target range/point, revision or withdrawal, actual result and outcome when comparable data exists.

The source specifically recommends comparing management guidance with actual results and examining repeated beat/meet behavior. Such patterns are **research warnings only**. The app must not infer earnings manipulation or fraud merely because management repeatedly beats its own guidance.

No fake TTM rows are created for guidance history.

## Q42 — Centralized versus decentralized management

The source distinguishes top-down centralized structures from decentralized structures where decision rights sit closer to the customer. The app records decision owner, autonomy, escalation/control and customer-proximity evidence.

Centralized and decentralized are structural descriptions, not universal quality scores. The analyst decides whether the structure fits the business.

## Q43 — Employee relations: exact source-locked evidence prompts

Phase 8A preserves the fourteen checks listed in Chapter 8:

1. Does management treat its employees as assets or liabilities?
2. Does management talk about the contributions of their employees?
3. Does management believe that retaining employees is critical?
4. Does the business promote from within?
5. Does management show employees how they can get promoted?
6. Does the business invest significant resources in employee training?
7. Does the business attract a great number of applicants?
8. Are employees avidly recruited from the business?
9. Are there large differences between the benefits that the top managers receive versus employees?
10. Does management treat employees with respect when they lay them off?
11. Does management listen to its employees?
12. Does the business have a strong culture?
13. Does the business have identifiable, shared values?
14. What is the employee-retention rate?

These are evidence prompts, not fourteen points in a score. Absence of disclosure is Unknown, not a negative conclusion. Employee-retention metrics must carry a period/as-of date and source.

## Q44 — Hiring and people decisions

The source treats hiring and promotion as core management decisions. Research should therefore capture the history and outcome of key hires/promotions, whether positions are filled internally or externally, whether management attracts candid/challenging people, succession depth, and board/governance relevance where supported by evidence.

Prestigious résumés, famous employers or outside hires do not by themselves establish hiring competence. Chapter 8 reuses Chapter 7 manager identities rather than maintaining a second manager master.

## Q45 — Cutting unnecessary costs

Cost discipline is not the same as indiscriminate frugality. The source distinguishes:

- removing waste, inefficiency and non-core costs while preserving/reinvesting in what benefits customers and the core business; from
- underinvesting in customers, employees, training, innovation or other capabilities needed by the business.

Repeated restructuring and recurring “one-time” cost programs are stored as evidence to investigate. A cost reduction is never automatically scored positive.

## Q46 — Capital allocation discipline

Shearn defines capital allocation here as the use of excess free cash flow and enumerates five actions:

1. Reinvest capital in the business / new projects.
2. Hold cash on the balance sheet.
3. Pay dividends.
4. Buy back stock.
5. Make acquisitions.

Phase 8A preserves exactly those five source-locked actions. Debt paydown may later be represented as a clearly labelled Trecapital extension if needed for modern company analysis; it is not silently inserted into Shearn's original five-item list.

The key evidence is the historical record of decisions and discipline, not an automatically computed management score. Operating competence and capital-allocation competence are kept conceptually separate.

## Q47 — Opportunistic share repurchases

The source requires evaluating repurchases in the context of value, liquidity/cash needs and dilution. The workspace therefore separates:

- authorization and actual repurchase execution;
- shares and cash spent;
- average price and share-count change;
- management's stated reason;
- whether repurchases offset option/equity dilution;
- valuation context;
- liquidity/cash context.

A buyback is not automatically value creating. Chapter 8 must not declare stock undervalued from market price alone. Any later valuation context must come from analyst-approved/Trecapital canonical valuation logic, not from a Chapter 8 evidence agent inventing intrinsic value.

## Data and time convention

Chapter 8 mixes qualitative/as-of evidence with dated management decisions:

- stakeholder/organization/culture: evidence date or as-of date;
- guidance: issue/revision/withdrawal date plus forecast horizon and actual period;
- hiring/cost/capital-allocation/buyback decisions: event or period date;
- employee metrics: explicit measurement period/as-of date.

The app does not fabricate TTM rows for qualitative/event tables. Later financial values must come from the Trecapital canonical dataset and retain source field, source module, source period and data origin where applicable.

## Analyst boundary

AI/Data may retrieve, organize, summarize, compare and surface counter-evidence. It may not:

- assign a management-competence score;
- turn centralized/decentralized structure into an automatic quality grade;
- infer poor culture from missing employee disclosures;
- infer fraud from earnings-guidance patterns;
- treat every cost cut as positive;
- declare a capital-allocation decision good solely because investment/growth occurred;
- declare a buyback accretive or opportunistic without explicit valuation and liquidity evidence;
- change BUY/HOLD/SELL, MOS, Research Gate or the investment recommendation;
- overwrite analyst assessment.

## Phase 8A implementation contract

Phase 8A provides:

- exact Q39–Q47 question keys and titles;
- source-locked Q43 fourteen-dimension employee matrix;
- source-locked Q46 five capital-allocation actions;
- evidence table schemas for Q39–Q47;
- Unknown-first analyst assessment, confidence and question status;
- evidence-completeness warnings that do not judge management quality.

## Deferred phases

- Phase 8B — structured data bridge: reuse Chapter 7 manager identity plus Trecapital canonical data for Q41/Q45/Q46/Q47 where financial values are needed.
- Phase 8C — evidence/research assistant, source grading, counter-evidence, human-intelligence/lower-grade source handling and management-event detection.
- Phase 8D — DGC live acceptance, source closure, review-on-change logic and Chapter 8 completion gate.
