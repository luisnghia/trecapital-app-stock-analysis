# Chapter 9 Phase 9C — Manager Context Bridge V64

## Scope

Phase 9C continues the existing Deep Company Analysis implementation sequence after:

- **Phase 9A / V62** — lock Michael Shearn Chapter 9 questions Q48-Q52;
- **Phase 9B / V63** — lock the 26 source-derived research dimensions, red flags/counter-signals and evidence families.

Phase 9C adds the **structured manager-context bridge** needed before automated evidence research. It connects those 26 Chapter 9 dimensions to the existing **Chapter 7 manager master**, which remains the single source of truth (SSOT) for manager identity/background.

This phase intentionally does **not** add a web research agent, UI, database persistence, financial-data bridge, management score, automatic character label, MOS change, Research Gate change, or BUY/HOLD/SELL signal.

## Why this bridge is separate

Chapter 9 is about personality and character, while Chapter 7 already owns manager identity/background. Building a second manager registry inside Chapter 9 would allow the same person to acquire different IDs/names/roles across chapters. Phase 9C therefore references Chapter 7 instead of copying or recreating a manager master.

The Phase 9C flow is:

`Chapter 7 manager master -> Chapter 9 manager reference -> Phase 9B source dimensions -> analyst/research context`

not:

`Chapter 9 -> invent manager -> assess character`.

## Source-question scoping

The original Chapter 9 question set remains unchanged:

- Q48 — Does the CEO love the money or the business?
- Q49 — Can you identify a moment of integrity for the manager?
- Q50 — Are managers clear and consistent in their communications and actions with stakeholders?
- Q51 — Does management think independently and remain unswayed by what others in their industry are doing?
- Q52 — Is the CEO self-promoting?

Phase 9C respects the wording when manager scope is created:

### Q48 and Q52 — CEO-specific

These rows are attached only when Chapter 7 explicitly identifies a current role as CEO / Chief Executive / Tổng Giám đốc. A Deputy CEO / Phó Tổng Giám đốc is **not** silently promoted to the CEO scope.

If an explicit CEO role is unavailable, Q48/Q52 remain unassigned with:

`Open — CEO identity/role gap`

The app must first correct/confirm the manager role in Chapter 7.

### Q49-Q51 — manager/management scope

The bridge references all manager records already present in Chapter 7. This creates research context only. It does not decide which manager is most important, whether a behavior is good/bad, or what the analyst should conclude.

## Unknown-first behavior

If the Chapter 7 manager master is unavailable:

- all **26** Phase 9B dimensions remain present;
- Manager ID and Manager remain blank;
- no synthetic/replacement manager ID is generated;
- an open manager-identity gap is created for Q48-Q52;
- every evidence row remains `Open — analyst research required`.

Absence of a manager identity or behavioral event is not a negative management signal.

## Module

`modules/deep_company_analysis/chapter9_data_bridge.py`

Key outputs:

- `chapter7_manager_reference()` — read-only reference to Chapter 7 manager IDs/roles;
- `build_dimension_scope()` — maps the 26 source dimensions to the appropriate Chapter 7 manager context;
- `build_scope_gaps()` — identity/CEO-role gaps only;
- `build_context()` — deterministic Phase 9C context bundle;
- `context_snapshot()` — coverage metadata only, never a management score.

## Acceptance boundaries

Phase 9C is accepted only when all of the following remain true:

- exact Q48-Q52 Phase 9A source lock remains unchanged;
- all 26 Phase 9B dimensions remain represented;
- manager identities come only from Chapter 7;
- Q48/Q52 are scoped only to an explicit CEO-equivalent role;
- Deputy CEO / Phó Tổng Giám đốc is not treated as CEO;
- missing manager/CEO identity remains Unknown/open gap;
- no replacement manager ID is created;
- no web research, crawler, OCR, UI, database/store, or financial bridge is added;
- no management score, weight, ranking, automatic positive/negative character conclusion, MOS, Research Gate, or BUY/HOLD/SELL behavior;
- full Deep Company Analysis regression and production Streamlit health remain green.

## Next phase

After V64 is green, the next incremental step should be **Phase 9D — Evidence Research Assistant**. It should use this manager-context bridge plus the 26 Phase 9B dimensions to find dated evidence/counter-evidence from company disclosures, exchange/regulator filings, shareholder letters, call transcripts, interviews/profiles and other source families identified by the source contract. Candidate evidence must still require analyst verification/promotion before it affects the Chapter 9 workspace.
