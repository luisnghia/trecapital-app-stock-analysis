# Chapter 3 — Locked Acceptance DGC

## Status

**Implementation lock candidate accepted after Phase 3D hardening.**

Methodology source: Michael Shearn, *The Investment Checklist: The Art of In-Depth Research*, Chapter 3 — **Understanding the Business—from the Customer Perspective**.

This lock means the **Chapter 3 research system, evidence guardrails, persistence and analyst-control behavior are accepted**. It does **not** mean every Q7–Q14 answer can or should be auto-filled for DGC.

Project rule remains:

> **AI/Data = Research Assistant; user = Investment Analyst.**

`Unknown` is a valid research outcome when the evidence is not available or not sufficiently reliable.

---

## Baseline DGC Phase 3D acceptance run

Baseline run date: **2026-09-03**  
Workflow run: `33710381096`  
Generated implementation commit: `8a0e925cc35145bf875524259d6ae8cd5ed44f9a`

Company:

- Ticker: `DGC`
- Company: `CTCP Tập đoàn Hóa chất Đức Giang`
- Canonical data error: none
- Customer-evidence engine error: none

### Evidence collected

- Total evidence candidates: **73**
- Q7: 28 candidates
- Q8: 0
- Q9: 23
- Q10: 0
- Q11: 10
- Q12: 6
- Q13: 0
- Q14: 0

The raw row counts are not treated as the acceptance score. Phase 3D uses **quality coverage** so generic links, directory placeholders or weak keyword hits do not make a question appear researched.

### Quality coverage

| Question | Usable evidence | Acceptance interpretation |
|---|---|---|
| Q7 — Core Customer | Yes | Evidence exists for customer/user context; analyst still decides the core customer. Revenue Relevance and Profit Relevance remain evidence-only optional fields. |
| Q8 — Customer Concentration | No | No explicit major-customer revenue-share evidence was found. Keep `Unknown` / Research Gap. |
| Q9 — Sales Friction | Yes | Evidence exists for selling/channel/promotion context; analyst still chooses Easy/Moderate/Hard. |
| Q10 — Retention | No | No explicit retention/churn/renewal metric was found. Do not manufacture a retention rate. |
| Q11 — Customer Orientation | Yes | Customer-facing/support evidence exists; it is evidence, not proof of strong customer orientation. |
| Q12 — Customer Pain | Yes | Evidence exists for customer need/use-case context; analyst validates the actual pain. |
| Q13 — Customer Dependency | No | Insufficient evidence for deferral/substitutes/dependency. Analyst must retain `Unknown` until researched. |
| Q14 — Disappearance Test | No | Insufficient customer-side evidence for replacement time/switching burden/disruption. |

Quality coverage baseline: **4/8 = 50.0%**.

The remaining four questions are genuine **research gaps**, not implementation failures.

---

## Critical guardrails — all passed

The DGC live acceptance confirmed that Research Assistant did **not** automatically:

- fill Q7 `Revenue Relevance` or `Profit Relevance`;
- assign Q8 concentration status;
- assign Q9 Sales Ease;
- assign Q13 Shearn dependency classification;
- assign Q14 disruption/impact level;
- write Q14 analyst conclusion;
- fabricate Customer Interview records;
- fabricate Evidence Matrix rows.

Phase 3D also adds dedicated regression tests to ensure:

1. `80% doanh thu từ xuất khẩu` cannot be converted into customer concentration;
2. named receivable counterparties without an explicit customer revenue share cannot become a concentration metric;
3. customer-support material may count as Q11 evidence but cannot become an analyst judgment;
4. generic source-directory/placeholders cannot inflate Q13/Q14 evidence coverage;
5. missing Q8/Q10/Q13/Q14 evidence becomes a Research Gap rather than a fabricated answer.

---

## Revenue Relevance / Profit Relevance lock rule

These two approved Trecapital fields remain separate in Q7:

- **Revenue Relevance** — customer/customer-group revenue importance only when supported by explicit disclosure/evidence.
- **Profit Relevance** — customer/customer-group profit contribution, margin economics or qualitative profitability relevance only when supported by disclosure/evidence.

They are optional and are **not Shearn scores**.

Forbidden in the locked implementation:

- deriving customer revenue share from geographic/export revenue;
- deriving customer revenue share from a business segment unless the disclosure explicitly maps that segment to the customer group;
- deriving profit contribution from revenue share alone;
- assuming export customers have a particular profit margin;
- auto-filling either field merely to improve research completion.

---

## Research gaps preserved for DGC

Current Phase 3D gaps that should be shown to the analyst:

- **Q8:** locate major-customer disclosure with explicit revenue percentage and period; compare historical concentration if available.
- **Q10:** locate explicit retention/churn/renewal data; otherwise keep `Not disclosed` or `Unknown` as appropriate.
- **Q13:** obtain evidence on dependency, how long customers can defer purchase/use, and viable substitutes; analyst chooses Shearn's continuum.
- **Q14:** obtain customer/channel evidence on immediate alternatives, time to replace, switching burden and operational disruption; analyst determines final impact.

Customer interviews / channel checks remain the preferred way to close gaps that company disclosure cannot answer.

---

## Test baseline

Phase 3D apply run passed:

- Phase 3D hardening tests: **5 passed**
- Chapter 3 core tests: **8 passed**
- Chapter 3 customer-evidence tests: **5 passed**
- Full Deep Company Analysis regression: **57 passed**
- DGC live Chapter 3 diagnostic: **passed**

Final release CI must additionally pass the unified Streamlit page smoke test and package build before the user-facing offline version is considered final.

---

## Lock decision

Chapter 3 is considered **implementation-complete** when final CI confirms the Phase 3D tests, DGC live diagnostic, unified-page smoke tests and offline package build.

The locked design intentionally does **not** target 8/8 Research Assistant coverage. The correct behavior is:

> **Use evidence when it exists; preserve Unknown when it does not; never turn missing customer knowledge into an invented conclusion.**
