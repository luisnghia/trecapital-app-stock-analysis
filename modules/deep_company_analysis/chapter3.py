from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

APP_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = APP_ROOT / "data_cache" / "deep_company_analysis_chapter3.db"

CONCENTRATION_STATUS = ["Unknown", "Diversified", "Moderately concentrated", "Concentrated"]
SALES_EASE_STATUS = ["Unknown", "Easy", "Moderate", "Hard"]
RETENTION_ASSESSABILITY = ["Unknown", "Disclosed metric", "Proxy only", "Not disclosed", "Not meaningful for this business model"]
DEPENDENCY_CLASS = ["Unknown", "Need to have", "Need to have, but not immediately", "Nice to have, but not critical"]
IMPACT_LEVEL = ["Unknown", "Low", "Moderate", "High", "Severe"]
CUSTOMER_PERSPECTIVE_LABELS = {
    "understood": "🟢 Customer Perspective Understood",
    "partial": "🟡 Customer Perspective Partial",
    "not_understood": "🔴 Customer Perspective Not Yet Understood",
}

CORE_CUSTOMER_COLUMNS = [
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
]
CONCENTRATION_COLUMNS = [
    "Customer / Group",
    "Revenue share %",
    "Period",
    "Trend",
    "Bargaining power",
    "Dependency / loss impact",
    "Evidence",
]
PAIN_COLUMNS = [
    "Customer Segment",
    "Pain / Need",
    "Consequence if unsolved",
    "Solution / Value delivered",
    "Alternative workaround",
    "Evidence",
]

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


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chapter3_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                customer_perspective_status TEXT NOT NULL DEFAULT 'not_understood',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapter3_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                customer_perspective_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def empty_payload(ticker: str = "", company_name: str = "") -> dict[str, Any]:
    return {
        "ticker": _safe_ticker(ticker),
        "company_name": company_name or "",
        "q7": {
            "core_customers": [],
            "core_customer_summary": "",
            "why_core": "",
        },
        "q8": {
            "concentration_status": "Unknown",
            "concentration_table": [],
            "concentration_trend": "",
            "concentration_summary": "",
        },
        "q9": {
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
        },
        "q10": {
            "retention_assessability": "Unknown",
            "business_model": "",
            "retention_rate": "",
            "retention_period": "",
            "churn_rate": "",
            "loyalty_proxy": "",
            "retention_investments": "",
            "renewal_incentives": "",
            "customer_success_service": "",
            "cross_sell_existing": "",
            "customer_selection_quality": "",
            "retention_trend": "",
            "retention_summary": "",
            "evidence": "",
        },
        "q11": {
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
        },
        "q12": {
            "pain_map": [],
            "pain_summary": "",
        },
        "q13": {
            "dependency_table": [],
            "dependency_class": "Unknown",
            "dependency_reason": "",
            "deferral_period": "",
            "consequence_if_stopped": "",
            "substitutes": "",
            "evidence": "",
        },
        "q14": {
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
        "analyst_summary": "",
    }


def load_record(ticker: str, company_name: str = "") -> dict[str, Any]:
    init_db()
    ticker = _safe_ticker(ticker)
    base = empty_payload(ticker, company_name)
    if not ticker:
        return base
    with _connect() as conn:
        row = conn.execute("SELECT * FROM chapter3_current WHERE ticker = ?", (ticker,)).fetchone()
    if not row:
        return base
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except Exception:
        payload = {}
    merged = base
    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    merged["ticker"] = ticker
    merged["company_name"] = row["company_name"] or merged.get("company_name", "")
    merged["_exists"] = True
    return merged


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _nonempty_table(rows: Any) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if isinstance(row, dict) and any(_has_text(v) for v in row.values()):
            return True
    return False


def question_statuses(payload: dict[str, Any]) -> dict[str, str]:
    def status(required: list[bool], optional: list[bool] | None = None) -> str:
        optional = optional or []
        if required and all(required):
            return "Answered"
        if any(required + optional):
            return "Partial"
        return "Unknown"

    q7 = payload.get("q7", {})
    q8 = payload.get("q8", {})
    q9 = payload.get("q9", {})
    q10 = payload.get("q10", {})
    q11 = payload.get("q11", {})
    q12 = payload.get("q12", {})
    q13 = payload.get("q13", {})
    q14 = payload.get("q14", {})

    q10_assessability = str(q10.get("retention_assessability") or "Unknown")
    q10_assessed = q10_assessability != "Unknown"
    q11_evidence_present = any(
        _has_text(q11.get(key))
        for key in (
            "feedback_mechanisms",
            "satisfaction_metrics",
            "management_proximity",
            "field_immersion",
            "service_quality",
            "fair_treatment",
            "customer_metrics_used",
            "independent_indicators",
            "evidence",
        )
    )

    return {
        "Q7": status(
            [_nonempty_table(q7.get("core_customers")), _has_text(q7.get("core_customer_summary"))],
            [_has_text(q7.get("why_core"))],
        ),
        "Q8": status(
            [str(q8.get("concentration_status") or "Unknown") != "Unknown", _has_text(q8.get("concentration_summary"))],
            [_nonempty_table(q8.get("concentration_table")), _has_text(q8.get("concentration_trend"))],
        ),
        "Q9": status(
            [str(q9.get("sales_ease_status") or "Unknown") != "Unknown", _has_text(q9.get("sales_friction_summary"))],
            [
                _has_text(q9.get("sales_motion")),
                _has_text(q9.get("sales_cycle")),
                _has_text(q9.get("trial_demo")),
                _has_text(q9.get("pressure_tactics")),
                _has_text(q9.get("discount_dependency")),
                _has_text(q9.get("inbound_demand")),
                _has_text(q9.get("repeat_purchase_friction")),
                _has_text(q9.get("evidence")),
            ],
        ),
        "Q10": status(
            [q10_assessed, _has_text(q10.get("retention_summary"))],
            [
                _has_text(q10.get("retention_rate")),
                _has_text(q10.get("churn_rate")),
                _has_text(q10.get("loyalty_proxy")),
                _has_text(q10.get("retention_investments")),
                _has_text(q10.get("renewal_incentives")),
                _has_text(q10.get("customer_success_service")),
                _has_text(q10.get("cross_sell_existing")),
                _has_text(q10.get("customer_selection_quality")),
                _has_text(q10.get("evidence")),
            ],
        ),
        "Q11": status(
            [_has_text(q11.get("customer_orientation_summary")), q11_evidence_present],
        ),
        "Q12": status(
            [_nonempty_table(q12.get("pain_map")), _has_text(q12.get("pain_summary"))],
        ),
        "Q13": status(
            [str(q13.get("dependency_class") or "Unknown") != "Unknown", _has_text(q13.get("dependency_reason"))],
            [
                _nonempty_table(q13.get("dependency_table")),
                _has_text(q13.get("deferral_period")),
                _has_text(q13.get("consequence_if_stopped")),
                _has_text(q13.get("substitutes")),
                _has_text(q13.get("evidence")),
            ],
        ),
        "Q14": status(
            [str(q14.get("impact_level") or "Unknown") != "Unknown", _has_text(q14.get("disappearance_conclusion"))],
            [
                _nonempty_table(q14.get("disappearance_table")),
                _has_text(q14.get("immediate_substitute")),
                _has_text(q14.get("switching_time")),
                _has_text(q14.get("switching_cost")),
                _has_text(q14.get("operational_disruption")),
                _has_text(q14.get("evidence")),
            ],
        ),
    }


def customer_perspective_status(payload: dict[str, Any]) -> str:
    statuses = question_statuses(payload)
    answered = sum(1 for value in statuses.values() if value == "Answered")
    if answered >= 6 and statuses.get("Q7") == "Answered" and statuses.get("Q12") == "Answered":
        return "understood"
    if any(value != "Unknown" for value in statuses.values()):
        return "partial"
    return "not_understood"


def save_record(payload: dict[str, Any]) -> str:
    init_db()
    ticker = _safe_ticker(payload.get("ticker", ""))
    if not ticker:
        raise ValueError("Ticker is required")
    payload = dict(payload)
    payload["ticker"] = ticker
    company_name = str(payload.get("company_name", "") or "")
    status = customer_perspective_status(payload)
    now = _now()
    serialized = json.dumps(payload, ensure_ascii=False)
    with _connect() as conn:
        old = conn.execute("SELECT created_at FROM chapter3_current WHERE ticker = ?", (ticker,)).fetchone()
        created_at = old["created_at"] if old else now
        conn.execute(
            """
            INSERT INTO chapter3_current (ticker, company_name, payload_json, customer_perspective_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name=excluded.company_name,
                payload_json=excluded.payload_json,
                customer_perspective_status=excluded.customer_perspective_status,
                updated_at=excluded.updated_at
            """,
            (ticker, company_name, serialized, status, created_at, now),
        )
        conn.execute(
            "INSERT INTO chapter3_snapshots (ticker, payload_json, customer_perspective_status, created_at) VALUES (?, ?, ?, ?)",
            (ticker, serialized, status, now),
        )
    return status


def load_history(ticker: str) -> pd.DataFrame:
    init_db()
    ticker = _safe_ticker(ticker)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, customer_perspective_status, created_at FROM chapter3_snapshots WHERE ticker = ? ORDER BY id DESC",
            (ticker,),
        ).fetchall()
    return pd.DataFrame([
        {
            "Snapshot": row["id"],
            "Customer Perspective": CUSTOMER_PERSPECTIVE_LABELS.get(
                row["customer_perspective_status"], row["customer_perspective_status"]
            ),
            "Thời điểm": row["created_at"],
        }
        for row in rows
    ])


