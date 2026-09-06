# Deep Company Analysis — Chapter 8 Phase 8C Research Assistant V44

## 1. Scope

Phase 8C adds the automated evidence-research layer for Michael Shearn Chapter 8 questions Q39–Q47.

This phase does **not** add a management score, an investment recommendation, a MOS change, or a Research Gate decision. It only produces evidence candidates, source-quality coverage, and explicit research gaps for analyst review.

Source lock remains:

- Q39 — CEO and all stakeholders.
- Q40 — day-to-day operating improvement versus strategic-plan approach.
- Q41 — CEO/CFO earnings guidance.
- Q42 — centralized versus decentralized management.
- Q43 — employee relations, preserving the 14 Shearn prompts from Phase 8A.
- Q44 — quality of hiring.
- Q45 — unnecessary-cost discipline.
- Q46 — capital-allocation discipline using the exact five Shearn uses of excess free cash flow.
- Q47 — opportunistic stock repurchases.

## 2. Architecture and SSOT boundaries

### Manager identity

Chapter 7 remains the manager master. Phase 8C may reference `Manager ID` and manager name only when those values already exist in the Chapter 7 payload.

If Chapter 7 is empty, Phase 8C:
- does not create replacement IDs;
- leaves manager fields blank;
- creates an explicit manager-identity research gap for manager-targeted questions.

### Financial data

Trecapital canonical normalized financial data / Module 1 remains the financial SSOT.

Phase 8C does not ingest web numbers into a parallel financial dataset. Quantitative Q45/Q46/Q47 context remains in Phase 8B and comes from canonical Trecapital data.

### Web / document research

External research is limited to qualitative/event evidence candidates and dated disclosure context:
- company/IR website and documents;
- exchange/regulator disclosures;
- high-quality independent financial sources as secondary corroboration;
- other secondary sources only as lower-grade context.

Search-result snippets and extracted text are never final analyst evidence until reviewed/promoted.

## 3. Source hierarchy

Phase 8C grades evidence candidates:

1. `A — Company/Official disclosure`
2. `A — Exchange/Regulator disclosure`
3. `B — Independent financial source/research`
4. `C — Secondary/context source`

For DGC, the registered company source is `ducgiangchem.vn`.

The research engine performs a bounded same-domain crawl from registered company/IR roots. It prioritizes annual reports, governance reports, sustainability/employee materials, AGM resolutions, disclosures, dividends, buybacks, ESOP/remuneration, appointments, strategy, restructuring, and cost-related material.

HTML and PDF text extraction is allowed. OCR is not used.

Fetch failures are retained in the source-attempt table rather than silently replaced by invented evidence.

## 4. Evidence candidate schema

Every candidate contains:

- selection flag;
- stable Candidate ID;
- Q39–Q47 question key;
- Chapter 7 Manager ID / Manager when explicitly matched;
- question-specific subtopic;
- evidence-direction **cue** only;
- source grade;
- explicitness;
- source title and URL/file;
- source/as-of date;
- evidence text/reference;
- source method;
- data origin;
- candidate status.

Direction values are deliberately non-conclusive:
- `Supporting cue — analyst assess`
- `Counter-evidence cue — analyst assess`
- `Mixed cue — analyst assess`
- `Neutral / context — analyst assess`

They are not management-quality conclusions.

## 5. Question-specific controls

### Q39

Candidates are separated across Customers, Employees, Suppliers, Shareholders, Business partners, and Other stakeholders.

The presence of stakeholder language is not enough to conclude that management benefits all stakeholders.

### Q40

Research distinguishes:
- continuous improvement;
- strategic plan / transformation;
- frontline feedback;
- adaptation.

No automatic centralized judgment or management-quality conclusion is produced.

### Q41

Research looks for explicit guidance/forecast/plan disclosures and revision/withdrawal evidence.

Search text does not automatically populate numeric guidance, actual results, or outcome. Phase 8B's structured guidance table remains the target for analyst-verified numeric entry.

### Q42

Research collects central-control, delegation/autonomy, and business-unit decision-right evidence.

Only the analyst may select Centralized / Mixed / Decentralized.

### Q43

The Phase 8A 14 employee-relations prompts remain source locked. Phase 8C collects candidate evidence around training, retention, promotion/career path, culture/shared values, employee voice, benefits/treatment, and recruitment attractiveness without scoring them.

### Q44

Research covers internal promotion/succession, external hiring, selection/talent development, and appointments. Appointment evidence alone is not treated as proof of hiring quality.

### Q45

Research must preserve both benefits and possible harms from cost actions:
- cost reduction/savings;
- restructuring/layoffs;
- efficiency/waste;
- customer and employee impact;
- whether core investment was preserved.

Quantitative cost history remains Phase 8B canonical context.

### Q46

The exact five Shearn uses remain:

1. Reinvest in business / new projects
2. Hold cash
3. Pay dividends
4. Buy back stock
5. Make acquisitions

Debt repayment is not inserted as a sixth source-locked Shearn bucket.

Phase 8C may research hurdle-rate/ROIC/IRR language as discipline context, but it does not score capital-allocation quality.

### Q47

A share-count decline alone is not evidence of a buyback.

Q47 evidence requires explicit buyback / repurchase / treasury-share language. Research may collect authorization, execution, price, valuation and liquidity context, but only the analyst determines opportunism.

## 6. Research gaps

For every Q39–Q47:

- no candidate -> `Open — evidence gap`;
- candidates but no A-quality source -> `Open — source-quality gap`;
- manager-targeted questions with no Chapter 7 manager master -> `Open — manager identity gap`.

Unknown is a valid result. Lack of disclosure is never converted into a positive or negative management conclusion.

## 7. V44 acceptance tests

V44 CI performs:

- Python compile for Phase 8A/8B/8C;
- deterministic Phase 8A/8B/8C tests;
- live DGC company-source research;
- source-quality and analyst-boundary static audit;
- full Deep Company Analysis regression;
- Streamlit health smoke test;
- artifact build and ZIP integrity check.

A PASS means the Phase 8C research-assistant implementation is technically accepted. It does not mean DGC management is good/bad, does not mean Q39–Q47 are fully answered, and does not constitute an investment recommendation.

## 8. Next phase

Phase 8D should integrate Phase 8B structured context and Phase 8C evidence candidates into the Streamlit Chapter 8 analyst workspace, including explicit analyst promotion, research-gap workflow, source opening, and persistence without overwriting analyst judgments.
