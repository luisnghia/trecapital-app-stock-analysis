# Chapter 8 Phase 8H — Gap-Directed Research V53

Phase 8H turns the open dimension/subtopic gaps produced by Phase 8G into a bounded second research pass. The purpose is to stop broad candidate accumulation from hiding missing Michael Shearn evidence dimensions.

## Workflow

1. Run the existing Chapter 8 evidence research.
2. Build source-locked dimension coverage for Q39-Q47.
3. Select only dimensions that remain open or only have non-A-quality evidence.
4. Schedule targets round-robin across Q39-Q47 so one question cannot consume the whole research budget.
5. Build at most two queries per target, using the registered company/IR domain when available.
6. For manager-scoped questions, include only names already present in the Chapter 7 manager master. If Chapter 7 is empty, the search stays general and the manager identity gap remains open.
7. Convert only search rows that explicitly match the target dimension into `Candidate — analyst verify` rows.
8. Merge by Candidate ID, recompute dimension coverage, and keep every remaining gap open.

## Source locks and boundaries

- Chapter 7 remains the manager identity/background SSOT.
- Trecapital canonical financial data / Module 1 remains the financial SSOT.
- Q43 remains exactly the 14 Shearn employee-relation dimensions locked in `chapter8.py`.
- Q46 remains exactly five Shearn capital-allocation actions. Hurdle/discipline evidence is context only and is never a sixth action.
- Q47 requires explicit buyback authorization/execution evidence; share-count decline is not proof.
- Phase 8H never promotes evidence automatically.
- Phase 8H never writes analyst assessment, confidence, question status, MOS, Research Gate, or investment action.
- Candidate and coverage counts are research workflow metadata, not a management score.

## Production integration

`chapter8_page_support.py` continues to use the existing Chapter 8 session/storage architecture. Its historical import path `chapter8_research_v52` is a compatibility shim on the V53 feature branch and re-exports `chapter8_research_v53`. This avoids a parallel workspace or database while allowing the existing **Tự nghiên cứu Q39–Q47** action to execute the gap-directed second pass.

Gap-directed candidates appear in the existing candidate table with `Source Method = Phase 8H gap-directed research — <dimension key>`. They still require the analyst to open the source, verify it, tick `Select`, and explicitly promote it.

## Acceptance

The live DGC acceptance verifies that:

- canonical data refreshes successfully and the latest structured context reaches TTM;
- the planner creates a bounded target list from open source-locked dimensions only;
- target queries are attempted and logged;
- source-locked open dimensions never increase after the second pass;
- any newly found rows remain `Candidate — analyst verify` and are not selected/promoted automatically;
- any Manager ID found is already present in the Chapter 7 manager reference;
- Q43=14, Q46=5, and Q47's explicit-buyback rule remain intact;
- no analyst workspace mutation, management score, or investment signal is created.