def _rows_to_df(rows: Any, columns: list[str]) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    # Backward compatibility with the unapproved prototype that used one combined relevance field.
    if columns == CORE_CUSTOMER_COLUMNS and "Revenue / profit relevance" in df.columns:
        if "Revenue Relevance" not in df.columns:
            df["Revenue Relevance"] = df["Revenue / profit relevance"].map(
                lambda value: f"Legacy combined field: {value}" if str(value or "").strip() else ""
            )
        if "Profit Relevance" not in df.columns:
            df["Profit Relevance"] = ""
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df[columns]


def _df_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    clean = df.copy().fillna("")
    rows: list[dict[str, Any]] = []
    for row in clean.to_dict(orient="records"):
        if any(_has_text(v) for v in row.values()):
            rows.append(row)
    return rows


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


def _render_intro() -> None:
    with st.expander("📙 Hướng dẫn Chương 3 — Hiểu doanh nghiệp từ góc nhìn khách hàng", expanded=True):
        st.markdown(
            """
**Mục đích:** chuyển góc nhìn từ sản phẩm/doanh nghiệp sang **khách hàng thực sự**. Câu hỏi trung tâm không phải “Tôi có thích sản phẩm này không?” mà là **“Khách hàng thực sự có cần/muốn sản phẩm này không, tại sao họ mua và vì sao họ tiếp tục mua?”**

**8 câu hỏi của Chương 3:** Q7 khách hàng cốt lõi; Q8 tập trung/đa dạng khách hàng; Q9 dễ hay khó thuyết phục mua; Q10 retention; Q11 dấu hiệu customer-oriented; Q12 customer pain; Q13 mức độ phụ thuộc; Q14 điều gì xảy ra nếu doanh nghiệp biến mất ngày mai.

**Ba lớp evidence:** A — Company Disclosure (BCTN/BCTC/IR); B — Independent / Customer-side; C — Analyst Fieldwork / Customer Interview. Nếu evidence mâu thuẫn, giữ cả hai phía và đánh dấu `Conflicting` để analyst xử lý.

**Q7 có hai field kinh tế bổ sung:** `Revenue Relevance` = tỷ trọng/đóng góp doanh thu của nhóm khách hàng nếu có evidence; `Profit Relevance` = đóng góp lợi nhuận/biên lợi nhuận nếu có disclosure. Hai field này **không bắt buộc** và không được suy diễn từ segment/geography.

**Guardrail:** Không suy diễn customer concentration, retention/churn, NPS, revenue share, profit contribution hay switching cost khi nguồn không công bố. `Unknown` là kết quả hợp lệ và phải được chuyển thành Research Gap. AI/Data = Research Assistant; người dùng = Investment Analyst.
            """
        )


