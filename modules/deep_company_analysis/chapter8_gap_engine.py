from __future__ import annotations

"""Chapter 8 Phase 8G — dimension/subtopic evidence-gap engine.

This module upgrades Chapter 8 research completeness from a coarse "candidate exists" check
to a question-specific coverage audit. It is intentionally a research workflow helper, not a
management score. Missing dimensions remain open research gaps; covered dimensions still require
analyst verification and promotion before they can support a conclusion.

Source locks:
- Chapter 7 is the manager identity/background SSOT.
- Trecapital canonical data is the financial SSOT.
- Q43 uses all fourteen Shearn employee-relation prompts exactly as locked in chapter8.py.
- Q46 uses exactly the five Shearn capital-allocation actions. Hurdle/discipline evidence is
  tracked as context, never silently inserted as a sixth action.
- Q47 never treats share-count decline as proof of a buyback.
"""

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_data_bridge import MANAGER_SOURCE_LABEL


BOUNDARY = "Coverage audit only — not a management score; analyst verification/promotion required."
MANAGER_SCOPED_QUESTIONS = {"Q41", "Q44", "Q46", "Q47"}


@dataclass(frozen=True)
class CoverageDimension:
    key: str
    label: str
    terms: tuple[str, ...]
    next_action: str
    source_locked: bool = True


def _d(key: str, label: str, terms: Iterable[str], next_action: str, *, source_locked: bool = True) -> CoverageDimension:
    return CoverageDimension(key, label, tuple(terms), next_action, source_locked)


Q43_TERM_MAP: dict[str, tuple[str, ...]] = {
    "employees_assets_or_liabilities": (
        "employees as assets", "employees are our greatest asset", "people are our greatest asset",
        "human capital", "nguồn nhân lực là tài sản", "người lao động là tài sản", "nguồn lực quý giá",
    ),
    "employee_contributions": (
        "employee contribution", "employees contributed", "contributions of employees",
        "đóng góp của người lao động", "đóng góp của nhân viên", "ghi nhận đóng góp",
    ),
    "retention_critical": (
        "employee retention", "retain employees", "retaining employees", "giữ chân nhân viên",
        "giữ chân người lao động", "ổn định lực lượng lao động", "retention critical",
    ),
    "promote_from_within": (
        "promote from within", "internal promotion", "internal candidate", "thăng tiến nội bộ",
        "bổ nhiệm nội bộ", "nguồn cán bộ nội bộ",
    ),
    "promotion_path": (
        "promotion path", "career path", "career progression", "lộ trình thăng tiến",
        "lộ trình nghề nghiệp", "cơ hội thăng tiến",
    ),
    "training_resources": (
        "employee training", "training program", "training hours", "learning and development",
        "đào tạo nhân viên", "đào tạo người lao động", "giờ đào tạo", "phát triển năng lực",
    ),
    "applicant_attraction": (
        "number of applicants", "job applicants", "applicant attraction", "talent attraction",
        "thu hút ứng viên", "số lượng ứng viên", "tuyển dụng nhân tài",
    ),
    "employees_recruited_away": (
        "recruited away", "employees poached", "headhunted", "headhunting", "poached by competitors",
        "bị săn đầu người", "được doanh nghiệp khác tuyển", "nhân sự bị lôi kéo",
    ),
    "benefit_gap": (
        "executive benefits", "management benefits", "employee benefits", "benefit gap",
        "executive compensation versus employees", "phúc lợi ban lãnh đạo", "phúc lợi người lao động",
        "chênh lệch phúc lợi", "thù lao lãnh đạo",
    ),
    "respectful_layoffs": (
        "respectful layoffs", "layoff", "redundancy", "severance", "workforce reduction",
        "sa thải", "cắt giảm nhân sự", "trợ cấp thôi việc", "hỗ trợ thôi việc",
    ),
    "listens_to_employees": (
        "employee survey", "engagement survey", "employee feedback", "employee voice", "listen to employees",
        "khảo sát nhân viên", "khảo sát người lao động", "lắng nghe nhân viên", "ý kiến người lao động",
    ),
    "strong_culture": (
        "strong culture", "company culture", "corporate culture", "organizational culture",
        "văn hóa doanh nghiệp", "văn hoá doanh nghiệp", "văn hóa tổ chức",
    ),
    "shared_values": (
        "shared values", "core values", "common values", "giá trị cốt lõi", "giá trị chung",
    ),
    "employee_retention_rate": (
        "employee retention rate", "retention rate", "employee turnover rate", "staff turnover rate",
        "tỷ lệ giữ chân", "tỷ lệ nghỉ việc", "tỷ lệ biến động lao động",
    ),
}


