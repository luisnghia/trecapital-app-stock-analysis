# Context — Deep Company Analysis Chapter 3 — APPROVED

## Approval status

**Approved by user on 2026-09-03.** This document is the source-of-truth design context for Chapter 3 of the Trecapital **Phân tích chuyên sâu doanh nghiệp** workspace.

Primary methodology: Michael Shearn, *The Investment Checklist: The Art of In-Depth Research*, Chapter 3 — **Understanding the Business—from the Customer Perspective**.

Project rule:

> **AI/Data = Research Assistant; user = Investment Analyst.**

Chapter 3 measures customer understanding and evidence completeness. It does **not** produce a Customer Score, BUY/HOLD/SELL or automatically modify the Chapter 1 Research Gate.

---

## 1. Chapter objective

Chapter 2 asks what the business does and how it makes money. Chapter 3 changes the viewpoint to the customer:

> Why do real customers buy, why do they continue buying, and how dependent are they on the product/service?

The analyst must not substitute personal product preference for actual customer evidence. `Unknown` is a valid result when evidence is insufficient.

---

## 2. Source questions Q7–Q14

7. **Who is the core customer of the business?** — Khách hàng cốt lõi của doanh nghiệp là ai?
8. **Is the customer base concentrated or diversified?** — Cơ sở khách hàng tập trung hay đa dạng?
9. **Is it easy or difficult to convince customers to buy the products or services?** — Dễ hay khó thuyết phục khách hàng mua?
10. **What is the customer retention rate for the business?** — Tỷ lệ giữ chân khách hàng là bao nhiêu?
11. **What are the signs a business is customer oriented?** — Dấu hiệu nào cho thấy doanh nghiệp định hướng khách hàng?
12. **What pain does the business alleviate for the customer?** — Doanh nghiệp giải quyết vấn đề/nỗi đau nào của khách hàng?
13. **To what degree is the customer dependent on the products or services from the business?** — Khách hàng phụ thuộc vào sản phẩm/dịch vụ đến mức nào?
14. **If the business disappeared tomorrow, what impact would this have on the customer base?** — Nếu doanh nghiệp biến mất ngày mai, khách hàng sẽ bị ảnh hưởng thế nào?

---

## 3. Chapter flow

```text
CUSTOMER EVIDENCE
      ↓
Q7  Core Customer
      ↓
Q8  Concentration
      ↓
Q9  Sales Friction
      ↓
Q10 Retention
      ↓
Q11 Customer Orientation
      ↓
Q12 Customer Pain
      ↓
Q13 Customer Dependency
      ↓
Q14 Disappearance Test
      ↓
Customer Perspective Summary
      ↓
Research Gaps / Questions to Verify
```

No automatic investment conclusion is generated.

---

## 4. Evidence architecture — three layers

### Layer A — Company Disclosure

- Annual reports / BCTN;
- financial statements / BCTC and notes;
- investor relations;
- company presentations;
- official website and product/service documents.

### Layer B — Independent / Customer-side

- customer-side material;
- industry publications;
- independent surveys;
- customer case studies;
- credible third-party evidence.

### Layer C — Analyst Fieldwork

- direct customer interviews;
- distributor/channel interviews;
- store/field visits;
- supplier or sales conversations;
- analyst observations.

Each material claim should be recordable as:

`Claim → Q → Layer → Source → Source date → Evidence text → Status → Analyst note`

Recommended evidence statuses:

- `Verified`;
- `Unverified`;
- `Conflicting`.

If evidence conflicts, the app must preserve both sides and show a warning. It must not automatically choose a side.

---

## 5. Q7 — Core Customer

### Approved Core Customer Map fields

- Customer Segment;
- Customer type;
- Buyer / Decision maker;
- Who pays?;
- Who uses?;
- Why they buy;
- Main need / job-to-be-done;
- Purchase criteria;
- Price sensitivity;
- **Revenue Relevance**;
- **Profit Relevance**;
- Evidence.

### Revenue Relevance — approved additional field

Purpose: record how economically important a customer/customer group is to revenue **only when evidence supports it**.

Examples of valid content:

- explicit customer-group revenue share;
- explicit major-customer revenue percentage;
- disclosed revenue attributable to a defined customer group.

Rules:

- optional field;
- blank/Unknown is valid;
- do not infer from geographic revenue;
- do not relabel business segment revenue as customer revenue unless the segment truly maps to the customer group and the disclosure supports that mapping;
- do not estimate a number merely to complete the table.

### Profit Relevance — approved additional field

Purpose: record profit contribution, margin economics or profitability relevance of the customer/customer group **only when disclosure/evidence exists**.

Rules:

- optional field;
- blank/Unknown is the normal outcome when profitability by customer is not disclosed;
- never infer profit contribution from revenue share alone;
- never assume export/customer segment profitability without source evidence;
- qualitative evidence is allowed if clearly labeled as qualitative rather than a calculated percentage.

These are **Trecapital implementation fields**, not named scoring fields from Shearn. They exist to distinguish customer count/revenue importance from actual economic importance.

### Q7 analyst conclusions

