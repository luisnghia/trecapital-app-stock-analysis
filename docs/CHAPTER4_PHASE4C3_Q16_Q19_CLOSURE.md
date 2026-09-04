# Chapter 4 — Phase 4C.3: Q16 Corroboration + Q19 Full Shearn Coverage

## Purpose

Phase 4C.3 closes the two residual evidence-quality problems after Phase 4C.2 without changing the core principle:

> Research Assistant finds, classifies and audits evidence; the analyst owns the conclusion.

The phase is based on Michael Shearn, *The Investment Checklist*, Chapter 4:

- Q16: **Does the business possess the ability to raise prices without losing customers?**
- Q19: **What is the competitive landscape, and how intense is the competition?**

For Q19, the implementation preserves the existing 8-bucket workspace taxonomy. Seven buckets correspond directly to Shearn's competitive-landscape questions; `Industry Change / Capacity Competition` makes explicit Shearn's instruction to ask how competitive dynamics could change.

## Q16 — evidence standard

A pricing candidate is not Pricing Power merely because:

- gross/EBIT margin increased;
- management says it raised price;
- ASP increased;
- commodity prices rose;
- cost increases were passed through.

Strong candidate evidence requires explicit **price + customer/volume/retention/demand response**. Phase 4C.3 adds a conservative corroboration matrix:

- same reporting period;
- at least two explicit candidates;
- at least two distinct source domains;
- at least one independent source.

Even then the result is labelled `Period-level corroboration candidate — analyst verify same event`. It is not event-level proof because two reports in the same year can discuss different pricing events.

## Q19 — full coverage matrix

The 8 workspace buckets are:

1. Limited / Direct Competition
2. How Competitors Compete
3. Fierceness / Price Competition
4. Substitute Products
5. Low-cost Country Competition
6. Industry Standard / Market Position
7. Industry Change / Capacity Competition
8. Why Competitors Failed

Phase 4C.3 fixes the previous **first-match classifier**. A single passage may legitimately support several buckets while preserving one source/snippet. Example: China capacity expansion plus discounting may be evidence for low-cost-country competition, capacity change and price competition at the same time.

The engine then searches only still-missing buckets with category-specific queries and displays a row-by-row Coverage Matrix. Missing evidence remains `Gap`; the app does not fabricate evidence to reach 8/8.

## Source hierarchy

1. Company/official disclosures.
2. Independent research/financial sources.
3. Search-result candidates.
4. Same-industry peers are context only and are never automatically treated as direct competitors.

DGC acceptance adds a small transparent registry of directly fetchable sources so CI is less dependent on search-engine throttling. Registered sources remain candidate evidence.

## Persistence

Phase 4C.3 candidates are appended to the existing Chapter-4 Evidence Matrix with:

- `Status = Candidate — Analyst verify`
- `Data Origin = Chapter 4 Research Assistant Evidence Bridge Phase 4C.3`

No analyst-owned fields are overwritten.

## Guardrails

The engine must never:

- infer Pricing Power from margin only;
- infer Pricing Power from price only;
- equate commodity/pass-through pricing with sustainable Pricing Power;
- claim period-level corroboration proves the same pricing event;
- convert same-industry peers into confirmed direct competitors;
- choose Competition Intensity;
- choose the Ideal Company;
- infer the root cause of competitor failure without evidence;
- change Research Gate;
- issue BUY/HOLD/SELL.

## Acceptance criteria

- Multi-label Q19 classifier is deterministic and tested.
- Q19 Coverage Matrix always contains all 8 buckets and visibly retains gaps.
- Q16 corroboration requires two domains plus at least one independent source.
- Price-only candidates never enter the corroboration matrix.
- Analyst fields are unchanged when evidence is appended.
- Full Deep Analysis regression passes.
- Live DGC diagnostic runs without synthetic peer/evidence fallback.
- Unified Streamlit page starts successfully.

## Next phase

After Phase 4C.3, run **Phase 4D — DGC Final Acceptance & Chapter 4 lock**. Phase 4D should evaluate completeness, provenance, UX, persistence, analyst-control guardrails and end-to-end restart behavior before declaring Chapter 4 locked.