def _q43_dimensions() -> tuple[CoverageDimension, ...]:
    rows: list[CoverageDimension] = []
    for key, label in ch8.EMPLOYEE_RELATION_DIMENSIONS:
        rows.append(_d(
            key,
            label,
            Q43_TERM_MAP[key],
            f"Find dated original evidence for Q43 dimension `{key}`; absence of evidence remains Unknown.",
        ))
    return tuple(rows)


QUESTION_DIMENSIONS: dict[str, tuple[CoverageDimension, ...]] = {
    "Q39": (
        _d("customers", "Customers", ("customer", "khách hàng"), "Find original evidence on customer treatment/value and any counter-evidence."),
        _d("employees", "Employees", ("employee", "nhân viên", "người lao động"), "Find original evidence on employee treatment/value and any counter-evidence."),
        _d("suppliers", "Suppliers", ("supplier", "nhà cung cấp"), "Find original evidence on supplier relationships and any counter-evidence."),
        _d("shareholders", "Shareholders", ("shareholder", "cổ đông"), "Find original evidence on shareholder treatment and capital stewardship."),
        _d("business_partners", "Business partners", ("business partner", "partner", "đối tác"), "Find original evidence on partner relationships and any counter-evidence."),
        _d("other_stakeholders", "Other stakeholders", ("community", "cộng đồng", "sustainability", "phát triển bền vững"), "Find original evidence for other material stakeholders; do not substitute slogans for operating evidence."),
    ),
    "Q40": (
        _d("continuous_improvement", "Continuous improvement", ("continuous improvement", "cải tiến liên tục", "kaizen", "lean", "operational excellence", "nâng cao hiệu quả"), "Verify repeatable day-to-day improvement practices from dated evidence."),
        _d("strategic_plan", "Strategic plan / transformation", ("strategic plan", "kế hoạch chiến lược", "strategy", "chiến lược", "transformation", "chuyển đổi"), "Verify strategic-plan or transformational-bet evidence and observed follow-through."),
        _d("frontline_feedback", "Frontline feedback", ("frontline", "tuyến đầu", "employee feedback", "customer feedback", "phản hồi"), "Find evidence that frontline/customer feedback reaches operating decisions."),
        _d("adaptation", "Adaptation", ("adapt", "adaptation", "thích ứng", "điều chỉnh vận hành"), "Find examples of management adapting operations when facts changed."),
    ),
    "Q41": (
        _d("guidance_issued", "Guidance issued", ("earnings guidance", "revenue guidance", "profit guidance", "guidance", "forecast", "kế hoạch doanh thu", "kế hoạch lợi nhuận", "chỉ tiêu kinh doanh"), "Verify dated issued guidance and who issued it."),
        _d("guidance_revised_withdrawn", "Guidance revised / withdrawn", ("revised guidance", "withdraw guidance", "guidance withdrawn", "điều chỉnh kế hoạch", "rút kế hoạch"), "Verify revisions/withdrawals from original dated disclosures."),
        _d("guidance_actual_outcome", "Guidance versus actual outcome", ("actual", "thực hiện", "hoàn thành kế hoạch", "vượt kế hoạch", "không đạt kế hoạch"), "Pair explicit guidance with actual outcome; do not infer sandbagging/manipulation from arithmetic alone."),
    ),
    "Q42": (
        _d("central_control", "Central control", ("centralized", "centralised", "tập trung", "central control"), "Map decisions retained centrally and the supporting evidence."),
        _d("delegation_autonomy", "Delegation / autonomy", ("decentralized", "decentralised", "phân quyền", "ủy quyền", "uỷ quyền", "autonomy", "tự chủ"), "Map delegated authority/autonomy and escalation controls."),
        _d("business_unit_rights", "Business-unit decision rights", ("business unit", "đơn vị kinh doanh", "subsidiary", "công ty con", "decision authority", "thẩm quyền quyết định"), "Verify business-unit/customer-proximity decision rights."),
    ),
    "Q43": _q43_dimensions(),
    "Q44": (
        _d("internal_promotion_succession", "Internal promotion / succession", ("internal promotion", "promote from within", "succession", "kế nhiệm", "bổ nhiệm nội bộ", "thăng tiến nội bộ"), "Verify internal promotions/succession decisions and subsequent outcomes."),
        _d("external_hire", "External hire", ("external hire", "external candidate", "tuyển bên ngoài", "ứng viên bên ngoài"), "Verify material external hires and subsequent outcomes."),
        _d("selection_process", "Selection / talent development", ("selection process", "hiring", "recruitment", "talent development", "leadership development", "tuyển dụng", "phát triển lãnh đạo", "nhân tài"), "Verify how management selects/develops people, not résumé prestige alone."),
        _d("candor_challenge", "Candor / challenge", ("candor", "candid", "challenge management", "dissent", "phản biện", "thẳng thắn", "tranh luận"), "Find evidence that management hires/listens to candid people who can challenge decisions."),
        _d("observed_outcome", "Observed hiring outcome", ("promoted", "appointed", "bổ nhiệm", "performance after appointment", "outcome", "kết quả sau bổ nhiệm"), "Link important hiring/promotion decisions to observed operating/governance outcomes."),
    ),
    "Q45": (
        _d("cost_action", "Cost reduction / waste removal", ("cost cutting", "cost reduction", "cost saving", "cắt giảm chi phí", "tiết giảm chi phí", "tiết kiệm chi phí", "waste", "lãng phí"), "Verify specific cost actions and whether they removed waste/non-core spend."),
        _d("customer_employee_impact", "Customer / employee impact", ("customer impact", "employee impact", "khách hàng", "nhân viên", "người lao động"), "Verify whether cost actions harmed customers/employees or service capability."),
        _d("core_investment_preserved", "Core investment preserved", ("core investment", "reinvest", "innovation", "training", "r&d", "đầu tư cốt lõi", "đổi mới", "đào tạo"), "Verify whether management preserved/reinvested in core capabilities while cutting waste."),
        _d("restructuring_one_off", "Restructuring / one-off context", ("restructuring", "restructuring charge", "one-off", "one time", "tái cấu trúc", "chi phí một lần"), "Identify recurring 'one-off' restructuring and distinguish it from durable efficiency."),
    ),
    "Q46": tuple(
        _d(
            f"shearn_action_{idx + 1}",
            action,
            terms,
            f"Find dated original evidence for Shearn capital-allocation action: {action}.",
        )
        for idx, (action, terms) in enumerate((
            (ch8.CAPITAL_ALLOCATION_ACTIONS[0], ("reinvest", "reinvestment", "capex", "tái đầu tư", "đầu tư dự án")),
            (ch8.CAPITAL_ALLOCATION_ACTIONS[1], ("hold cash", "cash reserve", "cash balance", "tiền mặt", "dự trữ tiền mặt")),
            (ch8.CAPITAL_ALLOCATION_ACTIONS[2], ("dividend", "cổ tức")),
            (ch8.CAPITAL_ALLOCATION_ACTIONS[3], ("buyback", "share repurchase", "stock repurchase", "mua lại cổ phiếu", "cổ phiếu quỹ")),
            (ch8.CAPITAL_ALLOCATION_ACTIONS[4], ("acquisition", "m&a", "merger", "mua bán sáp nhập", "thâu tóm")),
        ))
    ) + (
        _d("discipline_hurdle_context", "Discipline / hurdle evidence (context only)", ("hurdle rate", "irr", "roic", "return threshold", "tỷ suất sinh lời yêu cầu", "phân bổ vốn"), "Find explicit hurdle/discipline evidence; this is context, not a sixth Shearn action.", source_locked=False),
    ),
    "Q47": (
        _d("authorization_program", "Authorization / program", ("repurchase authorization", "repurchase program", "buyback program", "phương án mua lại", "kế hoạch mua lại"), "Verify explicit buyback authorization/program from original disclosure."),
        _d("execution_shares_cash", "Execution / shares / cash", ("shares repurchased", "cash spent on repurchase", "share repurchase", "stock repurchase", "mua lại cổ phiếu", "mua cổ phiếu quỹ", "cổ phiếu quỹ"), "Verify actual execution, shares and cash; share-count decline alone does not qualify."),
        _d("price_valuation", "Price / valuation context", ("average repurchase price", "repurchase price", "giá mua lại", "valuation", "định giá"), "Verify repurchase price and contemporaneous valuation rationale/context."),
        _d("liquidity_cash_context", "Liquidity / cash context", ("liquidity", "cash context", "cash balance", "thanh khoản", "tiền mặt"), "Verify liquidity/cash context around the repurchase decision."),
    ),
}


