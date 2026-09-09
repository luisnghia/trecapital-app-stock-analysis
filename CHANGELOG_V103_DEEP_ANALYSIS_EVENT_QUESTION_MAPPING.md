# V103 — Deep Company Analysis Event → Question Mapping

## Added
- Deterministic read-only event routing for raw-material/cost, audit/governance, and project-delay events.
- Canonical Qxx references with analyst-review reasons and complete provenance (`source_field`, `source_module`, `source_period`, `data_origin`).
- Stable deduplication/order and strict rejection of unsupported event families.
- V103 DOCX composition layer over the V102 report; exact question wording is resolved from Appendix C at render time.
- Deterministic tests, acceptance audit, architecture boundary checks, dedicated GitHub Actions workflow, full DCA regression, Streamlit health, and offline application artifact.

## Preserved boundaries
- No duplicate financial or question SSOT.
- No checklist status mutation; Q33–Q52 remain Unknown without evidence.
- No second valuation engine or automatic valuation/MOS changes.
- No weighted score, BUY/HOLD/SELL output, or automatic Research Gate changes.
- AI remains `Research Assistant`; the Analyst owns conclusions.
