from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CH3 = ROOT / "modules" / "deep_company_analysis" / "chapter3.py"
TEST = ROOT / "modules" / "deep_company_analysis" / "test_chapter3.py"
PAGE_SUPPORT = ROOT / "modules" / "deep_company_analysis" / "chapter3_page_support.py"
CONTEXT = ROOT / "docs" / "CONTEXT_DEEP_COMPANY_ANALYSIS_CHAPTER3.md"
WORKFLOW = ROOT / ".github" / "workflows" / "deep-company-analysis.yml"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Patch anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_chapter3() -> None:
    text = CH3.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''CORE_CUSTOMER_COLUMNS = [
    "Customer Segment",
    "Customer type",
    "Who pays?",
    "Who uses?",
    "Main need / job-to-be-done",
    "Purchase criteria",
    "Price sensitivity",
    "Revenue / profit relevance",
    "Evidence",
]''',
        '''CORE_CUSTOMER_COLUMNS = [
    "Customer Segment",
    "Customer type",
    "Buyer / Decision maker",
    "Who pays?",
    "Who uses?",
    "Why they buy",
    "Main need / job-to-be-done",
    "Purchase criteria",
    "Price sensitivity",
    "Revenue Relevance",
    "Profit Relevance",
    "Evidence",
]''',
        "Q7 core customer columns",
    )

    anchor = '''PAIN_COLUMNS = [
    "Customer Segment",
    "Pain / Need",
    "Consequence if unsolved",
    "Solution / Value delivered",
    "Alternative workaround",
    "Evidence",
]
'''
    replacement = anchor + '''
DEPENDENCY_TABLE_COLUMNS = [
    "Customer Segment",
    "Product / Service",
    "Dependency Class",
    "Can defer?",
    "How long?",
    "Alternatives / Substitutes",
    "Consequence if stopped",
    "Evidence",
]

DISAPPEARANCE_COLUMNS = [
    "Customer Segment",
    "Immediate Alternative",
    "Time to Replace",
    "Switching Cost",
    "Operational Disruption",
    "Customer Evidence",
]

CUSTOMER_INTERVIEW_COLUMNS = [
    "Date",
    "Company / Person",
    "Role",
    "Customer Segment",
    "Q Covered",
    "Key Insight",
    "Confidence",
    "Evidence / Note",
]

EVIDENCE_MATRIX_COLUMNS = [
    "Claim",
    "Q",
    "Layer",
    "Source",
    "Source date",
    "Evidence text",
    "Status",
    "Analyst note",
]
'''
    text = replace_once(text, anchor, replacement, "approved Chapter 3 table schemas")

    text = replace_once(
        text,
        '''        "q11": {
            "feedback_mechanisms": "",
            "satisfaction_metrics": "",
            "management_proximity": "",
            "field_immersion": "",
            "customer_metrics_used": "",
            "independent_indicators": "",
            "customer_orientation_summary": "",
            "evidence": "",
        },''',
        '''        "q11": {
            "feedback_mechanisms": "",
            "satisfaction_metrics": "",
            "service_quality": "",
            "fair_treatment": "",
            "management_proximity": "",
            "field_immersion": "",
            "customer_metrics_used": "",
            "independent_indicators": "",
            "customer_orientation_summary": "",
            "evidence": "",
        },''',
        "Q11 approved buckets",
    )

    text = replace_once(
        text,
        '''        "q9": {
            "sales_ease_status": "Unknown",
            "sales_motion": "",
            "sales_cycle": "",
            "trial_demo": "",
            "pressure_tactics": "",
            "sales_friction_summary": "",
            "evidence": "",
        },''',
        '''        "q9": {
            "sales_ease_status": "Unknown",
            "sales_motion": "",
            "sales_cycle": "",
            "trial_demo": "",
            "pressure_tactics": "",
            "discount_dependency": "",
            "inbound_demand": "",
            "repeat_purchase_friction": "",
            "sales_friction_summary": "",
            "evidence": "",
        },''',
        "Q9 approved fields",
    )

    text = replace_once(
        text,
        '''            "retention_investments": "",
            "renewal_incentives": "",
            "retention_trend": "",''',
        '''            "retention_investments": "",
            "renewal_incentives": "",
            "customer_success_service": "",
            "cross_sell_existing": "",
            "customer_selection_quality": "",
            "retention_trend": "",''',
        "Q10 approved fields",
    )

    text = replace_once(
        text,
        '''        "q13": {
            "dependency_class": "Unknown",
            "dependency_reason": "",
            "deferral_period": "",
            "consequence_if_stopped": "",
            "substitutes": "",
            "evidence": "",
        },''',
        '''        "q13": {
            "dependency_table": [],
            "dependency_class": "Unknown",
            "dependency_reason": "",
            "deferral_period": "",
            "consequence_if_stopped": "",
            "substitutes": "",
            "evidence": "",
        },''',
        "Q13 dependency table",
    )

    text = replace_once(
        text,
        '''        "q14": {
            "impact_level": "Unknown",
            "immediate_substitute": "",
            "switching_time": "",
            "switching_cost": "",
            "operational_disruption": "",
            "disappearance_conclusion": "",
            "evidence": "",
        },
        "research_gaps": "",
        "analyst_summary": "",''',
        '''        "q14": {
            "disappearance_table": [],
            "impact_level": "Unknown",
            "immediate_substitute": "",
            "switching_time": "",
            "switching_cost": "",
            "operational_disruption": "",
            "disappearance_conclusion": "",
            "evidence": "",
        },
        "customer_interviews": [],
        "evidence_matrix": [],
        "customer_strengths": "",
        "customer_risks": "",
        "most_important_evidence": "",
        "research_gaps": "",
        "analyst_summary": "",''',
        "approved top-level customer intelligence fields",
    )

    text = replace_once(
        text,
        '''            [_nonempty_table(q8.get("concentration_table")), _has_text(q8.get("concentration_trend"))],''',
        '''            [_nonempty_table(q8.get("concentration_table")), _has_text(q8.get("concentration_trend"))],''',
        "no-op q8 status anchor",
    ) if False else text

    text = replace_once(
        text,
        '''                _has_text(q9.get("pressure_tactics")),
                _has_text(q9.get("evidence")),''',
        '''                _has_text(q9.get("pressure_tactics")),
                _has_text(q9.get("discount_dependency")),
                _has_text(q9.get("inbound_demand")),
                _has_text(q9.get("repeat_purchase_friction")),
                _has_text(q9.get("evidence")),''',
        "Q9 status optional fields",
    )

    text = replace_once(
        text,
        '''                _has_text(q10.get("renewal_incentives")),
                _has_text(q10.get("evidence")),''',
        '''                _has_text(q10.get("renewal_incentives")),
                _has_text(q10.get("customer_success_service")),
                _has_text(q10.get("cross_sell_existing")),
                _has_text(q10.get("customer_selection_quality")),
                _has_text(q10.get("evidence")),''',
        "Q10 status optional fields",
    )

    text = replace_once(
        text,
        '''            "field_immersion",
            "customer_metrics_used",''',
        '''            "field_immersion",
            "service_quality",
            "fair_treatment",
            "customer_metrics_used",''',
        "Q11 status evidence fields",
    )

    text = replace_once(
        text,
        '''                _has_text(q13.get("deferral_period")),''',
        '''                _nonempty_table(q13.get("dependency_table")),
                _has_text(q13.get("deferral_period")),''',
        "Q13 status dependency table",
    )

    text = replace_once(
        text,
        '''                _has_text(q14.get("immediate_substitute")),''',
        '''                _nonempty_table(q14.get("disappearance_table")),
                _has_text(q14.get("immediate_substitute")),''',
        "Q14 status disappearance table",
    )

    text = replace_once(
        text,
        '''    df = pd.DataFrame(rows)
    for column in columns:''',
        '''    df = pd.DataFrame(rows)
    # Backward compatibility with the unapproved prototype that used one combined relevance field.
    if columns == CORE_CUSTOMER_COLUMNS and "Revenue / profit relevance" in df.columns:
        if "Revenue Relevance" not in df.columns:
            df["Revenue Relevance"] = df["Revenue / profit relevance"].map(
                lambda value: f"Legacy combined field: {value}" if str(value or "").strip() else ""
            )
        if "Profit Relevance" not in df.columns:
            df["Profit Relevance"] = ""
    for column in columns:''',
        "legacy Q7 relevance migration",
    )

    insert_after = '''def _df_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    clean = df.copy().fillna("")
    rows: list[dict[str, Any]] = []
    for row in clean.to_dict(orient="records"):
        if any(_has_text(v) for v in row.values()):
            rows.append(row)
    return rows