COVERAGE_COLUMNS = [
    "Question",
    "Dimension Key",
    "Dimension",
    "Source Locked",
    "Candidates",
    "A — Official",
    "Manager-scoped Candidates",
    "Coverage Status",
    "Next Action",
    "Boundary",
]

QUESTION_SUMMARY_COLUMNS = [
    "Question",
    "Dimensions Required",
    "Dimensions Covered",
    "Dimensions Open",
    "Manager Scope Required",
    "Manager-scoped Candidates",
    "Status",
    "Boundary",
]


def _safe(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _candidate_text(row: pd.Series) -> str:
    return _safe(" ".join((
        _safe(row.get("Subtopic")),
        _safe(row.get("Source Title")),
        _safe(row.get("Evidence Text / Reference")),
    ))).casefold()


def _candidate_subset(candidates: pd.DataFrame, question: str) -> pd.DataFrame:
    if not isinstance(candidates, pd.DataFrame) or candidates.empty or "Question" not in candidates.columns:
        return pd.DataFrame()
    return candidates[candidates["Question"].astype(str).eq(question)].copy()


def _dimension_matches(sub: pd.DataFrame, dimension: CoverageDimension) -> pd.DataFrame:
    if sub.empty:
        return sub
    mask = sub.apply(
        lambda row: any(term.casefold() in _candidate_text(row) for term in dimension.terms),
        axis=1,
    )
    return sub[mask].copy()


def build_dimension_coverage(candidates: pd.DataFrame) -> pd.DataFrame:
    """Return question/dimension evidence coverage without producing a score.

    Candidate counts are research coverage counts only. They do not imply that a dimension is true,
    favorable, verified, or sufficient for an investment conclusion.
    """
    rows: list[dict[str, Any]] = []
    for question in ch8.QUESTION_KEYS:
        sub = _candidate_subset(candidates, question)
        for dimension in QUESTION_DIMENSIONS[question]:
            matched = _dimension_matches(sub, dimension)
            grades = matched.get("Source Grade", pd.Series(dtype="object")).astype(str) if not matched.empty else pd.Series(dtype="object")
            manager_ids = matched.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str) if not matched.empty else pd.Series(dtype="object")
            managers = matched.get("Manager", pd.Series(dtype="object")).fillna("").astype(str) if not matched.empty else pd.Series(dtype="object")
            manager_scoped = int(((manager_ids.str.strip() != "") | (managers.str.strip() != "")).sum()) if not matched.empty else 0
            a_count = int(grades.str.startswith("A —").sum()) if not grades.empty else 0
            if matched.empty:
                status = "Open — subtopic evidence gap"
            elif a_count == 0:
                status = "Open — subtopic source-quality gap"
            else:
                status = "Candidate coverage — analyst verify"
            rows.append({
                "Question": question,
                "Dimension Key": dimension.key,
                "Dimension": dimension.label,
                "Source Locked": "Yes" if dimension.source_locked else "No — context only",
                "Candidates": int(len(matched)),
                "A — Official": a_count,
                "Manager-scoped Candidates": manager_scoped,
                "Coverage Status": status,
                "Next Action": dimension.next_action,
                "Boundary": BOUNDARY,
            })
    return pd.DataFrame(rows, columns=COVERAGE_COLUMNS)


