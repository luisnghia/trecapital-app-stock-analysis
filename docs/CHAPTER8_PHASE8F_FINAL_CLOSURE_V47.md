# Chapter 8 Phase 8F — Final Source Closure & Completion Gate V47

Phase 8F closes Chapter 8 as a research workflow without turning management competence into an automated score.

## Completion gate

The gate measures research completeness only. It does **not** decide whether management is good/bad and it never changes BUY/HOLD/SELL, MOS, valuation, or Research Gate.

A question is considered closed when the analyst has explicitly set it to `Answered` or `N/A`. `Partial` remains open. `Unknown` remains open.

The gate also reports, without auto-scoring:
- promoted / analyst-entered evidence coverage by Q39–Q47;
- unresolved Research Gaps by question and materiality;
- analyst conclusion presence;
- manager identity linkage to Chapter 7;
- structured-data bridge availability for Q41/Q45/Q46/Q47;
- Q43 employee-relation dimension coverage;
- Q46 source lock preserving Shearn's exact five capital-allocation actions;
- Q47 explicit-buyback evidence semantics.

## Source closure rules

1. Official/company and regulatory disclosures are preferred for factual management events.
2. Research candidates do not count as closed evidence until the analyst promotes them.
3. Web numeric observations never replace Trecapital canonical financial data.
4. Missing evidence remains a Research Gap; the app must not infer a negative conclusion from silence.
5. Guidance patterns are research evidence, not fraud/manipulation conclusions.
6. Cost reductions are not automatically positive.
7. Buybacks are not automatically value creating, and falling share count is not itself proof of a buyback.
8. Chapter 7 remains the manager identity master.

## Final acceptance

V47 must pass:
- Phase 8A–8F unit tests;
- source-lock boundary checks;
- DGC canonical refresh + Chapter 8 research + persistence + completion-gate end-to-end probe;
- full Deep Company Analysis regression;
- unified DCA Streamlit smoke;
- consolidated report Streamlit smoke;
- offline ZIP integrity.

The acceptance artifact is the audit package for Chapter 8 closure before work begins on Chapter 9.
