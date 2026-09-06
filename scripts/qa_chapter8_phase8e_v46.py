from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_integration import build_chapter8_report_frames, build_chapter8_summary


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)


def main() -> None:
    dca_text = (ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py").read_text(encoding="utf-8")
    report_text = (ROOT / "pages" / "04_Bao_cao_tong_hop.py").read_text(encoding="utf-8")

    payload = ch8.empty_payload("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    payload["question_status"]["Q39"] = "Answered"
    payload["question_status"]["Q46"] = "Partial"
    payload["confidence"]["Q39"] = "High"
    payload["analyst_assessment"]["Q39"] = "Analyst-owned acceptance conclusion"
    payload["evidence"] = [{"Question": "Q39", "Claim": "Analyst-promoted acceptance evidence"}]
    payload["research_gaps"] = [{"Question": "Q46", "Research Gap": "Acceptance gap", "Status": "Open"}]

    summary = build_chapter8_summary(payload)
    frames = build_chapter8_report_frames(payload)

    checks = {
        "chapter8_tab_integrated": "render_chapter8_tab" in dca_text and "🧭 Chương 8 — Năng lực vận hành" in dca_text,
        "chapter8_ticker_session_in_chain": 'st.session_state.get("dca_ch8_ticker")' in dca_text,
        "chapter8_status_summary_integrated": "Trạng thái nghiên cứu Chương 8" in dca_text,
        "consolidated_report_integrated": "Deep Company Analysis — Chương 8" in report_text,
        "all_q39_q47_in_report": list(frames["status"]["Question"]) == list(ch8.QUESTION_KEYS),
        "analyst_assessment_preserved": payload["analyst_assessment"]["Q39"] == "Analyst-owned acceptance conclusion",
        "automatic_management_score": summary["automatic_management_score"],
        "automatic_investment_signal": summary["automatic_investment_signal"],
    }
    acceptance = (
        checks["chapter8_tab_integrated"]
        and checks["chapter8_ticker_session_in_chain"]
        and checks["chapter8_status_summary_integrated"]
        and checks["consolidated_report_integrated"]
        and checks["all_q39_q47_in_report"]
        and checks["analyst_assessment_preserved"]
        and checks["automatic_management_score"] is False
        and checks["automatic_investment_signal"] is False
    )

    result = {
        "phase": "Chapter 8 Phase 8E Unified DCA + Consolidated Report Integration V46",
        "acceptance": "PASS" if acceptance else "FAIL",
        "ticker": "DGC",
        "questions": list(ch8.QUESTION_KEYS),
        "answered": summary["answered"],
        "partial": summary["partial"],
        "promoted_evidence": summary["promoted_evidence"],
        "open_research_gaps": summary["research_gaps_open"],
        **checks,
    }
    out = REPORTS / "CHAPTER8_PHASE8E_V46_ACCEPTANCE.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not acceptance:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