def build_question_coverage_summary(candidates: pd.DataFrame, manager_reference: pd.DataFrame | None = None) -> pd.DataFrame:
    coverage = build_dimension_coverage(candidates)
    manager_empty = not isinstance(manager_reference, pd.DataFrame) or manager_reference.empty
    rows: list[dict[str, Any]] = []
    for question in ch8.QUESTION_KEYS:
        qcov = coverage[(coverage["Question"] == question) & (coverage["Source Locked"] == "Yes")]
        required = int(len(qcov))
        covered = int(qcov["Coverage Status"].eq("Candidate coverage — analyst verify").sum())
        open_count = required - covered
        sub = _candidate_subset(candidates, question)
        manager_ids = sub.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str) if not sub.empty else pd.Series(dtype="object")
        managers = sub.get("Manager", pd.Series(dtype="object")).fillna("").astype(str) if not sub.empty else pd.Series(dtype="object")
        manager_scoped = int(((manager_ids.str.strip() != "") | (managers.str.strip() != "")).sum()) if not sub.empty else 0
        manager_required = question in MANAGER_SCOPED_QUESTIONS
        if open_count:
            status = "Open — dimension coverage gaps"
        elif manager_required and (manager_empty or manager_scoped == 0):
            status = "Open — manager-scoped evidence gap"
        else:
            status = "Candidate dimension coverage — analyst verify"
        rows.append({
            "Question": question,
            "Dimensions Required": required,
            "Dimensions Covered": covered,
            "Dimensions Open": open_count,
            "Manager Scope Required": manager_required,
            "Manager-scoped Candidates": manager_scoped,
            "Status": status,
            "Boundary": BOUNDARY,
        })
    return pd.DataFrame(rows, columns=QUESTION_SUMMARY_COLUMNS)


