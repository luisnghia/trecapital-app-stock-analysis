# Deep Company Analysis V103 — Event → Question Evidence Mapping

## Purpose
V103 adds a deterministic, read-only routing layer from material company events to relevant Michael Shearn Investment Checklist question references. It helps the Research Assistant surface where an analyst should re-review evidence; it does **not** answer a question or make an investment decision.

## Approved event families

| Event family | Canonical question references | Review purpose |
|---|---|---|
| raw-material / cost | Q20, Q23, Q24, Q45 | supplier dynamics, key risks, inflation/input-cost sensitivity, cost discipline |
| audit / governance | Q27, Q40, Q49, Q50 | accounting quality, stakeholder treatment, integrity, communication consistency |
| project delay | Q23, Q42, Q55, Q56 | execution risk, guidance, future growth, growth pace |

The table intentionally stores **Q IDs only**. Exact wording is resolved at runtime from `modules.deep_company_analysis.appendix_c`; V103 does not create a second question SSOT.

## Event/provenance contract
Each mapping row contains:
- `event_type`, `event_id`, `event_date`, `event_summary`
- `question_id`, `mapping_reason`
- `source_field`, `source_module`, `source_period`, `data_origin`

Rows are deterministically deduplicated and sorted. Unsupported event families are rejected rather than guessed.

## Status and evidence boundary
Mapping means **review this canonical question**. It does not write answer/evidence state and never emits a checklist `status` field. In particular, the existing Q33–Q52 guard remains authoritative: without evidence those questions remain `Unknown`.

## Report composition
`investment_checklist_report_v103.py` opens the V102 DOCX and appends an `Event → Investment Checklist evidence routing` section. Exact question wording is looked up from Appendix C only at render time. V101/V102 remain the owners of checklist and quantitative report presentation respectively.

## Architecture guardrails
- Trecapital Data Layer remains the financial SSOT.
- Appendix C / owner chapters remain the Q01–Q59 source/question SSOT.
- Module 2 remains the valuation/MOS owner; V103 has no valuation formula.
- AI role remains `Research Assistant`; conclusions remain owned by the Analyst.
- No weighted checklist/management/growth score.
- No BUY/HOLD/SELL output.
- No automatic intrinsic-value/MOS change.
- No automatic Investment Research Gate change.

## Deterministic QA
V103 acceptance verifies the three exact event families and Q-reference sets, canonical Q IDs, runtime source-wording resolution, complete provenance, stable dedupe/order, non-mutation of checklist status, the Q33–Q52 Unknown guard, and all investment/SSOT boundaries. Dedicated CI also runs full DCA regression, Streamlit health, and exports an offline application ZIP/artifact.
