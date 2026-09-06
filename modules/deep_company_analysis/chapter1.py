from __future__ import annotations

import html
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.table_format import render_static_table

from modules.deep_company_analysis.monitoring import evaluate_and_persist, render_monitoring_panel
from modules.deep_company_analysis.structured_triggers import render_structured_trigger_builder

APP_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = APP_ROOT / "data_cache" / "deep_company_analysis_chapter1.db"

QUALITY_CRITERIA = [
    ("recurring_revenue", "Recurring Revenue", "Doanh thu lặp lại"),
    ("long_runway", "Long Runway", "Dư địa tăng trưởng dài hạn"),
    ("proven_management", "Proven Management", "Ban lãnh đạo đã được kiểm chứng"),
    ("franchise_moat", "Franchise / Moat", "Lợi thế cạnh tranh bền vững"),
    ("strong_financials", "Strong Financials", "Nền tảng tài chính mạnh"),
    ("high_roic", "High ROIC", "ROIC cao"),
    ("limited_competition", "Limited Competition", "Cạnh tranh hạn chế"),
    ("low_capex", "Low Capital Expenditures", "Nhu cầu vốn đầu tư thấp"),
    ("diversified_customers", "Diversified Customer Base", "Tệp khách hàng đa dạng"),
    ("strong_balance_sheet", "Strong Balance Sheet", "Bảng cân đối mạnh"),
]

