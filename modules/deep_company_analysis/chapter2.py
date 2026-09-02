from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

APP_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = APP_ROOT / "data_cache" / "deep_company_analysis_chapter2.db"

RESEARCH_INTEREST = ["Thấp", "Trung bình", "Cao"]
LEARNING_CURVE = ["Dễ hiểu", "Có thể hiểu với thời gian", "Rất khó hiểu"]
CIRCLE_STATUS = ["Tiếp tục học", "Cần thêm thời gian", "Ngoài Circle of Competence hiện tại"]
COMPLEXITY_STATUS = ["Dễ giải thích", "Có phần phức tạp", "Chưa hiểu đầy đủ cách kiếm tiền"]
UNDERSTANDING_LABELS = {
    "understandable": "🟢 Understandable",
    "partial": "🟡 Partially Understood",
    "not_understood": "🔴 Not Yet Understood",
}

SEGMENT_COLUMNS = [
    "Segment",
    "Product / Service",
    "Customer",
    "Production / Service process",
    "Distribution",
    "Marketing",
    "Regulation",
    "Revenue share %",
]
MONEY_COLUMNS = [
    "Segment",
    "Who pays?",
    "Pays for what?",
    "Volume driver",
    "Price driver",
    "Revenue share %",
    "Major costs",
    "Profit engine",
]
EVOLUTION_COLUMNS = ["Year", "Event", "Type", "Why it happened", "Impact", "Evidence"]
FOREIGN_COLUMNS = [
    "Country / Region",
    "Entry year",
    "Revenue share %",
    "Operating profit",
    "Assets",
    "Capex",
    "Localization / R&D",
    "Dedicated regional management",
    "Evidence",
]
COUNTRY_RISK_COLUMNS = [
    "Country",
    "Revenue exposure %",
    "Political / social",
    "Regulation",
    "Tax",
    "Labor",
    "Protectionism / FDI",
    "Research note",
]
CURRENCY_COLUMNS = [
    "Currency",
    "Revenue exposure",
    "Cost exposure",
    "Net exposure",
    "Hedge",
    "Natural hedge",
    "Recent FX impact",
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
            CREATE TABLE IF NOT EXISTS chapter2_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                understanding_status TEXT NOT NULL DEFAULT 'not_understood',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapter2_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                understanding_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def empty_payload(ticker: str = "", company_name: str = "") -> dict[str, Any]:
    return {
        "ticker": _safe_ticker(ticker),
        "company_name": company_name or "",
        "q1": {
            "research_interest": "Trung bình",
            "learning_curve": "Có thể hiểu với thời gian",
            "interest_reason": "",
            "unknowns": "",
            "bias_check": "",
            "circle_status": "Cần thêm thời gian",
        },
        "q2": {
            "underlying_economics": "",
            "industry_context": "",
            "customers_users": "",
            "field_reality_check": "",
            "ceo_critical_questions": "",
        },
        "q3": {
            "segments": [],
            "business_flow": "",
            "own_words": "",
            "analogy": "",
            "world_without": "",
        },
        "q4": {
            "money_engine": [],
            "money_summary": "",
            "complexity_status": "Có phần phức tạp",
            "what_can_break": "",
        },
        "q5": {
            "evolution": [],
            "history_summary": "",
            "skill_vs_luck": "",
        },
        "q6": {
            "no_material_foreign_operations": False,
            "foreign_markets": [],
            "foreign_strategy_summary": "",
            "country_risks": [],
            "currency_risks": [],
        },
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
        row = conn.execute("SELECT * FROM chapter2_current WHERE ticker = ?", (ticker,)).fetchone()
    if not row:
        return base
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except Exception:
        payload = {}
    # Preserve forward-compatible defaults when new fields are added later.
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


def _nonempty_table(rows: Any) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if isinstance(row, dict) and any(str(v or "").strip() for v in row.values()):
            return True
    return False


def question_statuses(payload: dict[str, Any]) -> dict[str, str]:
    q1, q2, q3, q4, q5, q6 = (payload.get(f"q{i}", {}) for i in range(1, 7))

    def status(required: list[bool], optional: list[bool] | None = None) -> str:
        optional = optional or []
        if required and all(required):
            return "Answered"
        if any(required + optional):
            return "Partial"
        return "Unknown"

    statuses = {
        "Q1": status([
            bool(str(q1.get("interest_reason", "")).strip()),
            bool(str(q1.get("unknowns", "")).strip()),
        ], [bool(str(q1.get("bias_check", "")).strip())]),
        "Q2": status([
            bool(str(q2.get("underlying_economics", "")).strip()),
            bool(str(q2.get("ceo_critical_questions", "")).strip()),
        ], [bool(str(q2.get("industry_context", "")).strip()), bool(str(q2.get("customers_users", "")).strip())]),
        "Q3": status([
            _nonempty_table(q3.get("segments")),
            bool(str(q3.get("own_words", "")).strip()),
        ], [bool(str(q3.get("business_flow", "")).strip()), bool(str(q3.get("analogy", "")).strip())]),
        "Q4": status([
            _nonempty_table(q4.get("money_engine")),
            bool(str(q4.get("money_summary", "")).strip()),
        ], [bool(str(q4.get("what_can_break", "")).strip())]),
        "Q5": status([
            _nonempty_table(q5.get("evolution")),
            bool(str(q5.get("skill_vs_luck", "")).strip()),
        ], [bool(str(q5.get("history_summary", "")).strip())]),
    }
    if bool(q6.get("no_material_foreign_operations")):
        statuses["Q6"] = "Answered"
    else:
        statuses["Q6"] = status([
            _nonempty_table(q6.get("foreign_markets")),
            bool(str(q6.get("foreign_strategy_summary", "")).strip()),
        ], [_nonempty_table(q6.get("country_risks")), _nonempty_table(q6.get("currency_risks"))])
    return statuses


def understanding_status(payload: dict[str, Any]) -> str:
    statuses = question_statuses(payload)
    answered = sum(1 for value in statuses.values() if value == "Answered")
    if answered >= 5 and statuses.get("Q3") == "Answered" and statuses.get("Q4") == "Answered":
        return "understandable"
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
    status = understanding_status(payload)
    now = _now()
    serialized = json.dumps(payload, ensure_ascii=False)
    with _connect() as conn:
        old = conn.execute("SELECT created_at FROM chapter2_current WHERE ticker = ?", (ticker,)).fetchone()
        created_at = old["created_at"] if old else now
        conn.execute(
            """
            INSERT INTO chapter2_current (ticker, company_name, payload_json, understanding_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name=excluded.company_name,
                payload_json=excluded.payload_json,
                understanding_status=excluded.understanding_status,
                updated_at=excluded.updated_at
            """,
            (ticker, company_name, serialized, status, created_at, now),
        )
        conn.execute(
            "INSERT INTO chapter2_snapshots (ticker, payload_json, understanding_status, created_at) VALUES (?, ?, ?, ?)",
            (ticker, serialized, status, now),
        )
    return status


def load_history(ticker: str) -> pd.DataFrame:
    init_db()
    ticker = _safe_ticker(ticker)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, understanding_status, created_at FROM chapter2_snapshots WHERE ticker = ? ORDER BY id DESC",
            (ticker,),
        ).fetchall()
    return pd.DataFrame([
        {
            "Snapshot": row["id"],
            "Understanding": UNDERSTANDING_LABELS.get(row["understanding_status"], row["understanding_status"]),
            "Thời điểm": row["created_at"],
        }
        for row in rows
    ])


def _rows_to_df(rows: Any, columns: list[str]) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df[columns]


def _df_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    clean = df.copy().fillna("")
    rows = []
    for row in clean.to_dict(orient="records"):
        if any(str(v or "").strip() for v in row.values()):
            rows.append(row)
    return rows


def _render_intro() -> None:
    with st.expander("📘 Hướng dẫn Chương 2 — Understanding the Business: The Basics", expanded=True):
        st.markdown(
            """
**Mục đích:** xác nhận analyst thực sự hiểu doanh nghiệp trước khi đi sâu vào khách hàng, moat, tài chính và quản trị.

Chương 2 bám theo 6 câu hỏi của Michael Shearn: **(1)** có muốn dành nhiều thời gian học doanh nghiệp này, **(2)** nhìn doanh nghiệp như CEO, **(3)** tự mô tả cách doanh nghiệp vận hành, **(4)** hiểu cách doanh nghiệp kiếm tiền, **(5)** hiểu doanh nghiệp đã tiến hóa thế nào, và **(6)** hiểu hoạt động/rủi ro ở thị trường nước ngoài.

**Nguyên tắc sử dụng:** AI/Data có thể hỗ trợ thu thập và draft evidence, nhưng câu trả lời cuối cùng — đặc biệt phần “in your own words”, CEO lens và skill-vs-luck — phải do analyst xác nhận. Chương 2 không tạo BUY/HOLD/SELL và không tự đổi Research Gate của Chương 1.
            """
        )


def render_chapter2(default_ticker: str = "", company_name: str = "") -> None:
    _render_intro()
    ticker = _safe_ticker(st.text_input("Mã cổ phiếu — Chương 2", value=default_ticker or "", key="dca_ch2_ticker"))
    record = load_record(ticker, company_name)
    resolved_name = str(record.get("company_name") or company_name or "")
    company_name_value = st.text_input("Doanh nghiệp", value=resolved_name, key=f"dca_ch2_company_{ticker}")

    st.markdown("## Chương 2 — Hiểu doanh nghiệp: Những điều cơ bản")
    st.caption("Không chấm điểm chất lượng doanh nghiệp. Trạng thái cuối chỉ phản ánh mức độ analyst đã hiểu/hoàn tất 6 câu hỏi.")

    q1 = record["q1"]
    st.markdown("### Q1. Tôi có muốn dành nhiều thời gian để tìm hiểu doanh nghiệp này không?")
    c1, c2, c3 = st.columns(3)
    research_interest = c1.selectbox("Research Interest", RESEARCH_INTEREST, index=RESEARCH_INTEREST.index(q1.get("research_interest", "Trung bình")), key=f"ch2_interest_{ticker}")
    learning_curve = c2.selectbox("Learning Curve", LEARNING_CURVE, index=LEARNING_CURVE.index(q1.get("learning_curve", "Có thể hiểu với thời gian")), key=f"ch2_curve_{ticker}")
    circle_status = c3.selectbox("Circle of Competence", CIRCLE_STATUS, index=CIRCLE_STATUS.index(q1.get("circle_status", "Cần thêm thời gian")), key=f"ch2_circle_{ticker}")
    interest_reason = st.text_area("Vì sao tôi muốn/không muốn tiếp tục học doanh nghiệp này?", value=q1.get("interest_reason", ""), height=90, key=f"ch2_interest_reason_{ticker}")
    unknowns = st.text_area("Learning gaps — điều tôi chưa hiểu", value=q1.get("unknowns", ""), height=90, key=f"ch2_unknowns_{ticker}")
    bias_check = st.text_area("Bias check — tôi có đang yêu thích sản phẩm/ngành hoặc dựa quá nhiều vào người khác không?", value=q1.get("bias_check", ""), height=80, key=f"ch2_bias_{ticker}")

    q2 = record["q2"]
    st.markdown("### Q2. Nếu sắp trở thành CEO, tôi cần hiểu gì về doanh nghiệp này?")
    underlying_economics = st.text_area("Underlying economics — điều gì thực sự tạo ra giá trị và điều gì có thể làm economics thay đổi?", value=q2.get("underlying_economics", ""), height=110, key=f"ch2_econ_{ticker}")
    industry_context = st.text_area("Industry context — lịch sử/cấu trúc ngành và những thay đổi quan trọng", value=q2.get("industry_context", ""), height=90, key=f"ch2_industry_{ticker}")
    customers_users = st.text_area("Customers / users — ai trả tiền, ai sử dụng và họ nhận được lợi ích gì?", value=q2.get("customers_users", ""), height=90, key=f"ch2_customers_{ticker}")
    field_reality_check = st.text_area("Field / reality check — bằng chứng thực địa, sản phẩm, nhà máy, cửa hàng, customer/supplier/employee evidence", value=q2.get("field_reality_check", ""), height=90, key=f"ch2_field_{ticker}")
    ceo_critical_questions = st.text_area("5 câu hỏi đầu tiên nếu ngày mai nhận bàn giao doanh nghiệp", value=q2.get("ceo_critical_questions", ""), height=120, key=f"ch2_ceoq_{ticker}")

    q3 = record["q3"]
    st.markdown("### Q3. Tôi có thể mô tả doanh nghiệp vận hành bằng chính lời của mình không?")
    st.caption("Bảng segment là lớp cấu trúc của Trecapital; phần 'Own words' là kiểm tra quan trọng nhất để xác nhận analyst thực sự hiểu business.")
    segments_df = st.data_editor(_rows_to_df(q3.get("segments"), SEGMENT_COLUMNS), num_rows="dynamic", use_container_width=True, key=f"ch2_segments_{ticker}")
    business_flow = st.text_area("Business Flow — Input → Production/Service → Product → Distribution → Customer → Cash", value=q3.get("business_flow", ""), height=100, key=f"ch2_flow_{ticker}")
    own_words = st.text_area("Explain it to a friend — mô tả doanh nghiệp bằng lời của chính mình trong 5–10 câu", value=q3.get("own_words", ""), height=150, key=f"ch2_ownwords_{ticker}")
    analogy = st.text_input("Analogy — doanh nghiệp này giống cái gì?", value=q3.get("analogy", ""), key=f"ch2_analogy_{ticker}")
    world_without = st.text_area("Nếu sản phẩm/dịch vụ này không tồn tại, quy trình/thế giới của khách hàng sẽ thay đổi thế nào?", value=q3.get("world_without", ""), height=90, key=f"ch2_worldwithout_{ticker}")

    q4 = record["q4"]
    st.markdown("### Q4. Doanh nghiệp kiếm tiền bằng cách nào?")
    money_df = st.data_editor(_rows_to_df(q4.get("money_engine"), MONEY_COLUMNS), num_rows="dynamic", use_container_width=True, key=f"ch2_money_{ticker}")
    money_summary = st.text_area("Money-Making Engine — mô tả ngắn gọn ai trả tiền, volume × price, chi phí chính và profit engine", value=q4.get("money_summary", ""), height=120, key=f"ch2_money_summary_{ticker}")
    complexity_status = st.selectbox("Mức độ hiểu earnings model", COMPLEXITY_STATUS, index=COMPLEXITY_STATUS.index(q4.get("complexity_status", "Có phần phức tạp")), key=f"ch2_complexity_{ticker}")
    what_can_break = st.text_area("Điều gì có thể phá vỡ earnings engine?", value=q4.get("what_can_break", ""), height=90, key=f"ch2_break_{ticker}")
    if complexity_status == "Chưa hiểu đầy đủ cách kiếm tiền":
        st.warning("Earnings Model Not Understood — đây là research warning, không phải tín hiệu bán.")

    q5 = record["q5"]
    st.markdown("### Q5. Doanh nghiệp đã tiến hóa như thế nào theo thời gian?")
    evolution_df = st.data_editor(_rows_to_df(q5.get("evolution"), EVOLUTION_COLUMNS), num_rows="dynamic", use_container_width=True, key=f"ch2_evolution_{ticker}")
    history_summary = st.text_area("10+ year business history summary — các bước ngoặt quan trọng", value=q5.get("history_summary", ""), height=110, key=f"ch2_history_{ticker}")
    skill_vs_luck = st.text_area("Skill vs Luck — thành công lịch sử đến từ năng lực, structural tailwind, tài nguyên, chính sách, timing/luck hay sự kết hợp nào?", value=q5.get("skill_vs_luck", ""), height=110, key=f"ch2_skillluck_{ticker}")

    q6 = record["q6"]
    st.markdown("### Q6. Doanh nghiệp hoạt động ở thị trường nước ngoài nào và rủi ro là gì?")
    no_foreign = st.checkbox("Không có hoạt động nước ngoài trọng yếu / Q6 hiện N/A về mặt thực tế", value=bool(q6.get("no_material_foreign_operations")), key=f"ch2_noforeign_{ticker}")
    foreign_df = st.data_editor(_rows_to_df(q6.get("foreign_markets"), FOREIGN_COLUMNS), num_rows="dynamic", use_container_width=True, disabled=no_foreign, key=f"ch2_foreign_{ticker}")
    foreign_strategy_summary = st.text_area("Foreign-market commitment — thời gian hiện diện, localization/R&D, regional management, revenue→profit", value=q6.get("foreign_strategy_summary", ""), height=110, disabled=no_foreign, key=f"ch2_foreign_summary_{ticker}")
    with st.expander("Country Risk — ưu tiên thị trường có exposure trọng yếu", expanded=False):
        country_risk_df = st.data_editor(_rows_to_df(q6.get("country_risks"), COUNTRY_RISK_COLUMNS), num_rows="dynamic", use_container_width=True, disabled=no_foreign, key=f"ch2_countryrisk_{ticker}")
    with st.expander("Currency Risk / Hedging", expanded=False):
        currency_df = st.data_editor(_rows_to_df(q6.get("currency_risks"), CURRENCY_COLUMNS), num_rows="dynamic", use_container_width=True, disabled=no_foreign, key=f"ch2_currency_{ticker}")

    research_gaps = st.text_area("Research Gaps của Chương 2 — mỗi dòng một điều chưa biết cần chuyển sang chương sau", value=record.get("research_gaps", ""), height=120, key=f"ch2_gaps_{ticker}")
    analyst_summary = st.text_area("Business Understanding Summary — kết luận của analyst", value=record.get("analyst_summary", ""), height=130, key=f"ch2_summary_{ticker}")

    payload = {
        "ticker": ticker,
        "company_name": company_name_value,
        "q1": {
            "research_interest": research_interest,
            "learning_curve": learning_curve,
            "interest_reason": interest_reason,
            "unknowns": unknowns,
            "bias_check": bias_check,
            "circle_status": circle_status,
        },
        "q2": {
            "underlying_economics": underlying_economics,
            "industry_context": industry_context,
            "customers_users": customers_users,
            "field_reality_check": field_reality_check,
            "ceo_critical_questions": ceo_critical_questions,
        },
        "q3": {
            "segments": _df_to_rows(segments_df),
            "business_flow": business_flow,
            "own_words": own_words,
            "analogy": analogy,
            "world_without": world_without,
        },
        "q4": {
            "money_engine": _df_to_rows(money_df),
            "money_summary": money_summary,
            "complexity_status": complexity_status,
            "what_can_break": what_can_break,
        },
        "q5": {
            "evolution": _df_to_rows(evolution_df),
            "history_summary": history_summary,
            "skill_vs_luck": skill_vs_luck,
        },
        "q6": {
            "no_material_foreign_operations": no_foreign,
            "foreign_markets": _df_to_rows(foreign_df),
            "foreign_strategy_summary": foreign_strategy_summary,
            "country_risks": _df_to_rows(country_risk_df),
            "currency_risks": _df_to_rows(currency_df),
        },
        "research_gaps": research_gaps,
        "analyst_summary": analyst_summary,
    }

    statuses = question_statuses(payload)
    overall = understanding_status(payload)
    st.markdown("### Business Understanding Summary")
    cols = st.columns(6)
    for index, key in enumerate(("Q1", "Q2", "Q3", "Q4", "Q5", "Q6")):
        cols[index].metric(key, statuses[key])
    st.info(f"Understanding Status: **{UNDERSTANDING_LABELS[overall]}** — đây là trạng thái completeness/understanding, không phải rating đầu tư.")

    if st.button("💾 Lưu Chương 2", type="primary", use_container_width=True, key=f"ch2_save_{ticker}"):
        if not ticker:
            st.error("Vui lòng nhập mã cổ phiếu.")
        else:
            saved_status = save_record(payload)
            st.success(f"Đã lưu Chương 2 cho {ticker}. Trạng thái: {UNDERSTANDING_LABELS[saved_status]}.")
            st.rerun()

    history = load_history(ticker)
    with st.expander("Version History — Chương 2", expanded=False):
        if history.empty:
            st.caption("Chưa có snapshot.")
        else:
            st.dataframe(history, use_container_width=True, hide_index=True)