'''
    helpers = insert_after + '''

def evidence_layer_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = {
        "A — Company Disclosure": 0,
        "B — Independent / Customer-side": 0,
        "C — Analyst Fieldwork": 0,
    }
    matrix = payload.get("evidence_matrix", []) if isinstance(payload, dict) else []
    if isinstance(matrix, list):
        for row in matrix:
            if not isinstance(row, dict):
                continue
            layer = str(row.get("Layer") or "").strip()
            for key in counts:
                if layer.lower().startswith(key[0].lower()) or layer == key:
                    counts[key] += 1
                    break
    interviews = payload.get("customer_interviews", []) if isinstance(payload, dict) else []
    if isinstance(interviews, list):
        counts["C — Analyst Fieldwork"] += sum(
            1 for row in interviews if isinstance(row, dict) and any(_has_text(v) for v in row.values())
        )
    return counts


def conflicting_evidence_count(payload: dict[str, Any]) -> int:
    matrix = payload.get("evidence_matrix", []) if isinstance(payload, dict) else []
    if not isinstance(matrix, list):
        return 0
    return sum(
        1
        for row in matrix
        if isinstance(row, dict)
        and any(token in str(row.get("Status") or "").lower() for token in ("conflict", "mâu thuẫn", "mau thuan"))
    )
'''
    text = replace_once(text, insert_after, helpers, "evidence layer helpers")

    old_intro = '''**Mục đích:** chuyển góc nhìn từ sản phẩm/doanh nghiệp sang **khách hàng thực sự**. Chương này không hỏi analyst có thích sản phẩm hay không; nó buộc analyst xác định ai là khách hàng cốt lõi, mức tập trung, độ khó bán hàng, khả năng giữ chân, mức độ định hướng khách hàng, vấn đề doanh nghiệp giải quyết và mức độ khách hàng phụ thuộc vào sản phẩm/dịch vụ.

**8 câu hỏi của Chương 3:** Q7 khách hàng cốt lõi; Q8 tập trung/đa dạng khách hàng; Q9 dễ hay khó thuyết phục mua; Q10 retention; Q11 dấu hiệu customer-oriented; Q12 customer pain; Q13 mức độ phụ thuộc; Q14 điều gì xảy ra nếu doanh nghiệp biến mất ngày mai.

**Guardrail:** Không suy diễn customer concentration, retention/churn, NPS, revenue share hay switching cost khi nguồn không công bố. `Unknown` là kết quả hợp lệ và phải được chuyển thành Research Gap.'''
    new_intro = '''**Mục đích:** chuyển góc nhìn từ sản phẩm/doanh nghiệp sang **khách hàng thực sự**. Câu hỏi trung tâm không phải “Tôi có thích sản phẩm này không?” mà là **“Khách hàng thực sự có cần/muốn sản phẩm này không, tại sao họ mua và vì sao họ tiếp tục mua?”**