- Core customer summary;
- Why this is the core customer rather than merely one customer segment.

Research Assistant may surface evidence but does not decide the core customer.

---

## 6. Q8 — Customer Concentration

Fields:

- Customer / Group;
- Revenue share % if explicitly disclosed;
- Period;
- Trend;
- Bargaining power;
- Dependency / loss impact;
- Evidence;
- analyst concentration assessment: `Unknown / Diversified / Moderately concentrated / Concentrated`;
- concentration trend and conclusion.

Guardrails:

- no concentration inference from geographic/segment revenue;
- no automatic concentration classification;
- Shearn's US 10-K 10% discussion is methodology context, **not a Vietnam disclosure rule**;
- historical trend should be tracked when available.

---

## 7. Q9 — Sales Friction

Fields:

- Sales motion: direct / distributor / dealer / tender / online / contract / subscription / other;
- sales cycle / decision process;
- trial/demo/education/qualification requirement;
- high-pressure selling / promotion dependency;
- discount dependency;
- customer pull — whether customers proactively seek the product;
- repeat-purchase friction vs new-customer sale;
- evidence;
- analyst assessment: `Unknown / Easy / Moderate / Hard`;
- analyst conclusion: demand from product merit/need vs sales effort.

Research Assistant may surface evidence but never chooses Easy/Moderate/Hard.

---

## 8. Q10 — Customer Retention

Retention evidence status:

- Unknown;
- Disclosed metric;
- Proxy only;
- Not disclosed;
- Not meaningful for this business model.

Fields:

- business model;
- retention rate + period if explicitly disclosed;
- churn rate if explicitly disclosed;
- loyalty/repeat-customer proxy clearly labeled as proxy;
- retention investments;
- renewal/sales incentives;
- customer success/service;
- cross-sell/upsell within existing customers;
- customer-selection quality;
- retention trend;
- evidence;
- analyst conclusion.

Critical guardrail:

> Revenue growth, recurring revenue, repeat orders or loyalty membership must never be converted into a fabricated retention rate.

---

## 9. Q11 — Customer Orientation

Evidence buckets:

1. **Customer Satisfaction** — NPS/CSAT/independent ratings/complaints when explicitly available;
2. **Service Quality** — service/support quality and knowledgeable staff;
3. **Fair Treatment** — pricing/refund/fee/customer-friendly policies and whether the business avoids exploiting customers;
4. **Management Proximity** — management/CEO contact with customers and use of customer feedback;
5. **Customer Immersion** — field observation, store visits, user observation, direct customer research.

Additional fields:

- customer metrics used to manage operations;
- independent indicators;
- evidence;
- analyst conclusion: operating behavior vs marketing language.

---

## 10. Q12 — Customer Pain / Need

Pain Map fields:

- Customer Segment;
- Pain / Need;
- Consequence if unsolved;
- Solution / Value delivered;
- Alternative workaround;
- Evidence.

Pain must be written from the customer's viewpoint, not merely as a description of what the company manufactures.

---

## 11. Q13 — Customer Dependency

Shearn continuum is preserved exactly:

- `Need to have`;
- `Need to have, but not immediately`;
- `Nice to have, but not critical`;
- `Unknown`.

Dependency should first be assessed **by customer/product**, then summarized for the business.

Dependency table:

- Customer Segment;
- Product / Service;
- Dependency Class;
- Can defer?;
- How long?;
- Alternatives / Substitutes;
- Consequence if stopped;
- Evidence.

Aggregate analyst fields remain for overall conclusion/reason, deferral period, consequence, substitutes and evidence.

AI must never choose the dependency classification.

---

## 12. Q14 — Disappearance Test

Customer-segment table:

- Customer Segment;
- Immediate Alternative;
- Time to Replace;
- Switching Cost;
- Operational Disruption;
- Customer Evidence.

Aggregate analyst fields:

- customer disruption: `Unknown / Low / Moderate / High / Severe`;
- immediate substitute;
- switching time;
- switching cost / implementation burden;
- operational disruption;
- disappearance conclusion;
- evidence.

Research Assistant may find replacement/switching evidence. It must never choose impact level or write the final disappearance conclusion.

---

## 13. Customer / Channel Interview Log

Shearn's customer perspective requires more than web research. The approved app therefore includes a Layer C fieldwork log:

- Date;
- Company / Person;
- Role;
- Customer Segment;
- Q Covered;
- Key Insight;
- Confidence;
- Evidence / Note.

Suggested interview questions:

- Why did you choose this product/service?
- What alternatives exist?
- What would make you change supplier?
- What happens if price increases?
- If this business disappeared tomorrow, what would you do?

Research Assistant must never fabricate interview content.

---

## 14. Customer Perspective Summary

Final Chapter 3 workspace includes:

- Customer Strengths;
- Customer Risks;
- Most Important Customer Evidence (target 3–5 key items);
- Critical Research Gaps;
- overall analyst narrative / Customer Perspective Summary.

Question completion is shown as `Answered / Partial / Unknown` for Q7–Q14.

Overall completeness label:

