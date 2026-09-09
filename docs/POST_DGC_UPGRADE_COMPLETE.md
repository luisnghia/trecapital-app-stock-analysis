# POST-DGC UPGRADE COMPLETE — V104

## Closure scope
This marker closes the post-DGC upgrade program that begins with V99 Financial Semantics & TTM Provenance and continues through V100–V103.

Verified coverage:
- V99: canonical financial semantics, TTM provenance and Data Layer ownership boundaries.
- V100: 5–10 year cyclical normalization and historical comparability, including median / trimmed mean, peak-trough context, normalized profitability/returns, scenario range and comparability breaks.
- V101: evidence-rich Investment Checklist DOCX report, reading Q01–Q59 from the existing Appendix C/source-lock owner by reference.
- V102: 10Y + latest TTM quantitative financial tables/charts covering Revenue, Gross Profit/GPM, EBIT/EBITDA, consolidated net profit, NPAT-MI, margins, CFO/Capex/FCF, CFO/Net Profit, FCF/Net Profit, cash/debt/net cash/equity/leverage, ROIC/ROCE, AR/inventory/AP/CCC and cyclical normalization.
- V103: deterministic read-only event → question evidence routing for raw-material/cost, audit/governance and project-delay events with provenance.

## Required review surfaces
The report chain preserves:
- exact source wording through the Appendix C question owner rather than a duplicate question SSOT;
- Q33–Q52 = `Unknown` when evidence is insufficient;
- provenance fields `source_field`, `source_module`, `source_period`, `data_origin`;
- `What changed since last review` and `Critical unknowns`;
- quantitative evidence and V100 normalization composed into the DOCX reporting chain.

## Architecture and investment boundaries
- Trecapital Data Layer remains the financial SSOT.
- No duplicate financial/question SSOT is introduced.
- Valuation and MOS remain owned by Module 2; this closure creates no second valuation engine.
- AI role remains `Research Assistant`; the analyst owns interpretations and conclusions.
- No weighted management/growth/checklist score.
- No automatic BUY/HOLD/SELL recommendation.
- No automatic intrinsic-value or MOS change.
- No automatic Investment Research Gate change.
- Event routing is review assistance only and never mutates checklist status.

## QA closure contract
V104 adds a deterministic static closure audit and a dedicated GitHub Actions workflow. The workflow must compile the closure test, run V99–V103/post-DGC deterministic tests, run the full `modules/deep_company_analysis/test_*.py` regression, verify Streamlit can import/start in headless mode, build an offline repository ZIP, verify ZIP integrity and upload the artifact.

Final branch: `feature/deep-company-analysis-post-dgc-closure-v104`.
Base commit: `c95581e2597d976ba96fca0e62d4ccc8396adbb4` (V103).

This marker means the requested post-DGC upgrade scope is closed after the V104 workflow passes. No additional phase should be created unless a future audit identifies a concrete implementation/source-lock gap or the user supplies new scope.
