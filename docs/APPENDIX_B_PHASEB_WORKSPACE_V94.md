# Appendix B — Phase B / V94

## Scope

V94 operationalizes Michael Shearn's Appendix B, **How to Interview the Management Team**, on top of the V93 source-lock contract. It adds an analyst-owned management-interview workspace, deterministic session/research-gap identifiers, SQLite persistence, and reference-only linkage to Deep Company Analysis Q01–Q59.

## Source lock

The workspace preserves the Appendix B framing:

- ask one open-ended question at a time;
- listen and clarify rather than leading the answer;
- prefer evidence about what management actually did and why;
- mark hypothetical answers so they are not treated as evidence of future behavior;
- record face-to-face impressions only as assessment caveats;
- compare meeting impressions with contextual operating record, accomplishments and other informed views;
- keep **Management Response / Observation** separate from **Analyst Commentary**.

The eight V93 topic clusters are reused unchanged. V94 does not add an external management framework.

## Architecture

- `appendix_b.py`: V93 source-lock SSOT for terminology/protocol/topics.
- `appendix_b_workspace.py`: normalization, stable IDs, Q01–Q59 reference validation and analyst-owned workspace payload.
- `appendix_b_store.py`: SQLite persistence for normalized sessions and research gaps only.
- `pages/11_Appendix_B_Management_Interview.py`: practical Streamlit interview workspace.

DCA links store question identifiers only. They do not read, copy or mutate chapter state.

## Formula explanation

**No new financial formulas. No management-quality formula and no weighted score are introduced in V94.** Stable IDs use SHA-256 only as deterministic record identifiers; the hash has no analytical meaning.

## SSOT and investment boundary

V94 persists only Appendix B analyst-owned interview state. Normalization is allow-listed and therefore drops unknown fields such as financial payloads, valuation, intrinsic value, margin of safety, Research Gate, management/CEO/credibility/personality scores and investment recommendations.

V94 does **not**:

- create a management, CEO-quality, credibility, personality or weighted score;
- classify managers as good/bad or credible/not credible;
- generate BUY/HOLD/SELL or another investment recommendation;
- change intrinsic value or Margin of Safety;
- change the Investment Research Gate;
- duplicate financial/company SSOT;
- treat face-to-face confidence or charisma as quality evidence;
- infer future behavior from hypothetical answers.

AI remains a **Research Assistant** that may organize evidence and gaps. The analyst owns interpretation and conclusions.