def _status_summary(payload: dict[str, Any]) -> None:
    statuses = question_statuses(payload)
    cols = st.columns(8)
    for idx, question in enumerate(("Q7", "Q8", "Q9", "Q10", "Q11", "Q12", "Q13", "Q14")):
        value = statuses[question]
        icon = "✅" if value == "Answered" else "🟡" if value == "Partial" else "⚪"
        cols[idx].metric(question, f"{icon} {value}")


def render_chapter3(default_ticker: str = "", company_name: str = "") -> None:
    _render_intro()
    ticker = _safe_ticker(st.text_input("Mã cổ phiếu — Chương 3", value=default_ticker or "", key="dca_ch3_ticker"))
    record = load_record(ticker, company_name)
    resolved_name = str(record.get("company_name") or company_name or "")
    company_name_value = st.text_input("Doanh nghiệp", value=resolved_name, key=f"dca_ch3_company_{ticker}")

    st.markdown("## Chương 3 — Hiểu doanh nghiệp từ góc nhìn khách hàng")
    st.caption("Trạng thái chỉ phản ánh mức độ analyst đã hiểu customer economics; không phải điểm chất lượng và không phải tín hiệu mua/bán.")
    _status_summary(record)

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

    q7 = record["q7"]
    st.markdown("### Q7. Khách hàng cốt lõi của doanh nghiệp là ai?")
    st.caption("Tách rõ buyer, người trả tiền và người sử dụng. Revenue Relevance và Profit Relevance chỉ nhập khi có disclosure/evidence; không bắt buộc và không suy diễn từ segment/geography.")
    core_customer_df = st.data_editor(
        _rows_to_df(q7.get("core_customers"), CORE_CUSTOMER_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key=f"ch3_q7_customers_{ticker}",
    )
    core_customer_summary = st.text_area(
        "Core customer summary — nhóm nào thực sự quyết định economics của doanh nghiệp?",
        value=q7.get("core_customer_summary", ""),
        height=110,
        key=f"ch3_q7_summary_{ticker}",
    )
    why_core = st.text_area(
        "Vì sao đây là khách hàng cốt lõi — bằng chứng về nhu cầu, profitability, tần suất mua, bargaining power hoặc strategic fit",
        value=q7.get("why_core", ""),
        height=90,
        key=f"ch3_q7_why_{ticker}",
    )

    q8 = record["q8"]
    st.markdown("### Q8. Cơ sở khách hàng tập trung hay đa dạng?")
    concentration_status = st.selectbox(
        "Customer concentration",
        CONCENTRATION_STATUS,
        index=CONCENTRATION_STATUS.index(q8.get("concentration_status", "Unknown")),
        key=f"ch3_q8_status_{ticker}",
    )
    concentration_df = st.data_editor(
        _rows_to_df(q8.get("concentration_table"), CONCENTRATION_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key=f"ch3_q8_table_{ticker}",
    )
    concentration_trend = st.text_area(
        "Concentration trend — mức tập trung đang tăng, giảm hay không đủ dữ liệu?",
        value=q8.get("concentration_trend", ""),
        height=80,
        key=f"ch3_q8_trend_{ticker}",
    )
    concentration_summary = st.text_area(
        "Kết luận Q8 — tác động của concentration lên pricing, bargaining power và rủi ro mất khách hàng",
        value=q8.get("concentration_summary", ""),
        height=100,
        key=f"ch3_q8_summary_{ticker}",
    )
    if concentration_status == "Unknown":
        st.info("Không có disclosure đáng tin cậy thì để Unknown. Không suy customer concentration từ segment revenue hoặc geographic revenue.")

    q9 = record["q9"]
    st.markdown("### Q9. Dễ hay khó thuyết phục khách hàng mua sản phẩm/dịch vụ?")
    sales_ease_status = st.selectbox(
        "Mức độ sales friction",
        SALES_EASE_STATUS,
        index=SALES_EASE_STATUS.index(q9.get("sales_ease_status", "Unknown")),
        key=f"ch3_q9_status_{ticker}",
    )
    c91, c92 = st.columns(2)
    sales_motion = c91.text_area("Sales motion — self-serve, distributor, tender, relationship sales...", value=q9.get("sales_motion", ""), height=90, key=f"ch3_q9_motion_{ticker}")
    sales_cycle = c92.text_area("Sales cycle / decision process", value=q9.get("sales_cycle", ""), height=90, key=f"ch3_q9_cycle_{ticker}")
    trial_demo = st.text_area("Demo / trial / education / qualification cần thiết trước khi mua", value=q9.get("trial_demo", ""), height=80, key=f"ch3_q9_trial_{ticker}")
    pressure_tactics = st.text_area("High-pressure selling / promotion dependency — có bằng chứng hay không?", value=q9.get("pressure_tactics", ""), height=80, key=f"ch3_q9_pressure_{ticker}")
    c93, c94 = st.columns(2)
    discount_dependency = c93.text_area("Discount dependency — có phải giảm giá mạnh mới bán được?", value=q9.get("discount_dependency", ""), height=80, key=f"ch3_q9_discount_{ticker}")
    inbound_demand = c94.text_area("Customer pull — khách hàng chủ động tìm đến hay sales phải tạo nhu cầu?", value=q9.get("inbound_demand", ""), height=80, key=f"ch3_q9_inbound_{ticker}")
    repeat_purchase_friction = st.text_area("Repeat purchase — bán lại cho khách hàng cũ dễ hơn/khó hơn bán mới như thế nào?", value=q9.get("repeat_purchase_friction", ""), height=80, key=f"ch3_q9_repeat_{ticker}")
    sales_friction_summary = st.text_area("Kết luận Q9 — sản phẩm bán nhờ merit/need hay phụ thuộc mạnh vào sales effort?", value=q9.get("sales_friction_summary", ""), height=100, key=f"ch3_q9_summary_{ticker}")
    q9_evidence = st.text_area("Evidence Q9", value=q9.get("evidence", ""), height=80, key=f"ch3_q9_evidence_{ticker}")

    q10 = record["q10"]
    st.markdown("### Q10. Tỷ lệ giữ chân khách hàng của doanh nghiệp là bao nhiêu?")
    st.caption("Retention chỉ có thể đo trực tiếp ở một số business model. Loyalty membership hay recurring revenue có thể là proxy nhưng không được ghi như retention rate.")
    retention_assessability = st.selectbox(
        "Retention evidence status",
        RETENTION_ASSESSABILITY,
        index=RETENTION_ASSESSABILITY.index(q10.get("retention_assessability", "Unknown")),
        key=f"ch3_q10_assess_{ticker}",
    )
    business_model = st.text_input("Business model — recurring / transactional / mixed / other", value=q10.get("business_model", ""), key=f"ch3_q10_model_{ticker}")
    c101, c102, c103 = st.columns(3)
    retention_rate = c101.text_input("Retention rate — chỉ nhập nếu disclosure có nguồn", value=q10.get("retention_rate", ""), key=f"ch3_q10_retention_{ticker}")
    retention_period = c102.text_input("Period", value=q10.get("retention_period", ""), key=f"ch3_q10_period_{ticker}")
    churn_rate = c103.text_input("Churn rate — nếu disclosure có nguồn", value=q10.get("churn_rate", ""), key=f"ch3_q10_churn_{ticker}")
    loyalty_proxy = st.text_area("Loyalty / repeat-customer proxy — ghi rõ đây là proxy", value=q10.get("loyalty_proxy", ""), height=80, key=f"ch3_q10_proxy_{ticker}")
    retention_investments = st.text_area("Doanh nghiệp đầu tư gì để giữ khách hàng?", value=q10.get("retention_investments", ""), height=80, key=f"ch3_q10_invest_{ticker}")
    renewal_incentives = st.text_area("Sales / channel incentives có khuyến khích renewal/retention không?", value=q10.get("renewal_incentives", ""), height=80, key=f"ch3_q10_incentive_{ticker}")
    customer_success_service = st.text_area("Customer success / service — doanh nghiệp hỗ trợ khách hàng cũ như thế nào?", value=q10.get("customer_success_service", ""), height=80, key=f"ch3_q10_success_{ticker}")
    cross_sell_existing = st.text_area("Cross-sell / upsell trong khách hàng hiện hữu — có evidence hay không?", value=q10.get("cross_sell_existing", ""), height=80, key=f"ch3_q10_crosssell_{ticker}")
    customer_selection_quality = st.text_area("Doanh nghiệp có chủ động chọn nhóm khách hàng dễ giữ chân/profitable hơn không?", value=q10.get("customer_selection_quality", ""), height=80, key=f"ch3_q10_selection_{ticker}")
    retention_trend = st.text_area("Retention trend — tăng/giảm/không đủ dữ liệu", value=q10.get("retention_trend", ""), height=80, key=f"ch3_q10_trend_{ticker}")
    retention_summary = st.text_area("Kết luận Q10 — mức độ bền của quan hệ khách hàng và độ chắc chắn của evidence", value=q10.get("retention_summary", ""), height=100, key=f"ch3_q10_summary_{ticker}")
    q10_evidence = st.text_area("Evidence Q10", value=q10.get("evidence", ""), height=80, key=f"ch3_q10_evidence_{ticker}")

    q11 = record["q11"]
    st.markdown("### Q11. Những dấu hiệu nào cho thấy doanh nghiệp định hướng khách hàng?")
    c111, c112 = st.columns(2)
    feedback_mechanisms = c111.text_area("Feedback mechanisms — complaint, survey, customer panel, support data...", value=q11.get("feedback_mechanisms", ""), height=90, key=f"ch3_q11_feedback_{ticker}")
    satisfaction_metrics = c112.text_area("Customer satisfaction metrics — NPS/CSAT/independent studies nếu có", value=q11.get("satisfaction_metrics", ""), height=90, key=f"ch3_q11_metrics_{ticker}")
    management_proximity = st.text_area("Management proximity — lãnh đạo duy trì tiếp xúc với khách hàng như thế nào?", value=q11.get("management_proximity", ""), height=90, key=f"ch3_q11_management_{ticker}")
    service_quality = st.text_area("Service Quality — năng lực support/phục vụ, knowledgeable staff, response quality...", value=q11.get("service_quality", ""), height=80, key=f"ch3_q11_service_{ticker}")
    fair_treatment = st.text_area("Fair Treatment — pricing/refund/fee/policy có đối xử công bằng, không lợi dụng khách hàng?", value=q11.get("fair_treatment", ""), height=80, key=f"ch3_q11_fair_{ticker}")
    field_immersion = st.text_area("Field immersion / customer research — quan sát người dùng, đi thị trường, store/field visit...", value=q11.get("field_immersion", ""), height=90, key=f"ch3_q11_field_{ticker}")
    customer_metrics_used = st.text_area("Customer metrics được dùng để điều hành", value=q11.get("customer_metrics_used", ""), height=80, key=f"ch3_q11_usedmetrics_{ticker}")
    independent_indicators = st.text_area("Independent indicators — rating/review/study/customer evidence", value=q11.get("independent_indicators", ""), height=80, key=f"ch3_q11_independent_{ticker}")
    customer_orientation_summary = st.text_area("Kết luận Q11 — customer orientation có phải hành vi vận hành thực tế hay chỉ là marketing?", value=q11.get("customer_orientation_summary", ""), height=100, key=f"ch3_q11_summary_{ticker}")
    q11_evidence = st.text_area("Evidence Q11", value=q11.get("evidence", ""), height=80, key=f"ch3_q11_evidence_{ticker}")

    q12 = record["q12"]
    st.markdown("### Q12. Doanh nghiệp giải quyết 'nỗi đau' nào cho khách hàng?")
    pain_df = st.data_editor(
        _rows_to_df(q12.get("pain_map"), PAIN_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key=f"ch3_q12_table_{ticker}",
    )
    pain_summary = st.text_area("Kết luận Q12 — nhu cầu/vấn đề thực tế nào đủ quan trọng để khách hàng trả tiền?", value=q12.get("pain_summary", ""), height=110, key=f"ch3_q12_summary_{ticker}")

    q13 = record["q13"]
    st.markdown("### Q13. Khách hàng phụ thuộc vào sản phẩm/dịch vụ ở mức độ nào?")
    st.caption("Dùng đúng continuum của Shearn: Need to have → Need to have, but not immediately → Nice to have, but not critical. Đánh giá theo customer/product trước, rồi mới viết kết luận tổng hợp. Không mặc định discretionary = business xấu.")
    dependency_df = st.data_editor(
        _rows_to_df(q13.get("dependency_table"), DEPENDENCY_TABLE_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key=f"ch3_q13_table_{ticker}",
    )
    dependency_class = st.selectbox(
        "Customer dependency",
        DEPENDENCY_CLASS,
        index=DEPENDENCY_CLASS.index(q13.get("dependency_class", "Unknown")),
        key=f"ch3_q13_class_{ticker}",
    )
    dependency_reason = st.text_area("Vì sao xếp vào mức này?", value=q13.get("dependency_reason", ""), height=90, key=f"ch3_q13_reason_{ticker}")
    deferral_period = st.text_input("Khách hàng có thể trì hoãn bao lâu?", value=q13.get("deferral_period", ""), key=f"ch3_q13_deferral_{ticker}")
    consequence_if_stopped = st.text_area("Nếu ngừng dùng/mua, hậu quả vận hành/tài chính của khách hàng là gì?", value=q13.get("consequence_if_stopped", ""), height=90, key=f"ch3_q13_consequence_{ticker}")
    substitutes = st.text_area("Substitutes / workaround", value=q13.get("substitutes", ""), height=80, key=f"ch3_q13_substitutes_{ticker}")
    q13_evidence = st.text_area("Evidence Q13", value=q13.get("evidence", ""), height=80, key=f"ch3_q13_evidence_{ticker}")

    q14 = record["q14"]
    st.markdown("### Q14. Nếu doanh nghiệp biến mất ngày mai, khách hàng sẽ bị ảnh hưởng thế nào?")
    disappearance_df = st.data_editor(
        _rows_to_df(q14.get("disappearance_table"), DISAPPEARANCE_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key=f"ch3_q14_table_{ticker}",
    )
    impact_level = st.selectbox(
        "Customer disruption",
        IMPACT_LEVEL,
        index=IMPACT_LEVEL.index(q14.get("impact_level", "Unknown")),
        key=f"ch3_q14_level_{ticker}",
    )
    immediate_substitute = st.text_area("Khách hàng sẽ chuyển sang ai/cách nào ngay lập tức?", value=q14.get("immediate_substitute", ""), height=80, key=f"ch3_q14_substitute_{ticker}")
    c141, c142 = st.columns(2)
    switching_time = c141.text_input("Switching time", value=q14.get("switching_time", ""), key=f"ch3_q14_time_{ticker}")
    switching_cost = c142.text_input("Switching cost / implementation burden", value=q14.get("switching_cost", ""), key=f"ch3_q14_cost_{ticker}")
    operational_disruption = st.text_area("Operational disruption nếu mất nhà cung cấp/doanh nghiệp này", value=q14.get("operational_disruption", ""), height=90, key=f"ch3_q14_disruption_{ticker}")
    disappearance_conclusion = st.text_area("Kết luận Q14 — mức độ replaceability/dependency từ góc nhìn khách hàng", value=q14.get("disappearance_conclusion", ""), height=100, key=f"ch3_q14_conclusion_{ticker}")
    q14_evidence = st.text_area("Evidence Q14", value=q14.get("evidence", ""), height=80, key=f"ch3_q14_evidence_{ticker}")

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

    research_gaps = st.text_area(
        "Research Gaps Chương 3 — mỗi dòng một điều chưa biết cần tìm thêm",
        value=record.get("research_gaps", ""),
        height=120,
        key=f"ch3_gaps_{ticker}",
    )
    analyst_summary = st.text_area(
        "Customer Perspective Summary — kết luận của analyst",
        value=record.get("analyst_summary", ""),
        height=130,
        key=f"ch3_summary_{ticker}",
    )

    payload = {
        "ticker": ticker,
        "company_name": company_name_value,
        "q7": {
            "core_customers": _df_to_rows(core_customer_df),
            "core_customer_summary": core_customer_summary,
            "why_core": why_core,
        },
        "q8": {
            "concentration_status": concentration_status,
            "concentration_table": _df_to_rows(concentration_df),
            "concentration_trend": concentration_trend,
            "concentration_summary": concentration_summary,
        },
        "q9": {
            "sales_ease_status": sales_ease_status,
            "sales_motion": sales_motion,
            "sales_cycle": sales_cycle,
            "trial_demo": trial_demo,
            "pressure_tactics": pressure_tactics,
            "discount_dependency": discount_dependency,
            "inbound_demand": inbound_demand,
            "repeat_purchase_friction": repeat_purchase_friction,
            "sales_friction_summary": sales_friction_summary,
            "evidence": q9_evidence,
        },
        "q10": {
            "retention_assessability": retention_assessability,
            "business_model": business_model,
            "retention_rate": retention_rate,
            "retention_period": retention_period,
            "churn_rate": churn_rate,
            "loyalty_proxy": loyalty_proxy,
            "retention_investments": retention_investments,
            "renewal_incentives": renewal_incentives,
            "customer_success_service": customer_success_service,
            "cross_sell_existing": cross_sell_existing,
            "customer_selection_quality": customer_selection_quality,
            "retention_trend": retention_trend,
            "retention_summary": retention_summary,
            "evidence": q10_evidence,
        },
        "q11": {
            "feedback_mechanisms": feedback_mechanisms,
            "satisfaction_metrics": satisfaction_metrics,
            "service_quality": service_quality,
            "fair_treatment": fair_treatment,
            "management_proximity": management_proximity,
            "field_immersion": field_immersion,
            "customer_metrics_used": customer_metrics_used,
            "independent_indicators": independent_indicators,
            "customer_orientation_summary": customer_orientation_summary,
            "evidence": q11_evidence,
        },
        "q12": {
            "pain_map": _df_to_rows(pain_df),
            "pain_summary": pain_summary,
        },
        "q13": {
            "dependency_table": _df_to_rows(dependency_df),
            "dependency_class": dependency_class,
            "dependency_reason": dependency_reason,
            "deferral_period": deferral_period,
            "consequence_if_stopped": consequence_if_stopped,
            "substitutes": substitutes,
            "evidence": q13_evidence,
        },
        "q14": {
            "disappearance_table": _df_to_rows(disappearance_df),
            "impact_level": impact_level,
            "immediate_substitute": immediate_substitute,
            "switching_time": switching_time,
            "switching_cost": switching_cost,
            "operational_disruption": operational_disruption,
            "disappearance_conclusion": disappearance_conclusion,
            "evidence": q14_evidence,
        },
        "customer_interviews": _df_to_rows(interview_df),
        "evidence_matrix": _df_to_rows(evidence_matrix_df),
        "customer_strengths": customer_strengths,
        "customer_risks": customer_risks,
        "most_important_evidence": most_important_evidence,
        "research_gaps": research_gaps,
        "analyst_summary": analyst_summary,
    }

    statuses = question_statuses(payload)
    overall = customer_perspective_status(payload)
    answered = sum(1 for value in statuses.values() if value == "Answered")
    partial = sum(1 for value in statuses.values() if value == "Partial")
    unknown = sum(1 for value in statuses.values() if value == "Unknown")

    st.markdown("### Chapter 3 Research Status")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Answered", f"{answered}/8")
    s2.metric("Partial", partial)
    s3.metric("Unknown", unknown)
    s4.metric("Customer Perspective", CUSTOMER_PERSPECTIVE_LABELS[overall])

    if unknown:
        st.warning("Còn câu hỏi Unknown. Giữ Unknown nếu chưa có evidence; không ép câu trả lời để làm đẹp completion rate.")

    if st.button("💾 Lưu Chương 3", type="primary", use_container_width=True, key=f"ch3_save_{ticker}"):
        if not ticker:
            st.error("Cần nhập mã cổ phiếu trước khi lưu.")
        else:
            saved_status = save_record(payload)
            st.success(f"Đã lưu Chương 3 cho {ticker}. Trạng thái: {CUSTOMER_PERSPECTIVE_LABELS[saved_status]}")
            st.rerun()

    history = load_history(ticker) if ticker else pd.DataFrame()
    with st.expander("🕘 Snapshot History — Chương 3", expanded=False):
        if history.empty:
            st.caption("Chưa có snapshot.")
        else:
            st.dataframe(history, use_container_width=True, hide_index=True)