def enhanced_research_gaps(candidates: pd.DataFrame, manager_reference: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build evidence, source-quality, dimension and manager-scope gaps for Q39-Q47.

    The result deliberately stays in Chapter 8's existing Research Gap schema so the current
    analyst workspace can persist/render it without a parallel storage stack.
    """
    rows: list[dict[str, Any]] = []
    manager_empty = not isinstance(manager_reference, pd.DataFrame) or manager_reference.empty

    for question in ch8.QUESTION_KEYS:
        sub = _candidate_subset(candidates, question)
        if sub.empty:
            rows.append({
                "Question": question,
                "Manager ID": "",
                "Manager": "",
                "Research Gap": "No usable evidence candidate found in this run.",
                "Materiality": "Analyst decide",
                "Next Action": "Research dated original company/exchange/regulator sources for this question; keep Unknown until evidence is verified.",
                "Status": "Open — evidence gap",
                "Analyst Note": "",
            })
        elif not sub.get("Source Grade", pd.Series(dtype="object")).astype(str).str.startswith("A —").any():
            rows.append({
                "Question": question,
                "Manager ID": "",
                "Manager": "",
                "Research Gap": "No A-quality company/exchange/regulator evidence candidate yet.",
                "Materiality": "Analyst decide",
                "Next Action": "Replace/confirm secondary candidates with original company, exchange or regulator evidence where available.",
                "Status": "Open — source-quality gap",
                "Analyst Note": "",
            })

        qcov = build_dimension_coverage(candidates)
        qcov = qcov[(qcov["Question"] == question) & (qcov["Coverage Status"] != "Candidate coverage — analyst verify")]
        for _, gap in qcov.iterrows():
            context_note = " Context-only dimension; not part of source-locked completion." if gap["Source Locked"] != "Yes" else ""
            rows.append({
                "Question": question,
                "Manager ID": "",
                "Manager": "",
                "Research Gap": f"Dimension/subtopic open: {gap['Dimension']}.{context_note}",
                "Materiality": "Analyst decide",
                "Next Action": _safe(gap["Next Action"]),
                "Status": "Open — subtopic source-quality gap" if "source-quality" in str(gap["Coverage Status"]) else "Open — subtopic gap",
                "Analyst Note": "",
            })

        if question in MANAGER_SCOPED_QUESTIONS:
            manager_ids = sub.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str) if not sub.empty else pd.Series(dtype="object")
            managers = sub.get("Manager", pd.Series(dtype="object")).fillna("").astype(str) if not sub.empty else pd.Series(dtype="object")
            manager_scoped = int(((manager_ids.str.strip() != "") | (managers.str.strip() != "")).sum()) if not sub.empty else 0
            if manager_empty:
                rows.append({
                    "Question": question,
                    "Manager ID": "",
                    "Manager": "",
                    "Research Gap": f"{MANAGER_SOURCE_LABEL} is empty/unavailable, so manager-targeted research cannot be reliably scoped.",
                    "Materiality": "High",
                    "Next Action": "Confirm manager identities in Chapter 7 first, then rerun Chapter 8 research; do not create replacement manager IDs in Chapter 8.",
                    "Status": "Open — manager identity gap",
                    "Analyst Note": "",
                })
            elif manager_scoped == 0:
                rows.append({
                    "Question": question,
                    "Manager ID": "",
                    "Manager": "",
                    "Research Gap": "Chapter 7 manager master exists, but no candidate for this manager-scoped question is tied to a confirmed Chapter 7 manager.",
                    "Materiality": "High",
                    "Next Action": "Research the confirmed Chapter 7 CEO/CFO/management names explicitly and preserve their existing Manager IDs when promoting evidence.",
                    "Status": "Open — manager-scoped evidence gap",
                    "Analyst Note": "",
                })

    frame = pd.DataFrame(rows, columns=ch8.RESEARCH_GAP_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["Question", "Research Gap", "Status"], keep="first").reset_index(drop=True)


def validate_source_locks() -> dict[str, Any]:
    q43 = QUESTION_DIMENSIONS["Q43"]
    q46_locked = tuple(x.label for x in QUESTION_DIMENSIONS["Q46"] if x.source_locked)
    q46_context = tuple(x.label for x in QUESTION_DIMENSIONS["Q46"] if not x.source_locked)
    return {
        "q43_dimension_count": len(q43),
        "q43_keys": tuple(x.key for x in q43),
        "q46_source_locked_count": len(q46_locked),
        "q46_source_locked_actions": q46_locked,
        "q46_context_dimensions": q46_context,
        "q47_share_count_is_proof": False,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
    }


__all__ = [
    "BOUNDARY",
    "COVERAGE_COLUMNS",
    "MANAGER_SCOPED_QUESTIONS",
    "QUESTION_DIMENSIONS",
    "QUESTION_SUMMARY_COLUMNS",
    "Q43_TERM_MAP",
    "CoverageDimension",
    "build_dimension_coverage",
    "build_question_coverage_summary",
    "enhanced_research_gaps",
    "validate_source_locks",
]
