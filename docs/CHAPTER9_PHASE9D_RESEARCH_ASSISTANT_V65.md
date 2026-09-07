# Chapter 9 Phase 9D — Evidence Research Assistant V65

## Scope

Phase 9D continues the same incremental implementation sequence used throughout Deep Company Analysis:

- **Phase 9A / V62** — source-lock Michael Shearn Chapter 9 questions Q48-Q52;
- **Phase 9B / V63** — source-lock 26 research dimensions, explicit prompts/trait lists, red flags, counter-signals and evidence families;
- **Phase 9C / V64** — map those 26 dimensions to the existing Chapter 7 manager master without creating a second manager registry;
- **Phase 9D / V65** — search and extract **candidate evidence** for those already-locked dimensions.

The source question set remains exactly Q48-Q52. No new checklist question or management-quality scoring system is introduced.

## Research architecture

The V65 flow is:

`Chapter 7 manager master -> V64 manager scope -> V63 26-dimension source contract -> Phase 9D search/extraction -> candidate evidence -> analyst verification/promotion`

It is explicitly **not**:

`web snippet -> fact -> automatic management conclusion`.

## Candidate evidence model

Every research row records:

- question and source-locked dimension key;
- source-locked dimension label;
- Chapter 7 Manager ID/name/current role when the source text exactly matches the manager name;
- source family;
- non-conclusive direction cue;
- source grade;
- search-snippet versus extracted-original-source status;
- source title and URL/file;
- source/as-of date fields when available;
- evidence text/reference;
- research method and data origin;
- `Candidate — analyst verify` status.

Search result titles/snippets are never promoted to facts automatically. They remain:

`Search title/snippet candidate — analyst verify original source`

Original text extracted from company/official documents is stronger evidence but still remains:

`Extracted original source text — analyst verify context`

## Source families preserved from Phase 9B

Phase 9D keeps the evidence-family framing already locked in V63.

### Q48

Research targets include manager interviews/profiles, proxy/background biographies, lawful public records where available, foundation/nonprofit giving records, company/personal philanthropy disclosures and continuous-improvement evidence.

Lifestyle, compensation, philanthropy or outside activities are treated as **indicators/context**, never standalone proof of motivation, ethics or character.

### Q49

Research targets include historical adversity articles, regulatory/company filings, press releases during the event, conference-call transcripts and prior-employer history where useful.

The app looks for dated evidence around consistency between words/actions, moments of integrity, adversity response and durable problem solving. Lack of a documented integrity moment remains **Unknown**, not negative evidence.

### Q50

Research targets include sequential shareholder letters, annual reports, historical call transcripts/Q&A, adversity communications and adjusted/pro-forma disclosure context.

The research assistant can sort candidates around clarity, good-news/bad-news balance, corporate speak and double speak, but these labels remain analyst-review cues rather than automated conclusions.

### Q51

Research targets documented strategic/operating decisions, shareholder communications, manager interviews explaining rationale and peer actions used strictly as context.

Peer behavior is not treated as a management-quality benchmark.

### Q52

Research targets investor-conference/roadshow evidence, financial-press/TV activity, stock-price-focused language and financing context.

The V63 financing exception is preserved: promotion activity associated with genuine debt/equity/acquisition or expansion financing is tagged as:

`Context / exception cue — analyst assess`

rather than automatically treated as self-promotion.

## Manager identity controls

Chapter 7 remains the only manager identity/background SSOT.

- Q48 and Q52 remain CEO-specific.
- Search/extracted evidence is attached to a CEO only when the exact Chapter 7 manager name is found in the candidate text.
- Company-level evidence mentioning an unnamed CEO is left unassigned until analyst verification.
- A CFO, deputy CEO or other executive mentioned in Q48/Q52 research is never silently relabelled as the CEO.
- Missing Chapter 7 manager data remains an open research gap.
- No replacement/synthetic Manager ID is generated.

## Research gap model

V65 creates dimension-level gaps across all 26 source-locked dimensions.

Possible open gaps include:

- `Open — evidence gap` — no candidate found;
- `Open — verification gap` — only search title/snippet candidates exist;
- `Open — source-quality gap` — no A/B source has yet corroborated the dimension;
- `Open — manager-link verification gap` — CEO-specific candidate exists but is not linked by exact Chapter 7 manager-name match;
- Phase 9C manager/CEO identity-role gaps.

These are research-completeness warnings only. They are not positive/negative management traits.

## Coverage table

`evidence_quality_summary()` creates one row per source-locked dimension and counts:

- total candidates;
- A / B / C source grades;
- extracted direct-source text;
- manager-linked evidence;
- supporting/counter/mixed research cues.

Every row carries the boundary:

`Coverage only — not a management score`

Counts are for research completeness and do not create weights, ranks or character scores.

## Reuse of the existing research stack

To stay aligned with the current implementation rather than creating a parallel web stack, V65 reuses:

- the existing `WebEvidenceAgent` search mechanism;
- existing registered company/IR domains;
- the Chapter 8 bounded official-document discovery helper;
- the existing source-grade logic;
- Chapter 7 manager identities via the V64 bridge.

This keeps Chapter 9 research consistent with Chapters 7 and 8.

## Acceptance boundaries

Phase 9D must pass all of the following:

- exact Q48-Q52 source lock remains unchanged;
- exactly 26 Phase 9B dimensions remain the only dimension contract;
- every one of the 26 dimensions has research matching vocabulary;
- search snippets remain candidates requiring original-source verification;
- direct extracted source text still requires analyst context verification;
- Chapter 7 remains manager identity SSOT;
- Q48/Q52 evidence is not attached to an unnamed/unverified CEO;
- no replacement manager IDs;
- no automatic positive/negative character classification;
- no management score, rank or weight;
- no MOS, Research Gate or BUY/HOLD/SELL behavior;
- no database persistence or Streamlit/UI changes in this phase;
- full Deep Company Analysis regression and production Streamlit health remain green.

## Next phase

After V65 is green, the next incremental step should be **Phase 9E — Analyst Workspace / Candidate Promotion & Persistence**.

That phase should let the analyst review candidate evidence, promote selected rows into the Chapter 9 evidence matrix, preserve source/date/manager/dimension lineage, keep counter-evidence, and persist the analyst-owned workspace. It should still avoid an automatic management-quality score unless a later source-backed design phase explicitly defines one.
