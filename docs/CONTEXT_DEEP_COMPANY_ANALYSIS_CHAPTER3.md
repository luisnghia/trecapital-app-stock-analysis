# Context — Deep Company Analysis Chapter 3

## Source

Primary methodology: Michael Shearn, *The Investment Checklist: The Art of In-Depth Research*, Chapter 3 — **Understanding the Business—from the Customer Perspective**.

Chapter 3 contains questions 7–14:

7. Who is the core customer of the business?
8. Is the customer base concentrated or diversified?
9. Is it easy or difficult to convince customers to buy the products or services?
10. What is the customer retention rate for the business?
11. What are the signs a business is customer oriented?
12. What pain does the business alleviate for the customer?
13. To what degree is the customer dependent on the products or services from the business?
14. If the business disappeared tomorrow, what impact would this have on the customer base?

## Methodological framing

The chapter changes the analyst's viewpoint from company/product-centered research to **customer-centered research**.

Core principles preserved in the app:

- the quality of a business is strongly connected to the quality and behavior of its customers;
- personal liking or disliking of a product must not substitute for customer evidence;
- the analyst should understand why customers buy, whether they are likely to continue buying and how difficult replacement would be;
- diversified customer bases generally create less single-customer risk than concentrated bases;
- customer retention is useful when the business model makes it measurable, but it cannot be fabricated for business models that do not disclose or naturally report it;
- loyalty-program data, recurring revenue or repeat purchases can be useful evidence/proxies, but are not automatically equal to a disclosed retention rate;
- customer orientation should be evaluated through actual management behavior, customer feedback systems, field/customer research and independent indicators rather than marketing language alone;
- customer dependency should be assessed on Shearn's continuum: `Need to have` → `Need to have, but not immediately` → `Nice to have, but not critical`;
- a practical dependency test is to ask what customers would do if the business disappeared tomorrow and how easy substitution would be.

## Phase 3A architecture

Phase 3A is an **analyst workspace + persistence layer**. It deliberately does not yet automate answers from the web.

File:

- `modules/deep_company_analysis/chapter3.py`

Local SQLite:

- `data_cache/deep_company_analysis_chapter3.db`

Tables:

- `chapter3_current`: one current record per ticker;
- `chapter3_snapshots`: append-only snapshots on every save.

The status engine uses only:

- `Answered`;
- `Partial`;
- `Unknown`.

These statuses measure **research completeness**, not business quality and not investment attractiveness.

## Q7 — Core Customer

App fields:

- Customer Segment;
- Customer type;
- Who pays?;
- Who uses?;
- Main need / job-to-be-done;
- Purchase criteria;
- Price sensitivity;
- Revenue / profit relevance;
- Evidence;
- Core customer summary;
- Why core.

Guardrails:

- payer and user must be separated where relevant;
- no revenue/profit relevance may be invented when not disclosed;
- customer persona must be evidence-grounded rather than inferred from analyst preference.

## Q8 — Customer Concentration

App fields:

- concentration status: `Unknown`, `Diversified`, `Moderately concentrated`, `Concentrated`;
- customer/group table;
- revenue share if disclosed;
- period/trend;
- bargaining power;
- dependency/loss impact;
- evidence;
- concentration conclusion.

Guardrails:

- `Unknown` is valid when customer disclosure is absent;
- segment revenue/geographic revenue cannot be re-labeled as customer concentration;
- concentration trend should be tracked where historical disclosure exists;
- Shearn's US 10-K discussion of large-customer disclosure is methodology context, not a Vietnam legal disclosure rule.

## Q9 — Ease/Difficulty of Selling

App fields:

- sales friction: `Unknown`, `Easy`, `Moderate`, `Hard`;
- sales motion;
- sales cycle/decision process;
- demo/trial/education requirement;
- high-pressure selling/promotion dependency;
- conclusion and evidence.

Methodology emphasis: reliance on aggressive/high-pressure selling can be a warning that demand is being created by sales tactics rather than product/service merit.

## Q10 — Customer Retention

App explicitly separates evidence availability from the retention number.

`Retention evidence status`:

- Unknown;
- Disclosed metric;
- Proxy only;
- Not disclosed;
- Not meaningful for this business model.

Other fields:

- business model;
- retention rate + period if actually disclosed;
- churn rate if disclosed;
- loyalty/repeat-customer proxy;
- retention investments;
- renewal/sales incentives;
- trend;
- evidence;
- analyst conclusion.

Critical guardrail: **revenue growth, recurring revenue or loyalty membership must never be converted into a fabricated retention rate.**

## Q11 — Customer Orientation

App fields:

- feedback mechanisms;
- satisfaction metrics;
- management proximity to customers;
- field immersion/customer research;
- customer metrics used to manage operations;
- independent indicators;
- evidence;
- customer-orientation conclusion.

The analyst should distinguish repeatable operating behavior from customer-centric marketing claims.

## Q12 — Customer Pain / Need

Pain map fields:

- Customer Segment;
- Pain / Need;
- Consequence if unsolved;
- Solution / Value delivered;
- Alternative workaround;
- Evidence.

This section asks what actual problem or need causes the customer to pay the business.

## Q13 — Customer Dependency

The UI uses the source continuum exactly:

- Unknown;
- Need to have;
- Need to have, but not immediately;
- Nice to have, but not critical.

Other fields:

- reason for classification;
- how long purchase/use can be deferred;
- consequence if stopped;
- substitutes/workarounds;
- evidence.

Guardrail: a discretionary product is not automatically a bad business; customer composition and actual behavior still require evidence.

## Q14 — Disappearance Test

Fields:

- customer disruption: Unknown / Low / Moderate / High / Severe;
- immediate substitute;
- switching time;
- switching cost / implementation burden;
- operational disruption;
- conclusion;
- evidence.

The purpose is to make replaceability and customer dependency concrete. Brand loyalty alone is not sufficient evidence that alternatives are unavailable.

## Research Assistant policy for future Phase 3B

Phase 3B may collect and draft evidence, but must follow the existing project rule:

> AI/Data = Research Assistant; user = Investment Analyst.

Permitted future automation:

- extract named/explicit major-customer disclosure;
- extract retention/churn only when source explicitly states the metric and period;
- collect customer satisfaction/complaint/service indicators;
- collect official descriptions of customer segments, distribution/channel and customer requirements;
- find customer-side evidence and independent studies;
- propose research gaps.

Forbidden automatic behavior:

- infer retention from revenue growth;
- infer concentration from segment/geographic revenue;
- invent customer names or shares;
- infer NPS/CSAT without source;
- automatically classify customer dependency or disappearance impact as an analyst conclusion;
- produce BUY/HOLD/SELL;
- modify Chapter 1 Research Gate.

## Phase 3A acceptance criteria

- one current record per ticker;
- append-only snapshot on every save;
- Q7–Q14 preserved in the data model;
- `Unknown` remains first-class and does not reduce data integrity;
- proxy retention cannot become a disclosed retention metric;
- concentration table without an explicit supported assessment remains Partial;
- overall customer perspective cannot become `understood` unless core-customer understanding (Q7) and customer pain understanding (Q12) are both Answered;
- unified Deep Analysis page remains the single primary workspace;
- offline operation requires no external API.

## Unified page integration

Chapter 3 Phase 3A is rendered as the third tab of `pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py`:

- `📗 Chương 1 — Cơ hội đầu tư`
- `📘 Chương 2 — Hiểu doanh nghiệp`
- `📙 Chương 3 — Góc nhìn khách hàng`

The ticker is shared/fallback-compatible across the three tabs. Chapter 3 remains a single-page tab rather than a new sidebar page.