- 🟢 Customer Perspective Understood;
- 🟡 Customer Perspective Partial;
- 🔴 Customer Perspective Not Yet Understood.

This is **research completeness only**, not a quality score or investment rating.

---

## 15. Research Assistant permissions and prohibitions

### Permitted

- find customer evidence;
- classify evidence into Q7–Q14;
- extract explicitly disclosed customer concentration percentages;
- extract explicitly disclosed retention/churn/renewal percentages;
- find customer satisfaction/service evidence;
- find substitutes/replacement evidence;
- summarize source material into blank research fields;
- propose research gaps;
- preserve provenance and cache evidence for offline review.

### Forbidden

- invent customer names or shares;
- infer concentration from geography/segments;
- infer retention from revenue or recurring revenue;
- invent NPS/CSAT;
- infer Revenue Relevance or Profit Relevance without evidence;
- automatically classify Q8 concentration;
- automatically classify Q9 sales ease;
- automatically classify Q13 dependency;
- automatically classify Q14 impact;
- overwrite analyst content;
- change Chapter 1 Research Gate;
- output BUY/HOLD/SELL.

---

## 16. Persistence

SQLite:

`data_cache/deep_company_analysis_chapter3.db`

Tables:

- `chapter3_current` — one current record per ticker;
- `chapter3_snapshots` — append-only snapshot history.

The JSON payload stores Q7–Q14, interview log, evidence matrix, summary fields and Research Assistant provenance. Existing prototype records are loaded backward-compatibly.

---

## 17. Unified page integration

Chapter 3 is the third tab of the single page:

`Phân tích chuyên sâu doanh nghiệp`

Tabs:

1. 📗 Chương 1 — Cơ hội đầu tư
2. 📘 Chương 2 — Hiểu doanh nghiệp
3. 📙 Chương 3 — Góc nhìn khách hàng

The ticker context is shared across the workspace.

---

## 18. Delivery phases — approved

### Phase 3A — Source-locked Core

Schema + Q7–Q14 + tables + current/snapshot persistence + unified tab. No automatic analyst conclusions.

### Phase 3B — Evidence Bridge

BCTN/BCTC/IR + independent/customer-side evidence, provenance and no-overwrite Research Assistant draft.

### Phase 3C — Human / Customer Intelligence

Customer/channel interview log + three-layer evidence model + Evidence Matrix + conflicting-evidence warning + research gaps.

### Phase 3D — DGC Acceptance

Run DGC end-to-end, inspect Q7–Q14 evidence, ensure no fabricated customer/retention/concentration/relevance, run regression and UI smoke tests, then lock Chapter 3.

---

## 19. Acceptance criteria before Chapter 3 lock

- Q7–Q14 remain source-faithful;
- Revenue Relevance and Profit Relevance are separate optional fields;
- no revenue/profit relevance is invented;
- core-customer buyer/payer/user are distinguishable;
- Q8 concentration requires explicit evidence and analyst classification;
- Q10 retention cannot be fabricated from proxies;
- Q13 dependency has customer/product-level analysis and analyst-controlled classification;
- Q14 has customer-segment disappearance analysis and analyst-controlled impact/conclusion;
- interview log is manual Layer C evidence only;
- Evidence Matrix supports A/B/C layers and `Conflicting` status;
- conflicting evidence is surfaced, never auto-resolved;
- Research Assistant never overwrites analyst content;
- one current record per ticker and append-only snapshots remain intact;
- existing Chapter 1–2 regressions remain green;
- DGC live end-to-end and unified-page smoke tests pass before lock.


---

## Phase 3D — DGC final acceptance and implementation lock

Phase 3D hardens evidence quality rather than trying to force 8/8 autofill. The implementation must distinguish **usable evidence** from mere search-result count.

Quality rules:

- Q8 counts as usable concentration evidence only when an explicit customer/major-customer percentage candidate is present; export/geographic/segment revenue never qualifies by itself.
- Q10 counts as usable retention evidence only when an explicit retention/churn/renewal metric is found in a trusted source.
- Q7/Q9/Q11/Q12/Q13/Q14 require substantive trusted evidence; generic source-directory placeholders do not count.
- Customer-facing first-party sources may support Q9/Q11, but do not automatically prove strong customer orientation.
- Research Assistant may generate **Research Gap suggestions**, but must not overwrite analyst Research Gaps.
- Revenue Relevance / Profit Relevance remain optional analyst/evidence fields and are never auto-filled merely to improve completion.
- An implementation can be locked even if DGC still has Unknown questions: `Unknown` represents a real evidence gap, not a software failure.

DGC final acceptance requires:

1. live evidence collection completes without critical engine error;
2. all analyst-judgement autofill guardrails remain false;
3. export share does not become customer concentration;
4. customer names without explicit share do not become a fabricated concentration percentage;
5. generic links/placeholders do not inflate Q13/Q14 coverage;
6. missing Q8/Q10/Q11/Q13/Q14 evidence is surfaced as Research Gaps instead of invented conclusions;
7. full Chapter 1–3 regression and unified-page smoke tests pass.
