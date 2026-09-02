# Chapter 3 Phase 3B — Customer Perspective Evidence Bridge

## Source basis

Primary methodology: Michael Shearn, *The Investment Checklist*, Chapter 3 — **Understanding the Business—from the Customer Perspective**.

The source frames the customer as the stakeholder who ultimately determines the fate of a business and warns investors not to substitute their own product preferences for the customer's perspective. Shearn recommends understanding why real customers buy and whether they will continue to buy.

Phase 3B therefore automates **evidence collection**, not analyst judgement.

## Research Assistant principle

> AI/Data = Research Assistant; user = Investment Analyst.

Research Assistant may:

- find official/company/customer-related evidence;
- classify evidence into Q7–Q14 research buckets;
- draft summaries into blank workspace fields;
- extract an explicit retention/churn percentage when a reliable source states the metric;
- extract an explicit customer revenue-share candidate when a reliable source states the percentage;
- show links/snippets for analyst verification;
- preserve evidence cache for offline review.

Research Assistant must not automatically decide:

- Q8 Concentrated / Diversified;
- Q9 Easy / Moderate / Hard sales friction;
- Q13 Need-to-have continuum classification;
- Q14 disappearance impact level;
- Q14 final disappearance conclusion;
- investment rating or Chapter 1 Research Gate.

## Q7 — Core Customer evidence

Searches official/company and web sources for:

- customers/clients;
- user/buyer/purchaser language;
- B2B/B2C descriptions;
- explicit customer segments.

The assistant can draft `core_customer_summary` from evidence, but it does not invent payer/user separation or revenue/profit relevance when the source does not state them.

## Q8 — Customer concentration

The source explains that a concentrated customer base creates pricing and loss-of-customer risk, and that the analyst should watch trends in concentration.

Automation guardrails:

- no inference from geographic or segment revenue;
- no concentration status auto-classification;
- a candidate customer share requires an **explicit percentage** in a trusted/relevant source;
- if a percentage is found but the customer name cannot safely be parsed, the table explicitly says analyst must identify the customer from the original source;
- vague statements such as “many customers” do not become a quantitative concentration table.

## Q9 — Sales friction

Evidence search covers:

- sales force / sales process;
- distribution/dealer/channel;
- tender/bid/contract/order process;
- demo/trial/promotion.

The source warns about businesses dependent on high-pressure sales tactics. The assistant may surface evidence but does not classify sales as Easy/Moderate/Hard.

## Q10 — Retention

Shearn treats retention as a key customer-longevity metric and notes it is directly trackable only for certain business models. Loyalty programs may serve as indicators/proxies.

Automation therefore distinguishes:

- explicit retention rate;
- explicit churn rate;
- explicit renewal rate;
- general loyalty/repeat-customer evidence.

A retention/churn percentage is auto-extracted only when:

1. the text explicitly contains the metric label and a percentage; and
2. the evidence comes from a trusted company/official disclosure family or has high relevance.

Revenue growth, recurring revenue, repeat orders or membership counts are **not converted into a retention rate**.

## Q11 — Customer orientation

Evidence search covers:

- customer satisfaction;
- feedback and complaint mechanisms;
- NPS/CSAT when explicitly reported;
- customer service/support;
- surveys;
- customer-experience/customer-centric operating practices.

The assistant surfaces evidence; analyst determines whether it reflects real operating behavior or marketing language.

## Q12 — Customer pain / need

Evidence search covers:

- customer needs/problems;
- use cases/application;
- solution/value delivered;
- compliance/quality requirements;
- consequences avoided/reduced.

The assistant may draft a `pain_summary`; analyst should translate it into the actual customer job-to-be-done and test it against customer-side evidence.

## Q13 — Customer dependency

The source continuum is preserved:

- Need to have;
- Need to have, but not immediately;
- Nice to have, but not critical.

Evidence search surfaces references to necessity, criticality, alternatives, substitutes and switching. The assistant can place supporting evidence into `dependency_reason`, but it **never selects the continuum classification**.

## Q14 — Disappearance test

Searches for:

- substitutes/alternatives;
- replacement/qualified suppliers;
- switching burden;
- supply shortage/disruption;
- single-source dependencies.

The assistant may fill the evidence field only. `Impact level` and `disappearance_conclusion` remain analyst-controlled.

## Evidence architecture

Files:

- `modules/deep_company_analysis/chapter3_auto.py` — customer evidence agent, classification, extraction and no-overwrite merge;
- `modules/deep_company_analysis/chapter3_page_support.py` — Research Assistant UI/persistence bridge;
- `modules/deep_company_analysis/test_chapter3_auto.py` — evidence and guardrail regression tests;
- `tools/dgc_chapter3_e2e.py` — live DGC diagnostic.

Dedicated evidence cache:

`raw_data/chapter3_customer_evidence/<TICKER>/evidence_<timestamp>.json`

This keeps the final Chapter 3 evidence bundle reloadable for offline review. Search-source working files may still be produced by the reused Trecapital evidence infrastructure.

## UI

Chapter 3 remains the third tab of the single **Phân tích chuyên sâu doanh nghiệp** page and is now rendered through `render_chapter3_tab()` so the Research Assistant panel and analyst workspace share the same tab/ticker context.

Research Assistant panel adds:

- `🔄 Cập nhật Customer Evidence`;
- evidence counts Q7–Q14;
- explicit retention/concentration candidate notices;
- expandable evidence table with source URLs;
- `🧩 Điền các ô trống bằng Customer Evidence Draft`.

Applying the draft:

- fills blank evidence/research fields only;
- never overwrites saved analyst text;
- never auto-classifies Q8/Q9/Q13/Q14 analyst judgement fields.

The integration commit is `09d8602e188b737b60214e7153ed21c61fb241a9` on `feature/deep-company-analysis-checklist`.

## CI / offline package

The main Deep Company Analysis CI now explicitly runs:

- Chapter 3 Phase 3A tests;
- Chapter 3 Phase 3B evidence/guardrail tests;
- live DGC Chapter 2 diagnostic;
- live DGC Chapter 3 diagnostic;
- unified-page smoke test.

The corresponding Windows package target is **Trecapital_Deep_Analysis_Offline_V13** and includes Chapter 3 assistant/support code plus the Phase 3B context document.

## Phase 3B acceptance criteria

- source questions Q7–Q14 remain intact;
- evidence has source URL/title/snippet;
- evidence cache can be reloaded offline;
- explicit retention extraction passes a reliable-source gate;
- generic search snippets cannot fabricate retention;
- customer concentration requires explicit percentage evidence;
- Q8/Q9/Q13/Q14 analyst classifications are unchanged after Apply Draft;
- Q14 analyst conclusion is unchanged after Apply Draft;
- existing Chapter 1–3 regressions remain green;
- live DGC diagnostic reports evidence coverage and guardrails without modifying analyst records.
