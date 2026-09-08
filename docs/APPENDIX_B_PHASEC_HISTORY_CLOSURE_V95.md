# Appendix B — Phase C / V95

## Scope

V95 closes Michael Shearn's Appendix B, **How to Interview the Management Team**, by adding immutable snapshots, interview-session lineage, neutral delta, explicit analyst re-review, Streamlit history UI, deterministic closure QA and a dedicated GitHub Actions workflow.

## Source lock

Appendix B remains locked to printed pages **331–334**. The implementation preserves the book's framing:

- management interviews are an art intended to reveal how managers think;
- use open-ended questions and listen, then clarify;
- do not rely on hypothetical answers as evidence of how a manager will actually behave;
- treat face-to-face impressions cautiously because personality affinity, optimism, context, background and the observer's own experience can distort judgment;
- the analyst owns interpretation and conclusions.

V95 does not add new questions, weights or management-quality criteria beyond the source-locked Appendix B protocol.

## Snapshot / history model

A snapshot stores only normalized Appendix B analyst-owned state:

- management interview sessions;
- source-locked topic entries;
- management response / observation;
- clarification / follow-up;
- past-behavior evidence;
- hypothetical-answer caveats;
- face-to-face caveats;
- reference-only Q01–Q59 links;
- analyst commentary and session notes;
- Appendix B research gaps.

Snapshots are immutable. Current workspace edits do not rewrite earlier snapshots.

## Neutral delta

History comparison uses only:

- `Unchanged`
- `Added`
- `Removed`
- `Changed`

A delta has no directional investment meaning. It does **not** mean management became better/worse, more/less credible, or that an investment action should change.

## Explicit re-review

Analyst re-review is stored separately as timestamped scope + note. Recording re-review does not automatically change:

- session status;
- DCA question state;
- management conclusion;
- intrinsic value or MOS;
- Investment Research Gate;
- portfolio action.

## SSOT / investment boundary

V95 creates **no new financial formulas** and no duplicate company/financial SSOT. Q01–Q59 remain reference-only links.

Forbidden automation remains unchanged:

- no management score or weighted management score;
- no CEO-quality classifier;
- no credibility/personality score;
- no BUY/HOLD/SELL;
- no automatic intrinsic-value or MOS change;
- no Investment Research Gate change.

AI remains a **Research Assistant**. The analyst owns all interpretation and conclusions.

## Appendix B closure

With V93 source lock, V94 operational workspace/persistence and V95 history/closure, Appendix B is **COMPLETE** under the current Deep Company Analysis architecture.

The next source section is **Appendix C — Your Investment Checklist**. Appendix C must be read directly from the book before deciding whether it is a consolidated checklist view, a new persistence surface, or documentation-only mapping. No implementation assumptions are carried forward without source support.