STATUS_OPTIONS = ["— Chưa biết", "✓ Có", "X Không", "N/A"]
CONFIDENCE_LEVELS = {1: "Thấp", 2: "Trung bình", 3: "Cao"}
DGC_TRIAL_PATH = APP_ROOT / "sample_data" / "deep_company_analysis" / "DGC_chapter1_trial.json"
GATES = {
    "continue": ("🟢 Continue", "Tiếp tục nghiên cứu chuyên sâu"),
    "watch": ("🟡 Watch", "Theo dõi, chờ thêm dữ liệu hoặc điều kiện"),
    "pause": ("🟠 Pause", "Tạm dừng nghiên cứu"),
    "reject": ("🔴 Reject", "Loại khỏi pipeline nghiên cứu hiện tại"),
}
IDEA_SOURCE_OPTIONS = [
    "Thị trường giảm mạnh",
    "Ngành đang bị bán mạnh",
    "Cổ phiếu giảm mạnh / gần đáy 52 tuần",
    "Bị loại khỏi chỉ số / forced selling",
    "Spin-off / tái cấu trúc",
    "Sự kiện đặc biệt",
    "Kết quả kinh doanh tạm thời xấu",
    "Bất định pháp lý / quản trị / ngành",
    "Định giá thấp bất thường",
    "Screen định lượng phát hiện",
    "Ý tưởng từ nhà đầu tư khác",
    "Doanh nghiệp chất lượng muốn theo dõi dài hạn",
    "Khác",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _normalize_confidence(value: Any) -> int:
    """Chuẩn hóa Confidence về 3 mức: 1 Thấp, 2 Trung bình, 3 Cao.

    Bản cũ từng dùng thang 1–5; giá trị 4–5 được quy về mức Cao để không làm
    hỏng dữ liệu SQLite đã lưu trước đó. Confidence không tham gia Quality Score.
    """
    try:
        raw = int(value)
    except Exception:
        raw = 1
    if raw <= 1:
        return 1
    if raw == 2:
        return 2
    return 3


def _confidence_label(value: Any) -> str:
    return CONFIDENCE_LEVELS[_normalize_confidence(value)]


def load_dgc_trial_payload() -> dict[str, Any]:
    """Nạp case DGC point-in-time dùng để kiểm thử workflow Chương 1 offline."""
    if not DGC_TRIAL_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy case DGC thử nghiệm: {DGC_TRIAL_PATH}")
    payload = json.loads(DGC_TRIAL_PATH.read_text(encoding="utf-8"))
    if _safe_ticker(payload.get("ticker", "")) != "DGC":
        raise ValueError("Case thử nghiệm không phải DGC")
    return payload


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chapter1_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                idea_sources_json TEXT NOT NULL DEFAULT '[]',
                market_mispricing TEXT NOT NULL DEFAULT '',
                initial_thesis TEXT NOT NULL DEFAULT '',
                research_gaps TEXT NOT NULL DEFAULT '',
                opportunity_signals_json TEXT NOT NULL DEFAULT '{}',
                valuation_json TEXT NOT NULL DEFAULT '{}',
                gate TEXT NOT NULL DEFAULT 'watch',
                gate_reason TEXT NOT NULL DEFAULT '',
                next_review TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapter1_quality_current (
                ticker TEXT NOT NULL,
                criterion_code TEXT NOT NULL,
                analyst_status TEXT NOT NULL DEFAULT '— Chưa biết',
                confidence INTEGER NOT NULL DEFAULT 1,
                note TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (ticker, criterion_code),
                FOREIGN KEY (ticker) REFERENCES chapter1_current(ticker) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chapter1_gate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                old_gate TEXT NOT NULL DEFAULT '',
                new_gate TEXT NOT NULL,
                reason TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapter1_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapter1_monitoring_triggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                trigger_text TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """
        )


def _json_loads(value: str, default: Any) -> Any:
    try:
        loaded = json.loads(value or "")
        return loaded
    except Exception:
        return default


def load_record(ticker: str) -> dict[str, Any]:
    init_db()
    ticker = _safe_ticker(ticker)
    record: dict[str, Any] = {
        "ticker": ticker,
        "_exists": False,
        "company_name": "",
        "idea_sources": [],
        "market_mispricing": "",
        "initial_thesis": "",
        "research_gaps": "",
        "opportunity_signals": {},
        "valuation": {},
        "gate": "watch",
        "gate_reason": "",
        "next_review": "",
        "quality": {code: {"status": "— Chưa biết", "confidence": 1, "note": ""} for code, _, _ in QUALITY_CRITERIA},
        "triggers": [],
    }
    if not ticker:
        return record

    with _connect() as conn:
        row = conn.execute("SELECT * FROM chapter1_current WHERE ticker = ?", (ticker,)).fetchone()
        if row:
            record["_exists"] = True
            record.update(
                {
                    "company_name": row["company_name"],
                    "idea_sources": _json_loads(row["idea_sources_json"], []),
                    "market_mispricing": row["market_mispricing"],
                    "initial_thesis": row["initial_thesis"],
                    "research_gaps": row["research_gaps"],
                    "opportunity_signals": _json_loads(row["opportunity_signals_json"], {}),
                    "valuation": _json_loads(row["valuation_json"], {}),
                    "gate": row["gate"],
                    "gate_reason": row["gate_reason"],
                    "next_review": row["next_review"],
                }
            )
        for qrow in conn.execute("SELECT * FROM chapter1_quality_current WHERE ticker = ?", (ticker,)).fetchall():
            if qrow["criterion_code"] in record["quality"]:
                record["quality"][qrow["criterion_code"]] = {
                    "status": qrow["analyst_status"],
                    "confidence": _normalize_confidence(qrow["confidence"]),
                    "note": qrow["note"],
                }
        record["triggers"] = [
            r["trigger_text"]
            for r in conn.execute(
                "SELECT trigger_text FROM chapter1_monitoring_triggers WHERE ticker = ? AND active = 1 ORDER BY id",
                (ticker,),
            ).fetchall()
        ]
    return record


def _quality_score(quality: dict[str, dict[str, Any]]) -> tuple[int, int]:
    yes = sum(1 for item in quality.values() if str(item.get("status", "")).startswith("✓"))
    unknown = sum(1 for item in quality.values() if str(item.get("status", "")).startswith("—"))
    return yes, unknown


def save_record(payload: dict[str, Any]) -> None:
    init_db()
    ticker = _safe_ticker(payload.get("ticker", ""))
    if not ticker:
        raise ValueError("Ticker không hợp lệ")
    now = _now()
    quality = payload.get("quality", {})

    with _connect() as conn:
        old = conn.execute("SELECT gate FROM chapter1_current WHERE ticker = ?", (ticker,)).fetchone()
        old_gate = old["gate"] if old else ""
        conn.execute(
            """
            INSERT INTO chapter1_current (
                ticker, company_name, idea_sources_json, market_mispricing, initial_thesis,
                research_gaps, opportunity_signals_json, valuation_json, gate, gate_reason,
                next_review, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name=excluded.company_name,
                idea_sources_json=excluded.idea_sources_json,
                market_mispricing=excluded.market_mispricing,
                initial_thesis=excluded.initial_thesis,
                research_gaps=excluded.research_gaps,
                opportunity_signals_json=excluded.opportunity_signals_json,
                valuation_json=excluded.valuation_json,
                gate=excluded.gate,
                gate_reason=excluded.gate_reason,
                next_review=excluded.next_review,
                updated_at=excluded.updated_at
            """,
            (
                ticker,
                str(payload.get("company_name", "")),
                json.dumps(payload.get("idea_sources", []), ensure_ascii=False),
                str(payload.get("market_mispricing", "")),
                str(payload.get("initial_thesis", "")),
                str(payload.get("research_gaps", "")),
                json.dumps(payload.get("opportunity_signals", {}), ensure_ascii=False),
                json.dumps(payload.get("valuation", {}), ensure_ascii=False),
                str(payload.get("gate", "watch")),
                str(payload.get("gate_reason", "")),
                str(payload.get("next_review", "")),
                now,
                now,
            ),
        )
        for code, _, _ in QUALITY_CRITERIA:
            item = quality.get(code, {})
            conn.execute(
                """
                INSERT INTO chapter1_quality_current (ticker, criterion_code, analyst_status, confidence, note, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, criterion_code) DO UPDATE SET
                    analyst_status=excluded.analyst_status,
                    confidence=excluded.confidence,
                    note=excluded.note,
                    updated_at=excluded.updated_at
                """,
                (
                    ticker,
                    code,
                    str(item.get("status", "— Chưa biết")),
                    _normalize_confidence(item.get("confidence", 1)),
                    str(item.get("note", "")),
                    now,
                ),
            )

        new_gate = str(payload.get("gate", "watch"))
        if old_gate != new_gate:
            conn.execute(
                "INSERT INTO chapter1_gate_history (ticker, old_gate, new_gate, reason, changed_at) VALUES (?, ?, ?, ?, ?)",
                (ticker, old_gate, new_gate, str(payload.get("gate_reason", "")), now),
            )

        conn.execute("UPDATE chapter1_monitoring_triggers SET active = 0 WHERE ticker = ?", (ticker,))
        for trigger in payload.get("triggers", []):
            trigger = str(trigger).strip()
            if trigger:
                conn.execute(
                    "INSERT INTO chapter1_monitoring_triggers (ticker, trigger_text, active, created_at) VALUES (?, ?, 1, ?)",
                    (ticker, trigger, now),
                )

        snapshot = dict(payload)
        yes, unknown = _quality_score(quality)
        snapshot["quality_score"] = yes
        snapshot["unknown_count"] = unknown
        conn.execute(
            "INSERT INTO chapter1_snapshots (ticker, payload_json, created_at) VALUES (?, ?, ?)",
            (ticker, json.dumps(snapshot, ensure_ascii=False), now),
        )


def load_inventory() -> pd.DataFrame:
    init_db()
    rows: list[dict[str, Any]] = []
    with _connect() as conn:
        current = conn.execute("SELECT * FROM chapter1_current ORDER BY updated_at DESC").fetchall()
        for row in current:
            quality_rows = conn.execute(
                "SELECT analyst_status FROM chapter1_quality_current WHERE ticker = ?", (row["ticker"],)
            ).fetchall()
            statuses = [r["analyst_status"] for r in quality_rows]
            quality_score = sum(1 for value in statuses if str(value).startswith("✓"))
            unknown_count = sum(1 for value in statuses if str(value).startswith("—"))
            valuation = _json_loads(row["valuation_json"], {})
            rows.append(
                {
                    "Gate": GATES.get(row["gate"], (row["gate"], ""))[0],
                    "Mã": row["ticker"],
                    "Doanh nghiệp": row["company_name"] or "—",
                    "Quality": f"{quality_score}/10",
                    "Unknown": unknown_count,
                    "Giá": valuation.get("current_price"),
                    "Target": valuation.get("target_price"),
                    "MOS %": valuation.get("mos_pct"),
                    "FCF Yield %": valuation.get("fcf_yield_pct"),
                    "Gate reason": row["gate_reason"] or "—",
                    "Next review": row["next_review"] or "—",
                    "Cập nhật": row["updated_at"],
                    "gate_key": row["gate"],
                }
            )
    return pd.DataFrame(rows)


def load_gate_history(ticker: str) -> pd.DataFrame:
    ticker = _safe_ticker(ticker)
    if not ticker:
        return pd.DataFrame()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT old_gate, new_gate, reason, changed_at FROM chapter1_gate_history WHERE ticker = ? ORDER BY id DESC",
            (ticker,),
        ).fetchall()
    data = []
    for row in rows:
        data.append(
            {
                "Thời điểm": row["changed_at"],
                "Gate cũ": GATES.get(row["old_gate"], (row["old_gate"] or "—", ""))[0],
                "Gate mới": GATES.get(row["new_gate"], (row["new_gate"], ""))[0],
                "Lý do": row["reason"] or "—",
            }
        )
    return pd.DataFrame(data)


def _fmt_number(value: Any, decimals: int = 1, suffix: str = "") -> str:
    try:
        if value is None or value == "":
            return "—"
        return f"{float(value):,.{decimals}f}{suffix}"
    except Exception:
        return "—"


def _html_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<div style='padding:12px;border:1px solid #d7cfbe;border-radius:8px'>Chưa có dữ liệu.</div>"
    cols = list(df.columns)
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    body_rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(str(row[c]))}</td>" for c in cols)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"""
    <div style="overflow-x:auto;width:100%">
      <table style="width:100%;table-layout:fixed;border-collapse:collapse;font-size:0.9rem">
        <thead><tr>{head}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
      </table>
    </div>
    <style>
      table th, table td {{border:1px solid #d7cfbe;padding:8px;vertical-align:top;white-space:normal;overflow-wrap:anywhere}}
      table th {{background:#f3efe4;color:#0b2a25}}
    </style>
    """


def _render_inventory() -> None:
    st.subheader("Opportunity Inventory / Table 1.2")
    st.caption(
        "Danh sách được tự động tổng hợp từ Research Gate. Gate chỉ thay đổi khi analyst lưu đánh giá; app không tự đổi Gate."
    )
    inventory = load_inventory()
    for gate_key in ["continue", "watch", "pause", "reject"]:
        gate_label, gate_desc = GATES[gate_key]
        st.markdown(f"#### {gate_label} — {gate_desc}")
        if inventory.empty:
            subset = pd.DataFrame()
        else:
            subset = inventory[inventory["gate_key"] == gate_key].drop(columns=["gate_key"], errors="ignore").copy()
        render_static_table(
            subset,
            use_container_width=True,
            hide_index=True,
            height=min(420, 78 + 38 * max(1, len(subset))),
        )


def render_chapter1(default_ticker: str = "", auto_data: dict[str, Any] | None = None, auto_company_name: str = "") -> None:
    init_db()
    auto_data = auto_data or {}
    auto_valuation = auto_data.get("valuation", {}) if isinstance(auto_data, dict) else {}
    auto_quality = auto_data.get("quality_suggestions", {}) if isinstance(auto_data, dict) else {}
    auto_signals = auto_data.get("opportunity_signals", {}) if isinstance(auto_data, dict) else {}
    st.markdown("## Chương 1 — Hình thành & Sàng lọc Cơ hội đầu tư")
    st.caption(
        "Nguồn sách: Chapter 1 — How to Generate Investment Ideas. Phần Research Gate và monitoring là lớp triển khai của Trecapital để quản lý pipeline nghiên cứu."
    )
    st.info(
        "Chế độ offline: dữ liệu Chương 1 được lưu cục bộ bằng SQLite tại data_cache/deep_company_analysis_chapter1.db. "
        "Không cần API hay kết nối mạng để nhập, lưu, mở lại và quản lý Opportunity Inventory.",
        icon="💾",
    )

    top1, top2 = st.columns([1, 2])
    with top1:
        ticker = _safe_ticker(st.text_input("Mã cổ phiếu", value=_safe_ticker(default_ticker) or "DCM", key="dca_ch1_ticker"))
    record = load_record(ticker)
    is_saved = bool(record.get("_exists"))
    with top2:
        company_default = record.get("company_name", "") or (auto_company_name if not is_saved else "")
        company_name = st.text_input("Tên doanh nghiệp", value=company_default, key=f"dca_company_{ticker}")

    if ticker == "DGC":
        st.caption("Có sẵn case DGC thử nghiệm point-in-time để kiểm tra workflow Chương 1; đây không phải dữ liệu live.")
        if st.button("🧪 Nạp case thử nghiệm DGC (as-of 28/08/2026)", key="dca_load_dgc_trial"):
            try:
                save_record(load_dgc_trial_payload())
                st.success("Đã nạp case DGC thử nghiệm vào SQLite local.")
                st.rerun()
            except Exception as exc:
                st.error(f"Không nạp được case DGC: {exc}")

    st.markdown("### A. Tại sao doanh nghiệp này xuất hiện trên radar?")
    idea_sources = st.multiselect(
        "Nguồn hình thành ý tưởng",
        IDEA_SOURCE_OPTIONS,
        default=[x for x in record.get("idea_sources", []) if x in IDEA_SOURCE_OPTIONS],
        key=f"dca_idea_sources_{ticker}",
    )
    market_mispricing = st.text_area(
        "Tại sao thị trường có thể đang định giá sai doanh nghiệp này?",
        value=record.get("market_mispricing", ""),
        height=110,
        key=f"dca_mispricing_{ticker}",
    )
    initial_thesis = st.text_area(
        "Initial thesis / Luận điểm ban đầu",
        value=record.get("initial_thesis", ""),
        height=110,
        key=f"dca_thesis_{ticker}",
    )

    st.markdown("### B. Opportunity Signals")
    st.caption(
        "Tín hiệu định lượng được prefill từ pipeline chung của Trecapital: price history FireAnt đã lưu + BCTC canonical + Table 1.2 proxy. "
        "Event Signal chỉ là ứng viên từ WebEvidence và luôn cần analyst xác minh; tất cả đều là research signal, không phải Buy Signal."
    )
    sig = record.get("opportunity_signals", {})

    def _signal_value(key: str, fallback: Any = None, *, prefer_auto: bool = True) -> Any:
        auto_value = auto_signals.get(key) if isinstance(auto_signals, dict) else None
        saved_value = sig.get(key) if isinstance(sig, dict) else None
        if prefer_auto and auto_value not in (None, ""):
            return auto_value
        if saved_value not in (None, ""):
            return saved_value
        if auto_value not in (None, ""):
            return auto_value
        return fallback

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        drawdown_52w = st.number_input(
            "Giảm từ đỉnh 52 tuần (%)",
            value=float(_signal_value("drawdown_52w_pct", 0.0) or 0.0),
            step=0.1,
            format="%.1f",
            key=f"dca_dd_{ticker}",
        )
        if auto_signals.get("high_52w") is not None:
            st.caption(
                f"52W High {_fmt_number(auto_signals.get('high_52w'), 0)} | Low {_fmt_number(auto_signals.get('low_52w'), 0)} | "
                f"as-of {auto_signals.get('price_history_as_of') or '—'} | {int(auto_signals.get('price_history_observations') or 0)} phiên"
            )
    with c2:
        valuation_percentile = st.number_input(
            "Valuation percentile lịch sử (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(_signal_value("valuation_percentile", 0.0) or 0.0),
            step=1.0,
            format="%.1f",
            key=f"dca_vp_{ticker}",
        )
        if auto_signals.get("valuation_metric"):
            st.caption(
                f"{auto_signals.get('valuation_metric')} hiện tại {_fmt_number(auto_signals.get('valuation_current'), 1)} | "
                f"{int(auto_signals.get('valuation_history_n') or 0)} kỳ lịch sử | 0%=rẻ nhất, 100%=đắt nhất"
            )
    with c3:
        divergence_options = ["— Chưa xác định", "Có", "Không"]
        divergence_default = str(_signal_value("price_earnings_divergence", "— Chưa xác định") or "— Chưa xác định")
        if divergence_default not in divergence_options:
            divergence_default = "— Chưa xác định"
        price_earnings_divergence = st.selectbox(
            "Giá giảm nhưng earnings/cash flow cải thiện?",
            divergence_options,
            index=divergence_options.index(divergence_default),
            key=f"dca_div_{ticker}",
        )
        if auto_signals.get("divergence_evidence"):
            st.caption(str(auto_signals.get("divergence_evidence")))
    with c4:
        saved_event = str(sig.get("special_event", "") or "")
        event_candidate = str(auto_signals.get("special_event", "") or "")
        event_default = saved_event or (event_candidate if not is_saved else "")
        special_event = st.text_input("Sự kiện/forced selling", value=event_default, key=f"dca_event_{ticker}")
        if event_candidate:
            st.caption(event_candidate)
            st.caption("Ứng viên tự động — phải mở nguồn/CBTT để xác minh trước khi dùng làm kết luận.")

    event_candidates = auto_signals.get("event_candidates", []) if isinstance(auto_signals, dict) else []
    if event_candidates:
        with st.expander("Event Signal — bằng chứng ứng viên", expanded=False):
            for event in event_candidates[:5]:
                st.markdown(f"- **{event.get('category') or 'Sự kiện'}:** {event.get('title') or '—'}")
                if event.get("snippet"):
                    st.caption(str(event.get("snippet")))
                if event.get("url"):
                    st.caption(f"Nguồn: {event.get('url')}")
    elif auto_data:
        st.caption("Event Signal: chưa tìm thấy ứng viên có keyword đủ rõ trong WebEvidence cache. Analyst vẫn có thể nhập thủ công.")

    st.markdown("### C. Quality Filter — Table 1.1")
    st.caption(
        "Data Suggested dùng dữ liệu canonical Trecapital cho 4 tiêu chí định lượng. "
        "Nếu ticker chưa từng được lưu, app prefill đề xuất để analyst kiểm tra; bản đã lưu không bao giờ bị ghi đè. "
        "Confidence chỉ có Thấp / Trung bình / Cao và không cộng vào Quality Score."
    )
    quality: dict[str, dict[str, Any]] = {}
    header = st.columns([2.0, 1.25, 1.05, 1.0, 2.8])
    header[0].markdown("**Tiêu chí**")
    header[1].markdown("**Data Suggested**")
    header[2].markdown("**Analyst**")
    header[3].markdown("**Confidence**")
    header[4].markdown("**Evidence / Note**")
    for code, book_label, vi_label in QUALITY_CRITERIA:
        item = record["quality"].get(code, {"status": "— Chưa biết", "confidence": 1, "note": ""})
        suggested = auto_quality.get(code, {}) if isinstance(auto_quality, dict) else {}
        cols = st.columns([2.0, 1.25, 1.05, 1.0, 2.8])
        with cols[0]:
            st.markdown(f"**{book_label}**  \n{vi_label}")
        with cols[1]:
            if suggested:
                suggested_status = str(suggested.get("status", "— Chưa biết"))
                st.markdown(f"**{suggested_status}**")
                st.caption(f"Nguồn: Trecapital | {_confidence_label(suggested.get('confidence', 1))}")
            else:
                st.markdown("—")
        with cols[2]:
            current_status = item.get("status", "— Chưa biết")
            if not is_saved and suggested and current_status == "— Chưa biết":
                current_status = str(suggested.get("status", current_status))
            status = st.selectbox(
                f"Trạng thái {book_label}",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0,
                label_visibility="collapsed",
                key=f"dca_q_status_{ticker}_{code}",
            )
        with cols[3]:
            current_confidence = _normalize_confidence(item.get("confidence", 1))
            if not is_saved and suggested:
                current_confidence = _normalize_confidence(suggested.get("confidence", current_confidence))
            confidence = st.selectbox(
                f"Confidence {book_label}",
                list(CONFIDENCE_LEVELS),
                index=list(CONFIDENCE_LEVELS).index(current_confidence),
                format_func=lambda level: CONFIDENCE_LEVELS[level],
                label_visibility="collapsed",
                key=f"dca_q_conf_{ticker}_{code}",
            )
        with cols[4]:
            note_default = str(item.get("note", ""))
            if not is_saved and not note_default and suggested:
                note_default = str(suggested.get("evidence", ""))
            note = st.text_input(
                f"Note {book_label}", value=note_default, label_visibility="collapsed", key=f"dca_q_note_{ticker}_{code}"
            )
            if suggested and suggested.get("rule"):
                st.caption(str(suggested.get("rule")))
        quality[code] = {"status": status, "confidence": confidence, "note": note}
    quality_score, unknown_count = _quality_score(quality)
    m1, m2, m3 = st.columns(3)
    m1.metric("Quality Filter", f"{quality_score}/10")
    m2.metric("Unknown", f"{unknown_count}/10")
    m3.metric("Mục đích", "Research filter")
    st.caption("Quality score không phải tín hiệu mua/bán.")

    st.markdown("### D. Research Gaps")
    research_gaps = st.text_area(
        "Những điều chưa biết / Critical Unknowns — mỗi dòng một nội dung",
        value=record.get("research_gaps", ""),
        height=130,
        key=f"dca_gaps_{ticker}",
    )

    st.markdown("### E. Valuation Snapshot — Table 1.2 bridge")
    valuation = record.get("valuation", {})

    def _auto_value(key: str, fallback: float = 0.0) -> float:
        if key in valuation and valuation.get(key) is not None:
            return float(valuation.get(key))
        value = auto_valuation.get(key) if isinstance(auto_valuation, dict) else None
        return fallback if value is None else float(value)

    if auto_valuation:
        st.caption(
            f"Prefill từ Trecapital canonical data | kỳ {auto_data.get('as_of') or '—'} | "
            f"nguồn {auto_data.get('source_module') or 'Trecapital'}. Analyst có thể chỉnh trước khi lưu snapshot."
        )
    else:
        st.caption("Chưa có canonical data cho ticker này; các ô vẫn cho phép analyst nhập thủ công.")

    r1 = st.columns(4)
    with r1[0]:
        current_price = st.number_input("Giá hiện tại", min_value=0.0, value=_auto_value("current_price"), step=100.0, key=f"dca_price_{ticker}")
    with r1[1]:
        target_price = st.number_input("Target Price", min_value=0.0, value=_auto_value("target_price"), step=100.0, key=f"dca_target_{ticker}")
    with r1[2]:
        fcf_yield_pct = st.number_input("FCF Yield (%)", value=_auto_value("fcf_yield_pct"), step=0.1, format="%.1f", key=f"dca_fcfy_{ticker}")
    with r1[3]:
        dividend_yield_pct = st.number_input("Dividend Yield (%)", value=_auto_value("dividend_yield_pct"), step=0.1, format="%.1f", key=f"dca_divy_{ticker}")
    r2 = st.columns(4)
    with r2[0]:
        tev_ebit = st.number_input("TEV / EBIT (x)", value=_auto_value("tev_ebit"), step=0.1, format="%.1f", key=f"dca_te_{ticker}")
    with r2[1]:
        tev_ebitda = st.number_input("TEV / EBITDA (x)", value=_auto_value("tev_ebitda"), step=0.1, format="%.1f", key=f"dca_tebitda_{ticker}")
    with r2[2]:
        debt_ebitda = st.number_input("Debt / EBITDA (x)", value=_auto_value("debt_ebitda"), step=0.1, format="%.1f", key=f"dca_debt_{ticker}")
    with r2[3]:
        ebit_interest = st.number_input("EBIT / Interest (x)", value=_auto_value("ebit_interest"), step=0.1, format="%.1f", key=f"dca_interest_{ticker}")

    source_notes = auto_data.get("source_notes", []) if isinstance(auto_data, dict) else []
    if source_notes:
        with st.expander("Nguồn & reconciliation notes từ Trecapital", expanded=False):
            for source_note in source_notes:
                st.markdown(f"- {source_note}")
    mos_pct = ((target_price - current_price) / target_price * 100.0) if target_price > 0 else None
    price_vs_target_pct = (current_price / target_price * 100.0) if target_price > 0 else None
    x1, x2 = st.columns(2)
    x1.metric("MOS so với Target", _fmt_number(mos_pct, 1, "%"))
    x2.metric("Stock Price / Target", _fmt_number(price_vs_target_pct, 1, "%"))

    st.markdown("### F. Research Gate")
    gate_keys = list(GATES)
    current_gate = record.get("gate", "watch") if record.get("gate", "watch") in GATES else "watch"
    gate = st.selectbox(
        "Research Gate",
        gate_keys,
        index=gate_keys.index(current_gate),
        format_func=lambda key: f"{GATES[key][0]} — {GATES[key][1]}",
        key=f"dca_gate_{ticker}",
    )
    gate_reason = st.text_area(
        "Reason for Gate — bắt buộc ghi rõ vì sao",
        value=record.get("gate_reason", ""),
        height=90,
        key=f"dca_gate_reason_{ticker}",
    )
    next_review = st.text_input(
        "Next review / Điều kiện xem lại",
        value=record.get("next_review", ""),
        placeholder="Ví dụ: Sau BCTC Q3/2026 hoặc khi giá < 80.000",
        key=f"dca_next_review_{ticker}",
    )
    configured_triggers = render_structured_trigger_builder(ticker, list(record.get("triggers", [])))
    st.warning(
        "Monitoring Engine tự kiểm tra các trigger đã lưu khi dữ liệu Trecapital được cập nhật, nhưng không bao giờ tự đổi Research Gate. Gate vẫn là quyết định của analyst.",
        icon="⚠️",
    )

    evaluation_results: list[dict[str, Any]] = []
    if is_saved and auto_data and record.get("triggers"):
        try:
            evaluation_results = evaluate_and_persist(ticker, record, auto_data)
        except Exception as exc:
            st.caption(f"Monitoring Engine chưa đánh giá được trigger: {exc}")

    if st.button("💾 Lưu đánh giá Chương 1", type="primary", use_container_width=True, key=f"dca_save_{ticker}"):
        if not ticker:
            st.error("Vui lòng nhập mã cổ phiếu.")
        elif not gate_reason.strip():
            st.error("Reason for Gate là bắt buộc.")
        else:
            payload = {
                "ticker": ticker,
                "company_name": company_name,
                "idea_sources": idea_sources,
                "market_mispricing": market_mispricing,
                "initial_thesis": initial_thesis,
                "research_gaps": research_gaps,
                "opportunity_signals": {
                    **(auto_signals if isinstance(auto_signals, dict) else {}),
                    "drawdown_52w_pct": drawdown_52w,
                    "valuation_percentile": valuation_percentile,
                    "price_earnings_divergence": price_earnings_divergence,
                    "special_event": special_event,
                },
                "valuation": {
                    "current_price": current_price,
                    "target_price": target_price,
                    "mos_pct": mos_pct,
                    "stock_price_vs_target_pct": price_vs_target_pct,
                    "fcf_yield_pct": fcf_yield_pct,
                    "dividend_yield_pct": dividend_yield_pct,
                    "tev_ebit": tev_ebit,
                    "tev_ebitda": tev_ebitda,
                    "debt_ebitda": debt_ebitda,
                    "ebit_interest": ebit_interest,
                },
                "quality": quality,
                "gate": gate,
                "gate_reason": gate_reason,
                "next_review": next_review,
                "triggers": configured_triggers,
            }
            save_record(payload)
            st.success(f"Đã lưu {ticker}. Opportunity Inventory được cập nhật tự động vào nhóm {GATES[gate][0]}.")
            st.rerun()

    st.divider()
    _render_inventory()
    render_monitoring_panel(ticker, evaluation_results)

    history = load_gate_history(ticker)
    st.subheader(f"Gate History — {ticker}")
    render_static_table(history, use_container_width=True, hide_index=True, height=300)