**8 câu hỏi của Chương 3:** Q7 khách hàng cốt lõi; Q8 tập trung/đa dạng khách hàng; Q9 dễ hay khó thuyết phục mua; Q10 retention; Q11 dấu hiệu customer-oriented; Q12 customer pain; Q13 mức độ phụ thuộc; Q14 điều gì xảy ra nếu doanh nghiệp biến mất ngày mai.

**Ba lớp evidence:** A — Company Disclosure (BCTN/BCTC/IR); B — Independent / Customer-side; C — Analyst Fieldwork / Customer Interview. Nếu evidence mâu thuẫn, giữ cả hai phía và đánh dấu `Conflicting` để analyst xử lý.

**Q7 có hai field kinh tế bổ sung:** `Revenue Relevance` = tỷ trọng/đóng góp doanh thu của nhóm khách hàng nếu có evidence; `Profit Relevance` = đóng góp lợi nhuận/biên lợi nhuận nếu có disclosure. Hai field này **không bắt buộc** và không được suy diễn từ segment/geography.

**Guardrail:** Không suy diễn customer concentration, retention/churn, NPS, revenue share, profit contribution hay switching cost khi nguồn không công bố. `Unknown` là kết quả hợp lệ và phải được chuyển thành Research Gap. AI/Data = Research Assistant; người dùng = Investment Analyst.'''
    text = replace_once(text, old_intro, new_intro, "approved Chapter 3 guide")

    text = replace_once(
        text,
        '''    _status_summary(record)

    q7 = record["q7"]''',
        '''    _status_summary(record)

    layer_counts = evidence_layer_counts(record)
    conflict_count = conflicting_evidence_count(record)
    st.markdown("### Customer Evidence Dashboard — analyst-verified")
    ed1, ed2, ed3, ed4 = st.columns(4)
    ed1.metric("A — Company Disclosure", layer_counts["A — Company Disclosure"])
    ed2.metric("B — Independent / Customer-side", layer_counts["B — Independent / Customer-side"])
    ed3.metric("C — Analyst Fieldwork", layer_counts["C — Analyst Fieldwork"])
    ed4.metric("Conflicting Evidence", conflict_count)
    st.caption("Dashboard này đếm Evidence Matrix + Customer Interview đã lưu. Research Assistant candidates được hiển thị riêng ở panel phía trên và chỉ trở thành analyst-verified khi anh đưa vào hồ sơ/evidence matrix.")
    if conflict_count:
        st.warning("⚠ Có evidence mâu thuẫn. Không tự chọn một phía; mở nguồn và ghi Analyst note trước khi kết luận.")

    q7 = record["q7"]''',
        "customer evidence dashboard",
    )

    text = replace_once(
        text,
        '''    st.caption("Tách rõ người trả tiền, người sử dụng và nhóm khách hàng tạo economics quan trọng. Không đồng nhất 'người dùng' với 'người mua' nếu mô hình có trung gian.")''',
        '''    st.caption("Tách rõ buyer, người trả tiền và người sử dụng. Revenue Relevance và Profit Relevance chỉ nhập khi có disclosure/evidence; không bắt buộc và không suy diễn từ segment/geography.")''',
        "Q7 approved caption",
    )

    text = replace_once(
        text,
        '''    pressure_tactics = st.text_area("High-pressure selling / promotion dependency — có bằng chứng hay không?", value=q9.get("pressure_tactics", ""), height=80, key=f"ch3_q9_pressure_{ticker}")
    sales_friction_summary = st.text_area''',
        '''    pressure_tactics = st.text_area("High-pressure selling / promotion dependency — có bằng chứng hay không?", value=q9.get("pressure_tactics", ""), height=80, key=f"ch3_q9_pressure_{ticker}")
    c93, c94 = st.columns(2)
    discount_dependency = c93.text_area("Discount dependency — có phải giảm giá mạnh mới bán được?", value=q9.get("discount_dependency", ""), height=80, key=f"ch3_q9_discount_{ticker}")
    inbound_demand = c94.text_area("Customer pull — khách hàng chủ động tìm đến hay sales phải tạo nhu cầu?", value=q9.get("inbound_demand", ""), height=80, key=f"ch3_q9_inbound_{ticker}")
    repeat_purchase_friction = st.text_area("Repeat purchase — bán lại cho khách hàng cũ dễ hơn/khó hơn bán mới như thế nào?", value=q9.get("repeat_purchase_friction", ""), height=80, key=f"ch3_q9_repeat_{ticker}")
    sales_friction_summary = st.text_area''',
        "Q9 approved UI fields",
    )

    text = replace_once(
        text,
        '''    renewal_incentives = st.text_area("Sales / channel incentives có khuyến khích renewal/retention không?", value=q10.get("renewal_incentives", ""), height=80, key=f"ch3_q10_incentive_{ticker}")
    retention_trend = st.text_area''',
        '''    renewal_incentives = st.text_area("Sales / channel incentives có khuyến khích renewal/retention không?", value=q10.get("renewal_incentives", ""), height=80, key=f"ch3_q10_incentive_{ticker}")
    customer_success_service = st.text_area("Customer success / service — doanh nghiệp hỗ trợ khách hàng cũ như thế nào?", value=q10.get("customer_success_service", ""), height=80, key=f"ch3_q10_success_{ticker}")
    cross_sell_existing = st.text_area("Cross-sell / upsell trong khách hàng hiện hữu — có evidence hay không?", value=q10.get("cross_sell_existing", ""), height=80, key=f"ch3_q10_crosssell_{ticker}")
    customer_selection_quality = st.text_area("Doanh nghiệp có chủ động chọn nhóm khách hàng dễ giữ chân/profitable hơn không?", value=q10.get("customer_selection_quality", ""), height=80, key=f"ch3_q10_selection_{ticker}")
    retention_trend = st.text_area''',
        "Q10 approved UI fields",
    )

    text = replace_once(
        text,
        '''    field_immersion = st.text_area("Field immersion / customer research — quan sát người dùng, đi thị trường, store/field visit...", value=q11.get("field_immersion", ""), height=90, key=f"ch3_q11_field_{ticker}")
    customer_metrics_used = st.text_area''',
        '''    service_quality = st.text_area("Service Quality — năng lực support/phục vụ, knowledgeable staff, response quality...", value=q11.get("service_quality", ""), height=80, key=f"ch3_q11_service_{ticker}")
    fair_treatment = st.text_area("Fair Treatment — pricing/refund/fee/policy có đối xử công bằng, không lợi dụng khách hàng?", value=q11.get("fair_treatment", ""), height=80, key=f"ch3_q11_fair_{ticker}")
    field_immersion = st.text_area("Field immersion / customer research — quan sát người dùng, đi thị trường, store/field visit...", value=q11.get("field_immersion", ""), height=90, key=f"ch3_q11_field_{ticker}")
    customer_metrics_used = st.text_area''',
        "Q11 approved evidence buckets",
    )

    text = replace_once(
        text,
        '''    st.caption("Dùng đúng continuum của Shearn: Need to have → Need to have, but not immediately → Nice to have, but not critical. Không mặc định discretionary = business xấu.")
    dependency_class = st.selectbox''',
        '''    st.caption("Dùng đúng continuum của Shearn: Need to have → Need to have, but not immediately → Nice to have, but not critical. Đánh giá theo customer/product trước, rồi mới viết kết luận tổng hợp. Không mặc định discretionary = business xấu.")
    dependency_df = st.data_editor(
        _rows_to_df(q13.get("dependency_table"), DEPENDENCY_TABLE_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key=f"ch3_q13_table_{ticker}",
    )
    dependency_class = st.selectbox''',
        "Q13 per-customer dependency table UI",
    )

    text = replace_once(
        text,
        '''    st.markdown("### Q14. Nếu doanh nghiệp biến mất ngày mai, khách hàng sẽ bị ảnh hưởng thế nào?")
    impact_level = st.selectbox''',
        '''    st.markdown("### Q14. Nếu doanh nghiệp biến mất ngày mai, khách hàng sẽ bị ảnh hưởng thế nào?")
    disappearance_df = st.data_editor(
        _rows_to_df(q14.get("disappearance_table"), DISAPPEARANCE_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key=f"ch3_q14_table_{ticker}",
    )
    impact_level = st.selectbox''',
        "Q14 disappearance table UI",
    )

    text = replace_once(
        text,
        '''    q14_evidence = st.text_area("Evidence Q14", value=q14.get("evidence", ""), height=80, key=f"ch3_q14_evidence_{ticker}")

    research_gaps = st.text_area(''',
        '''    q14_evidence = st.text_area("Evidence Q14", value=q14.get("evidence", ""), height=80, key=f"ch3_q14_evidence_{ticker}")

    st.markdown("### 🎤 Customer / Channel Interview Log")
    st.caption("Shearn khuyến nghị nói chuyện với khách hàng thật. Log này là Layer C — Analyst Fieldwork và không được AI tự tạo.")
    interview_df = st.data_editor(
        _rows_to_df(record.get("customer_interviews"), CUSTOMER_INTERVIEW_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key=f"ch3_interviews_{ticker}",
    )
    with st.expander("Gợi ý câu hỏi phỏng vấn khách hàng/kênh", expanded=False):
        st.markdown("""
- Tại sao anh/chị chọn sản phẩm/dịch vụ này?
- Có lựa chọn thay thế nào và vì sao chưa chuyển?
- Điều gì khiến anh/chị đổi supplier/nhà cung cấp?
- Nếu giá tăng thì hành vi mua sẽ thay đổi thế nào?
- Nếu doanh nghiệp này biến mất ngày mai, anh/chị sẽ làm gì?
        """)

    st.markdown("### 🧾 Evidence Matrix — Claim → Source → Verification")
    st.caption("Layer A = Company Disclosure; Layer B = Independent/Customer-side; Layer C = Analyst Fieldwork. Status nên dùng Verified / Unverified / Conflicting. Giữ evidence mâu thuẫn thay vì tự chọn một phía.")
    evidence_matrix_df = st.data_editor(
        _rows_to_df(record.get("evidence_matrix"), EVIDENCE_MATRIX_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key=f"ch3_evidence_matrix_{ticker}",
    )
    live_conflicts = sum(
        1
        for row in _df_to_rows(evidence_matrix_df)
        if any(token in str(row.get("Status") or "").lower() for token in ("conflict", "mâu thuẫn", "mau thuan"))
    )
    if live_conflicts:
        st.warning(f"⚠ Có {live_conflicts} evidence item đang Conflicting. Cần mở nguồn và ghi Analyst note trước khi dùng cho kết luận.")

    st.markdown("### Customer Perspective Summary")
    customer_strengths = st.text_area("Customer Strengths", value=record.get("customer_strengths", ""), height=90, key=f"ch3_strengths_{ticker}")
    customer_risks = st.text_area("Customer Risks", value=record.get("customer_risks", ""), height=90, key=f"ch3_risks_{ticker}")
    most_important_evidence = st.text_area("Most Important Customer Evidence — 3–5 evidence quan trọng nhất", value=record.get("most_important_evidence", ""), height=100, key=f"ch3_keyevidence_{ticker}")

    research_gaps = st.text_area(''',
        "approved interview/evidence matrix and summary sections",
    )

    text = replace_once(
        text,
        '''            "pressure_tactics": pressure_tactics,
            "sales_friction_summary": sales_friction_summary,''',
        '''            "pressure_tactics": pressure_tactics,
            "discount_dependency": discount_dependency,
            "inbound_demand": inbound_demand,
            "repeat_purchase_friction": repeat_purchase_friction,
            "sales_friction_summary": sales_friction_summary,''',
        "Q9 payload fields",
    )

    text = replace_once(
        text,
        '''            "retention_investments": retention_investments,
            "renewal_incentives": renewal_incentives,
            "retention_trend": retention_trend,''',
        '''            "retention_investments": retention_investments,
            "renewal_incentives": renewal_incentives,
            "customer_success_service": customer_success_service,
            "cross_sell_existing": cross_sell_existing,
            "customer_selection_quality": customer_selection_quality,
            "retention_trend": retention_trend,''',
        "Q10 payload fields",
    )

    text = replace_once(
        text,
        '''            "satisfaction_metrics": satisfaction_metrics,
            "management_proximity": management_proximity,
            "field_immersion": field_immersion,''',
        '''            "satisfaction_metrics": satisfaction_metrics,
            "service_quality": service_quality,
            "fair_treatment": fair_treatment,
            "management_proximity": management_proximity,
            "field_immersion": field_immersion,''',
        "Q11 payload fields",
    )

    text = replace_once(
        text,
        '''        "q13": {
            "dependency_class": dependency_class,''',
        '''        "q13": {
            "dependency_table": _df_to_rows(dependency_df),
            "dependency_class": dependency_class,''',
        "Q13 payload table",
    )

    text = replace_once(
        text,
        '''        "q14": {
            "impact_level": impact_level,''',
        '''        "q14": {
            "disappearance_table": _df_to_rows(disappearance_df),
            "impact_level": impact_level,''',
        "Q14 payload table",
    )

    text = replace_once(
        text,
        '''        "research_gaps": research_gaps,
        "analyst_summary": analyst_summary,''',
        '''        "customer_interviews": _df_to_rows(interview_df),
        "evidence_matrix": _df_to_rows(evidence_matrix_df),
        "customer_strengths": customer_strengths,
        "customer_risks": customer_risks,
        "most_important_evidence": most_important_evidence,
        "research_gaps": research_gaps,
        "analyst_summary": analyst_summary,''',
        "top-level approved payload fields",
    )

    CH3.write_text(text, encoding="utf-8")


def patch_page_support() -> None:
    text = PAGE_SUPPORT.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''from modules.deep_company_analysis.chapter3 import load_record, render_chapter3, save_record''',
        '''from modules.deep_company_analysis.chapter3 import conflicting_evidence_count, load_record, render_chapter3, save_record''',
        "page support conflict helper import",
    )

    old = '''def _evidence_table(rows) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=["Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu"])
    df = pd.DataFrame(rows)
    cols = [c for c in ("Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu", "Điểm phù hợp") if c in df.columns]
    return df[cols].head(12) if cols else pd.DataFrame()
'''
    new = '''def _evidence_layer(row: dict) -> str:
    group = str(row.get("Nhóm thông tin") or "").lower()
    url = str(row.get("Nguồn/URL") or "").lower()
    official_tokens = ("nguồn doanh nghiệp", "bctn", "bctc", "pdf chính thức", "official", "investor relations")
    if any(token in group for token in official_tokens) or "ducgiangchem.vn" in url:
        return "A — Company Disclosure"
    return "B — Independent / Customer-side"


def _evidence_table(rows) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=["Layer", "Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu"])
    df = pd.DataFrame(rows)
    df.insert(0, "Layer", [_evidence_layer(row) for row in rows])
    cols = [c for c in ("Layer", "Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu", "Điểm phù hợp") if c in df.columns]
    return df[cols].head(12) if cols else pd.DataFrame()
'''
    text = replace_once(text, old, new, "page support evidence layers")

    text = replace_once(
        text,
        '''        counts = []
        for question in ("q7", "q8", "q9", "q10", "q11", "q12", "q13", "q14"):
            counts.append(len(draft.get(question, {}).get("evidence", []) or []))''',
        '''        all_evidence_rows = []
        counts = []
        for question in ("q7", "q8", "q9", "q10", "q11", "q12", "q13", "q14"):
            rows = draft.get(question, {}).get("evidence", []) or []
            counts.append(len(rows))
            all_evidence_rows.extend(row for row in rows if isinstance(row, dict))
        unique_rows = {}
        for row in all_evidence_rows:
            key = (str(row.get("Nguồn/URL") or ""), str(row.get("Tiêu đề") or ""), str(row.get("Trích yếu") or ""))
            unique_rows[key] = row
        layer_a = sum(1 for row in unique_rows.values() if _evidence_layer(row).startswith("A"))
        layer_b = sum(1 for row in unique_rows.values() if _evidence_layer(row).startswith("B"))
        saved_record = load_record(ticker, company_name)
        layer_c = len(saved_record.get("customer_interviews", []) or [])
        conflicts = conflicting_evidence_count(saved_record)
        ecols = st.columns(4)
        ecols[0].metric("A — Company Disclosure", layer_a)
        ecols[1].metric("B — Independent/Customer-side", layer_b)
        ecols[2].metric("C — Analyst Fieldwork", layer_c)
        ecols[3].metric("Conflicting", conflicts)''',
        "assistant evidence layer dashboard",
    )
    PAGE_SUPPORT.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''            "Main need / job-to-be-done": "Nguyên liệu đầu vào hóa chất",
            "Evidence": "IR/BCTN",''',
        '''            "Buyer / Decision maker": "Bộ phận procurement / kỹ thuật",
            "Why they buy": "Cần nguyên liệu đạt specification",
            "Main need / job-to-be-done": "Nguyên liệu đầu vào hóa chất",
            "Revenue Relevance": "35% doanh thu nếu disclosure hỗ trợ",
            "Profit Relevance": "Chưa công bố",
            "Evidence": "IR/BCTN",''',
        "test Q7 approved fields",
    )

    marker = '''def test_customer_perspective_understood_requires_q7_and_q12(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = _complete_payload()
    payload["q12"]["pain_summary"] = ""
    assert ch3.question_statuses(payload)["Q12"] == "Partial"
    assert ch3.customer_perspective_status(payload) == "partial"
'''
    addition = marker + '''


def test_q7_revenue_and_profit_relevance_roundtrip_are_separate_fields(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = _complete_payload()
    row = payload["q7"]["core_customers"][0]
    row["Revenue Relevance"] = "35% doanh thu — source disclosed"
    row["Profit Relevance"] = "Unknown — không có disclosure"
    ch3.save_record(payload)
    loaded = ch3.load_record("DGC")
    saved = loaded["q7"]["core_customers"][0]
    assert saved["Revenue Relevance"] == "35% doanh thu — source disclosed"
    assert saved["Profit Relevance"] == "Unknown — không có disclosure"


def test_customer_interview_evidence_matrix_and_conflict_roundtrip(tmp_path, monkeypatch):
    _bind_db(tmp_path, monkeypatch)
    payload = _complete_payload()
    payload["customer_interviews"] = [{
        "Date": "2026-09-03",
        "Company / Person": "Khách hàng A",
        "Role": "Procurement",
        "Customer Segment": "Industrial",
        "Q Covered": "Q13/Q14",
        "Key Insight": "Có alternative nhưng cần qualification.",
        "Confidence": "Medium",
        "Evidence / Note": "Analyst interview",
    }]
    payload["evidence_matrix"] = [
        {"Claim": "Switching nhanh", "Q": "Q14", "Layer": "B — Independent / Customer-side", "Status": "Conflicting"},
        {"Claim": "Switching cần qualification", "Q": "Q14", "Layer": "A — Company Disclosure", "Status": "Verified"},
    ]
    payload["q13"]["dependency_table"] = [{
        "Customer Segment": "Industrial",
        "Product / Service": "Input chemical",
        "Dependency Class": "Need to have, but not immediately",
        "Evidence": "Interview + disclosure",
    }]
    payload["q14"]["disappearance_table"] = [{
        "Customer Segment": "Industrial",
        "Immediate Alternative": "Qualified supplier khác",
        "Time to Replace": "Cần xác minh",
        "Customer Evidence": "Interview",
    }]
    ch3.save_record(payload)
    loaded = ch3.load_record("DGC")
    assert len(loaded["customer_interviews"]) == 1
    assert len(loaded["q13"]["dependency_table"]) == 1
    assert len(loaded["q14"]["disappearance_table"]) == 1
    counts = ch3.evidence_layer_counts(loaded)
    assert counts["A — Company Disclosure"] == 1
    assert counts["B — Independent / Customer-side"] == 1
    assert counts["C — Analyst Fieldwork"] == 1
    assert ch3.conflicting_evidence_count(loaded) == 1


def test_legacy_combined_relevance_is_not_silently_split_into_profit():
    df = ch3._rows_to_df(
        [{"Customer Segment": "Legacy", "Revenue / profit relevance": "Old combined note"}],
        ch3.CORE_CUSTOMER_COLUMNS,
    )
    assert "Legacy combined field" in str(df.iloc[0]["Revenue Relevance"])
    assert df.iloc[0]["Profit Relevance"] == ""
'''
    text = replace_once(text, marker, addition, "approved Chapter 3 regression tests")
    TEST.write_text(text, encoding="utf-8")


def write_context() -> None:
    CONTEXT.write_text('''# Context — Deep Company Analysis Chapter 3 — APPROVED

## Approval status

**Approved by user on 2026-09-03.** This document is the source-of-truth design context for Chapter 3 of the Trecapital **Phân tích chuyên sâu doanh nghiệp** workspace.

Primary methodology: Michael Shearn, *The Investment Checklist: The Art of In-Depth Research*, Chapter 3 — **Understanding the Business—from the Customer Perspective**.

Project rule:

> **AI/Data = Research Assistant; user = Investment Analyst.**

Chapter 3 measures customer understanding and evidence completeness. It does **not** produce a Customer Score, BUY/HOLD/SELL or automatically modify the Chapter 1 Research Gate.

---

## 1. Chapter objective

Chapter 2 asks what the business does and how it makes money. Chapter 3 changes the viewpoint to the customer:

> Why do real customers buy, why do they continue buying, and how dependent are they on the product/service?

The analyst must not substitute personal product preference for actual customer evidence. `Unknown` is a valid result when evidence is insufficient.

---

## 2. Source questions Q7–Q14

7. **Who is the core customer of the business?** — Khách hàng cốt lõi của doanh nghiệp là ai?
8. **Is the customer base concentrated or diversified?** — Cơ sở khách hàng tập trung hay đa dạng?
9. **Is it easy or difficult to convince customers to buy the products or services?** — Dễ hay khó thuyết phục khách hàng mua?
10. **What is the customer retention rate for the business?** — Tỷ lệ giữ chân khách hàng là bao nhiêu?
11. **What are the signs a business is customer oriented?** — Dấu hiệu nào cho thấy doanh nghiệp định hướng khách hàng?
12. **What pain does the business alleviate for the customer?** — Doanh nghiệp giải quyết vấn đề/nỗi đau nào của khách hàng?
13. **To what degree is the customer dependent on the products or services from the business?** — Khách hàng phụ thuộc vào sản phẩm/dịch vụ đến mức nào?
14. **If the business disappeared tomorrow, what impact would this have on the customer base?** — Nếu doanh nghiệp biến mất ngày mai, khách hàng sẽ bị ảnh hưởng thế nào?

---

## 3. Chapter flow

```text
CUSTOMER EVIDENCE
      ↓
Q7  Core Customer
      ↓
Q8  Concentration
      ↓
Q9  Sales Friction
      ↓
Q10 Retention
      ↓
Q11 Customer Orientation
      ↓
Q12 Customer Pain
      ↓
Q13 Customer Dependency
      ↓
Q14 Disappearance Test
      ↓
Customer Perspective Summary
      ↓
Research Gaps / Questions to Verify
```

No automatic investment conclusion is generated.

---

## 4. Evidence architecture — three layers

### Layer A — Company Disclosure

- Annual reports / BCTN;
- financial statements / BCTC and notes;
- investor relations;
- company presentations;
- official website and product/service documents.

### Layer B — Independent / Customer-side

- customer-side material;
- industry publications;
- independent surveys;
- customer case studies;
- credible third-party evidence.

### Layer C — Analyst Fieldwork

- direct customer interviews;
- distributor/channel interviews;
- store/field visits;
- supplier or sales conversations;
- analyst observations.

Each material claim should be recordable as:

`Claim → Q → Layer → Source → Source date → Evidence text → Status → Analyst note`

Recommended evidence statuses:

- `Verified`;
- `Unverified`;
- `Conflicting`.

If evidence conflicts, the app must preserve both sides and show a warning. It must not automatically choose a side.

---

## 5. Q7 — Core Customer

### Approved Core Customer Map fields

- Customer Segment;
- Customer type;
- Buyer / Decision maker;
- Who pays?;
- Who uses?;
- Why they buy;
- Main need / job-to-be-done;
- Purchase criteria;
- Price sensitivity;
- **Revenue Relevance**;
- **Profit Relevance**;
- Evidence.

### Revenue Relevance — approved additional field

Purpose: record how economically important a customer/customer group is to revenue **only when evidence supports it**.

Examples of valid content:

- explicit customer-group revenue share;
- explicit major-customer revenue percentage;
- disclosed revenue attributable to a defined customer group.

Rules:

- optional field;
- blank/Unknown is valid;
- do not infer from geographic revenue;
- do not relabel business segment revenue as customer revenue unless the segment truly maps to the customer group and the disclosure supports that mapping;
- do not estimate a number merely to complete the table.

### Profit Relevance — approved additional field

Purpose: record profit contribution, margin economics or profitability relevance of the customer/customer group **only when disclosure/evidence exists**.

Rules:

- optional field;
- blank/Unknown is the normal outcome when profitability by customer is not disclosed;
- never infer profit contribution from revenue share alone;
- never assume export/customer segment profitability without source evidence;
- qualitative evidence is allowed if clearly labeled as qualitative rather than a calculated percentage.

These are **Trecapital implementation fields**, not named scoring fields from Shearn. They exist to distinguish customer count/revenue importance from actual economic importance.

### Q7 analyst conclusions

- Core customer summary;
- Why this is the core customer rather than merely one customer segment.

Research Assistant may surface evidence but does not decide the core customer.

---

## 6. Q8 — Customer Concentration

Fields:

- Customer / Group;
- Revenue share % if explicitly disclosed;
- Period;
- Trend;
- Bargaining power;
- Dependency / loss impact;
- Evidence;
- analyst concentration assessment: `Unknown / Diversified / Moderately concentrated / Concentrated`;
- concentration trend and conclusion.

Guardrails:

- no concentration inference from geographic/segment revenue;
- no automatic concentration classification;
- Shearn's US 10-K 10% discussion is methodology context, **not a Vietnam disclosure rule**;
- historical trend should be tracked when available.

---

## 7. Q9 — Sales Friction

Fields:

- Sales motion: direct / distributor / dealer / tender / online / contract / subscription / other;
- sales cycle / decision process;
- trial/demo/education/qualification requirement;
- high-pressure selling / promotion dependency;
- discount dependency;
- customer pull — whether customers proactively seek the product;
- repeat-purchase friction vs new-customer sale;
- evidence;
- analyst assessment: `Unknown / Easy / Moderate / Hard`;
- analyst conclusion: demand from product merit/need vs sales effort.

Research Assistant may surface evidence but never chooses Easy/Moderate/Hard.

---

## 8. Q10 — Customer Retention

Retention evidence status:

- Unknown;
- Disclosed metric;
- Proxy only;
- Not disclosed;
- Not meaningful for this business model.

Fields:

- business model;
- retention rate + period if explicitly disclosed;
- churn rate if explicitly disclosed;
- loyalty/repeat-customer proxy clearly labeled as proxy;
- retention investments;
- renewal/sales incentives;
- customer success/service;
- cross-sell/upsell within existing customers;
- customer-selection quality;
- retention trend;
- evidence;
- analyst conclusion.

Critical guardrail:

> Revenue growth, recurring revenue, repeat orders or loyalty membership must never be converted into a fabricated retention rate.

---

## 9. Q11 — Customer Orientation

Evidence buckets:

1. **Customer Satisfaction** — NPS/CSAT/independent ratings/complaints when explicitly available;
2. **Service Quality** — service/support quality and knowledgeable staff;
3. **Fair Treatment** — pricing/refund/fee/customer-friendly policies and whether the business avoids exploiting customers;
4. **Management Proximity** — management/CEO contact with customers and use of customer feedback;
5. **Customer Immersion** — field observation, store visits, user observation, direct customer research.

Additional fields:

- customer metrics used to manage operations;
- independent indicators;
- evidence;
- analyst conclusion: operating behavior vs marketing language.

---

## 10. Q12 — Customer Pain / Need

Pain Map fields:

- Customer Segment;
- Pain / Need;
- Consequence if unsolved;
- Solution / Value delivered;
- Alternative workaround;
- Evidence.

Pain must be written from the customer's viewpoint, not merely as a description of what the company manufactures.

---

## 11. Q13 — Customer Dependency

Shearn continuum is preserved exactly:

- `Need to have`;
- `Need to have, but not immediately`;
- `Nice to have, but not critical`;
- `Unknown`.

Dependency should first be assessed **by customer/product**, then summarized for the business.

Dependency table:

- Customer Segment;
- Product / Service;
- Dependency Class;
- Can defer?;
- How long?;
- Alternatives / Substitutes;
- Consequence if stopped;
- Evidence.

Aggregate analyst fields remain for overall conclusion/reason, deferral period, consequence, substitutes and evidence.

AI must never choose the dependency classification.

---

## 12. Q14 — Disappearance Test

Customer-segment table:

- Customer Segment;
- Immediate Alternative;
- Time to Replace;
- Switching Cost;
- Operational Disruption;
- Customer Evidence.

Aggregate analyst fields:

- customer disruption: `Unknown / Low / Moderate / High / Severe`;
- immediate substitute;
- switching time;
- switching cost / implementation burden;
- operational disruption;
- disappearance conclusion;
- evidence.

Research Assistant may find replacement/switching evidence. It must never choose impact level or write the final disappearance conclusion.

---

## 13. Customer / Channel Interview Log

Shearn's customer perspective requires more than web research. The approved app therefore includes a Layer C fieldwork log:

- Date;
- Company / Person;
- Role;
- Customer Segment;
- Q Covered;
- Key Insight;
- Confidence;
- Evidence / Note.

Suggested interview questions:

- Why did you choose this product/service?
- What alternatives exist?
- What would make you change supplier?
- What happens if price increases?
- If this business disappeared tomorrow, what would you do?

Research Assistant must never fabricate interview content.

---

## 14. Customer Perspective Summary

Final Chapter 3 workspace includes:

- Customer Strengths;
- Customer Risks;
- Most Important Customer Evidence (target 3–5 key items);
- Critical Research Gaps;
- overall analyst narrative / Customer Perspective Summary.

Question completion is shown as `Answered / Partial / Unknown` for Q7–Q14.

Overall completeness label:

- 🟢 Customer Perspective Understood;
- 🟡 Customer Perspective Partial;
- 🔴 Customer Perspective Not Yet Understood.

This is **research completeness only**, not a quality score or investment rating.

---

## 15. Research Assistant permissions and prohibitions

### Permitted

- find customer evidence;
- classify evidence into Q7–Q14;
- extract explicitly disclosed customer concentration percentages;
- extract explicitly disclosed retention/churn/renewal percentages;
- find customer satisfaction/service evidence;
- find substitutes/replacement evidence;
- summarize source material into blank research fields;
- propose research gaps;
- preserve provenance and cache evidence for offline review.

### Forbidden

- invent customer names or shares;
- infer concentration from geography/segments;
- infer retention from revenue or recurring revenue;
- invent NPS/CSAT;
- infer Revenue Relevance or Profit Relevance without evidence;
- automatically classify Q8 concentration;
- automatically classify Q9 sales ease;
- automatically classify Q13 dependency;
- automatically classify Q14 impact;
- overwrite analyst content;
- change Chapter 1 Research Gate;
- output BUY/HOLD/SELL.

---

## 16. Persistence

SQLite:

`data_cache/deep_company_analysis_chapter3.db`

Tables:

- `chapter3_current` — one current record per ticker;
- `chapter3_snapshots` — append-only snapshot history.

The JSON payload stores Q7–Q14, interview log, evidence matrix, summary fields and Research Assistant provenance. Existing prototype records are loaded backward-compatibly.

---

## 17. Unified page integration

Chapter 3 is the third tab of the single page:

`Phân tích chuyên sâu doanh nghiệp`

Tabs:

1. 📗 Chương 1 — Cơ hội đầu tư
2. 📘 Chương 2 — Hiểu doanh nghiệp
3. 📙 Chương 3 — Góc nhìn khách hàng

The ticker context is shared across the workspace.

---

## 18. Delivery phases — approved

### Phase 3A — Source-locked Core

Schema + Q7–Q14 + tables + current/snapshot persistence + unified tab. No automatic analyst conclusions.

### Phase 3B — Evidence Bridge

BCTN/BCTC/IR + independent/customer-side evidence, provenance and no-overwrite Research Assistant draft.

### Phase 3C — Human / Customer Intelligence

Customer/channel interview log + three-layer evidence model + Evidence Matrix + conflicting-evidence warning + research gaps.

### Phase 3D — DGC Acceptance

Run DGC end-to-end, inspect Q7–Q14 evidence, ensure no fabricated customer/retention/concentration/relevance, run regression and UI smoke tests, then lock Chapter 3.

---

## 19. Acceptance criteria before Chapter 3 lock

- Q7–Q14 remain source-faithful;
- Revenue Relevance and Profit Relevance are separate optional fields;
- no revenue/profit relevance is invented;
- core-customer buyer/payer/user are distinguishable;
- Q8 concentration requires explicit evidence and analyst classification;
- Q10 retention cannot be fabricated from proxies;
- Q13 dependency has customer/product-level analysis and analyst-controlled classification;
- Q14 has customer-segment disappearance analysis and analyst-controlled impact/conclusion;
- interview log is manual Layer C evidence only;
- Evidence Matrix supports A/B/C layers and `Conflicting` status;
- conflicting evidence is surfaced, never auto-resolved;
- Research Assistant never overwrites analyst content;
- one current record per ticker and append-only snapshots remain intact;
- existing Chapter 1–2 regressions remain green;
- DGC live end-to-end and unified-page smoke tests pass before lock.
''', encoding="utf-8")


def patch_workflow_version() -> None:
    if not WORKFLOW.exists():
        return
    text = WORKFLOW.read_text(encoding="utf-8")
    # Move only the current offline-package target forward. Do not alter old artifact history.
    text = text.replace("Trecapital_Deep_Analysis_Offline_V13", "Trecapital_Deep_Analysis_Offline_V14")
    text = text.replace("package V13", "package V14")
    WORKFLOW.write_text(text, encoding="utf-8")


def main() -> None:
    patch_chapter3()
    patch_page_support()
    patch_tests()
    write_context()
    patch_workflow_version()
    print("Applied approved Chapter 3 specification, including separate Revenue Relevance and Profit Relevance fields.")


if __name__ == "__main__":
    main()
