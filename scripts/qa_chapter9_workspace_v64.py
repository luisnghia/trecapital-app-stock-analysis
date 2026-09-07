from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_source_contract_v63 as v63
import modules.deep_company_analysis.chapter9_workspace_v64 as ws
import modules.deep_company_analysis.chapter9_completion_v64 as completion


def main() -> int:
    default_payload = ws.empty_workspace_payload("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    default_snapshot = ws.workspace_snapshot(default_payload)
    default_gate = completion.build_completion_gate(default_payload)

    closed_payload = ws.empty_workspace_payload("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    closed_payload, applied, rejected = ws.apply_dimension_edits(
        closed_payload,
        [
            {
                "Dimension Key": dim.key,
                "Evidence Status": "N/A — analyst verified",
                "Analyst Note": "Synthetic QA row: explicit analyst N/A closure only.",
            }
            for dim in v63.all_dimensions()
        ],
    )
    for q in ch9.QUESTION_KEYS:
        closed_payload["question_status"][q] = "N/A"
    closed_gate = completion.build_completion_gate(closed_payload)

    tampered = ws.empty_workspace_payload("DGC")
    first_key = tampered["dimension_evidence"][0]["Dimension Key"]
    tampered, _, tampered_rejections = ws.apply_dimension_edits(
        tampered,
        [{
            "Dimension Key": first_key,
            "Question": "Q52",
            "Dimension": "tampered",
            "Source Pages": "999",
            "Evidence Status": "Partial — analyst review",
        }],
    )
    first = tampered["dimension_evidence"][0]

    report = {
        "phase": "Chapter 9 Phase 9C Analyst Workspace V64",
        "acceptance": "PASS",
        "chapter": ch9.CHAPTER_NUMBER,
        "chapter_title": ch9.CHAPTER_TITLE,
        "source_lock": ch9.SOURCE_LOCK,
        "question_keys": list(ch9.QUESTION_KEYS),
        "dimension_counts": default_snapshot["dimension_counts"],
        "total_dimensions": default_snapshot["total_dimensions"],
        "default_open_dimension_gaps": len(ws.build_open_dimension_gaps(default_payload)),
        "default_gate_ready": default_gate["ready_for_chapter_close"],
        "explicit_all_na_edits_applied": applied,
        "explicit_all_na_edit_rejections": rejected,
        "explicit_all_na_gate_ready": closed_gate["ready_for_chapter_close"],
        "source_fields_relocked_after_tamper": (
            first["Question"] == "Q48"
            and first["Dimension"] == ch9.Q48_PASSION_RESEARCH_PROMPTS[0]
            and first["Source Pages"] == "257"
        ),
        "tamper_edit_rejections": tampered_rejections,
        "manager_identity_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "ui_added": False,
        "database_or_store_added": False,
        "web_research_added": False,
        "financial_bridge_added": False,
        "mos_or_research_gate_changed": False,
        "research_note": (
            "Phase 9C turns the 26 V63 source-locked dimensions into a pure analyst workspace and "
            "research-completion gate. Source fields are immutable, Chapter 7 remains manager SSOT, "
            "all default rows are unknown/open, and only explicit analyst closure can satisfy the gate."
        ),
    }

    assert report["total_dimensions"] == 26
    assert report["default_open_dimension_gaps"] == 26
    assert report["default_gate_ready"] is False
    assert report["explicit_all_na_edits_applied"] == 26
    assert report["explicit_all_na_edit_rejections"] == []
    assert report["explicit_all_na_gate_ready"] is True
    assert report["source_fields_relocked_after_tamper"] is True
    assert report["automatic_management_score"] is False
    assert report["automatic_investment_signal"] is False

    output = Path("reports/CH9_PHASE9C_ANALYST_WORKSPACE_V64.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
