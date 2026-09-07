# Formula / Logic Explanation — Chapter 9 Phase 9L / V73

## Scope

Phase 9L has **no financial valuation formula** and **no weighted score**. It performs deterministic comparison of analyst-owned Management Synthesis versions and immutable snapshot lineage.

The output is a version/history audit, not a Management Quality Score and not an investment recommendation.

## 1. Field-level delta logic

For each tracked synthesis field, Phase 9L converts the stored value to a deterministic canonical representation and compares version A with version B.

Conceptually:

`Delta(field) = compare(canonical(value_before), canonical(value_after))`

Classification priority:

1. equal canonical values → `Unchanged`
2. blank before and non-blank after → `Added`
3. non-blank before and blank after → `Removed`
4. otherwise → `Changed`

Dictionaries are serialized with sorted keys. Lists are serialized deterministically. Ordinary text is whitespace-normalized for comparison. This prevents irrelevant formatting noise from being treated as a substantive version change.

These labels are purely structural. `Added` does not mean positive management evidence; `Removed` does not mean negative management evidence; `Changed` does not mean the management thesis improved or worsened.

## 2. Tracked fields

Phase 9L compares:

- Synthesis Status
- Analyst Confidence
- Chapter 7 Background Takeaway
- Chapter 8 Operating Competence Takeaway
- Chapter 9 Management Traits Takeaway
- Management Strengths
- Management Concerns
- Material Management Unknowns
- Evidence That Would Change View
- Final Analyst Management Synthesis
- Analyst Note
- Source Baseline Fingerprint
- Source Counts
- Source Handoff State
- Source Captured At
- Analyst Reviewed At
- Last Re-review At
- Last Re-review Note
- Last Re-review Sections

The source fingerprint is compared using the full stored value but displayed as its first 16 characters for readability.

## 3. Summary counts

For `N` tracked fields:

`Changed fields = Added + Removed + Changed`

`Unchanged fields = count(Delta == Unchanged)`

The engine separately returns booleans for whether these stored fields changed:

- workspace status
- analyst confidence
- final analyst synthesis
- source baseline fingerprint

These are descriptive flags only. No automatic action is attached to them.

## 4. Version lineage ordering

For immutable snapshot records:

`Sort Key = (stored created_at ascending, snapshot_id ascending)`

This gives a deterministic oldest-to-newest lineage. Phase 9L never creates a missing timestamp or guesses historical order from research content.

## 5. Historical source freshness rule

Historical freshness cannot be truthfully reconstructed by comparing an old synthesis snapshot against today's Chapter 7–9 source package and pretending that comparison describes the old date.

Therefore Phase 9L applies this rule:

`Historical freshness reconstruction = False`

For each historical snapshot, only metadata actually stored in that version is shown:

- source baseline fingerprint
- source capture time
- analyst reviewed time
- explicit re-review time
- explicit re-review note/sections

Current source freshness remains the Phase 9K responsibility.

## 6. Immutable snapshot rule

Phase 9L is read-only:

`Snapshot input → comparison/lineage output`

There is no reverse edge:

`comparison output ↛ restore snapshot`

and no write:

`comparison output ↛ overwrite current synthesis`

All version comparison functions operate on normalized deep copies so caller payloads are not mutated.

## 7. Consolidated report rule

The consolidated report can compare:

`Latest immutable snapshot → Current saved Management Synthesis workspace`

If fields differ, the report says that the **record changed**. It does not say management quality improved/deteriorated.

## 8. UI rendering rule

New read-only lineage and delta tables are rendered through:

`static_table_html(frame, height=...) → st.html(html)`

This preserves cell wrapping for long analyst synthesis text and audit metadata.

## 9. Investment boundary invariants

The Phase 9L summary explicitly returns:

- `automatic_workspace_status_change = False`
- `automatic_confidence_change = False`
- `automatic_analyst_text_change = False`
- `automatic_management_score = False`
- `automatic_character_classification = False`
- `automatic_investment_signal = False`
- `mos_or_investment_research_gate_changed = False`
- `historical_source_freshness_reconstructed = False`

There is no financial valuation formula, no weighted management score, no MOS adjustment, no portfolio-sizing rule, and no BUY/HOLD/SELL output in Phase 9L.
