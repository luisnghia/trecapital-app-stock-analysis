from __future__ import annotations

import hashlib
import html
import json
import math
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

APP_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = APP_ROOT / "data_cache" / "deep_company_analysis_chapter1.db"


@dataclass(frozen=True)
class TriggerRule:
    kind: str
    metric: str = ""
    operator: str = ""
    threshold: Optional[float] = None
    label: str = ""


METRIC_SPECS = (
    ("current_price", "Giá", (r"\bgi[aá]\b", r"\bprice\b", r"th[iị] gi[aá]")),
    ("mos_pct", "MOS", (r"\bmos\b", r"margin of safety", r"bi[eê]n an to[aà]n")),
    ("roic_pct", "ROIC", (r"\broic\b",)),
    ("debt_ebitda", "Debt/EBITDA", (r"debt\s*/?\s*ebitda", r"n[oợ]\s*/?\s*ebitda")),
    ("ebit_interest", "EBIT/Interest", (r"ebit\s*/?\s*interest", r"interest cover", r"kh[aả] n[aă]ng tr[aả] l[aã]i")),
    ("fcf_yield_pct", "FCF Yield", (r"fcf\s*yield", r"free cash flow yield")),
    ("valuation_percentile", "Valuation Percentile", (r"valuation\s*percentile", r"percentile.*[dđ]ịnh gi[aá]", r"[dđ]ịnh gi[aá].*percentile")),
    ("drawdown_52w_pct", "52W Drawdown", (r"drawdown", r"gi[aả]m.*[dđ]ỉnh.*52", r"52\s*w.*drawdown")),
)

PRIORITY_BY_METRIC = {
    "roic_pct": "Cao",
    "debt_ebitda": "Cao",
    "ebit_interest": "Cao",
    "event_new": "Cao",
    "statement_new": "Trung bình",
    "current_price": "Trung bình",
    "mos_pct": "Trung bình",
    "fcf_yield_pct": "Trung bình",
    "valuation_percentile": "Trung bình",
    "drawdown_52w_pct": "Trung bình",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip()


def _parse_number(token: str, metric: str) -> Optional[float]:
    raw = str(token or "").strip().replace("%", "").replace("x", "").replace("X", "")
    raw = re.sub(r"\s+", "", raw)
    if not raw:
        return None
    if metric == "current_price":
        # Vietnamese stock-price input commonly uses 80.000 or 80,000 for 80,000 VND.
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", raw):
            raw = raw.replace(".", "").replace(",", "")
        elif "," in raw and "." not in raw:
            raw = raw.replace(",", ".")
    else:
        if "," in raw and "." not in raw:
            raw = raw.replace(",", ".")
        elif "," in raw and "." in raw:
            raw = raw.replace(",", "")
    try:
        return float(raw)
    except Exception:
        return None


def parse_trigger(text: str) -> TriggerRule:
    original = str(text or "").strip()
    normalized = _norm(original)
    if not normalized:
        return TriggerRule("unsupported", label=original)

    if re.search(r"\bbctc\s*moi\b|bao cao tai chinh moi|co bctc moi|sau bctc", normalized):
        return TriggerRule("statement_new", label="BCTC mới")
    if re.search(r"event moi|su kien moi|cbtt moi|cong bo thong tin moi|tin phap ly moi|tin quan tri moi", normalized):
        return TriggerRule("event_new", label="Sự kiện/CBTT mới")

    op_match = re.search(r"(<=|>=|<|>|=)\s*([0-9][0-9.,]*)\s*(%|x)?", normalized)
    if not op_match:
        return TriggerRule("unsupported", label=original)
    operator, number_token = op_match.group(1), op_match.group(2)

    for metric, label, patterns in METRIC_SPECS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            threshold = _parse_number(number_token, metric)
            if threshold is None:
                return TriggerRule("unsupported", label=original)
            return TriggerRule("numeric", metric=metric, operator=operator, threshold=threshold, label=label)
    return TriggerRule("unsupported", label=original)


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "=":
        return abs(value - threshold) <= max(1e-9, abs(threshold) * 1e-6)
    return False


def _metric_values(auto_data: dict[str, Any]) -> dict[str, Optional[float]]:
    valuation = auto_data.get("valuation", {}) if isinstance(auto_data, dict) else {}
    signals = auto_data.get("opportunity_signals", {}) if isinstance(auto_data, dict) else {}
    monitoring = auto_data.get("monitoring_metrics", {}) if isinstance(auto_data, dict) else {}
    return {
        "current_price": _safe_float(monitoring.get("current_price", valuation.get("current_price"))),
        "mos_pct": _safe_float(monitoring.get("mos_pct", valuation.get("mos_pct"))),
        "roic_pct": _safe_float(monitoring.get("roic_pct")),
        "debt_ebitda": _safe_float(monitoring.get("debt_ebitda", valuation.get("debt_ebitda"))),
        "ebit_interest": _safe_float(monitoring.get("ebit_interest", valuation.get("ebit_interest"))),
        "fcf_yield_pct": _safe_float(monitoring.get("fcf_yield_pct", valuation.get("fcf_yield_pct"))),
        "valuation_percentile": _safe_float(monitoring.get("valuation_percentile", signals.get("valuation_percentile"))),
        "drawdown_52w_pct": _safe_float(monitoring.get("drawdown_52w_pct", signals.get("drawdown_52w_pct"))),
    }


def _event_signature(event: dict[str, Any]) -> str:
    raw = "|".join(str(event.get(k, "") or "") for k in ("category", "title", "url"))
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:20]


def _current_event_signatures(auto_data: dict[str, Any]) -> list[str]:
    signals = auto_data.get("opportunity_signals", {}) if isinstance(auto_data, dict) else {}
    events = signals.get("event_candidates", []) if isinstance(signals, dict) else []
    return sorted({_event_signature(event) for event in events if isinstance(event, dict) and (event.get("title") or event.get("url"))})


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_monitoring_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chapter1_trigger_state (
                ticker TEXT NOT NULL,
                trigger_text TEXT NOT NULL,
                trigger_kind TEXT NOT NULL,
                metric TEXT NOT NULL DEFAULT '',
                operator TEXT NOT NULL DEFAULT '',
                threshold REAL,
                last_status TEXT NOT NULL DEFAULT '',
                last_triggered INTEGER NOT NULL DEFAULT 0,
                last_value TEXT NOT NULL DEFAULT '',
                baseline_json TEXT NOT NULL DEFAULT '{}',
                evidence TEXT NOT NULL DEFAULT '',
                data_as_of TEXT NOT NULL DEFAULT '',
                checked_at TEXT NOT NULL,
                PRIMARY KEY (ticker, trigger_text)
            );

            CREATE TABLE IF NOT EXISTS chapter1_review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                trigger_text TEXT NOT NULL,
                trigger_kind TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Trung bình',
                reason TEXT NOT NULL,
                observed_value TEXT NOT NULL DEFAULT '',
                threshold TEXT NOT NULL DEFAULT '',
                data_as_of TEXT NOT NULL DEFAULT '',
                detected_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                resolved_at TEXT NOT NULL DEFAULT ''
            );
            """
        )


def _load_state(ticker: str, trigger_text: str) -> Optional[sqlite3.Row]:
    init_monitoring_db()
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM chapter1_trigger_state WHERE ticker = ? AND trigger_text = ?",
            (ticker, trigger_text),
        ).fetchone()


def _baseline(row: Optional[sqlite3.Row]) -> dict[str, Any]:
    if not row:
        return {}
    try:
        return json.loads(row["baseline_json"] or "{}")
    except Exception:
        return {}


def evaluate_trigger(ticker: str, trigger_text: str, auto_data: dict[str, Any], previous_state: Optional[sqlite3.Row] = None) -> dict[str, Any]:
    rule = parse_trigger(trigger_text)
    data_as_of = str(auto_data.get("as_of") or "")
    result: dict[str, Any] = {
        "ticker": ticker,
        "trigger_text": trigger_text,
        "kind": rule.kind,
        "metric": rule.metric,
        "operator": rule.operator,
        "threshold": rule.threshold,
        "triggered": False,
        "status": "unsupported",
        "observed_value": "",
        "evidence": "Trigger chưa thuộc cú pháp tự động hỗ trợ; vẫn được giữ để analyst theo dõi thủ công.",
        "data_as_of": data_as_of,
        "baseline": _baseline(previous_state),
    }

    if rule.kind == "numeric":
        value = _metric_values(auto_data).get(rule.metric)
        if value is None:
            result.update(status="missing_data", evidence=f"Chưa có dữ liệu tự động cho {rule.label}.")
            return result
        hit = _compare(value, rule.operator, float(rule.threshold))
        suffix = "%" if rule.metric in {"mos_pct", "roic_pct", "fcf_yield_pct", "valuation_percentile", "drawdown_52w_pct"} else ("x" if rule.metric in {"debt_ebitda", "ebit_interest"} else "")
        result.update(
            triggered=hit,
            status="triggered" if hit else "armed",
            observed_value=f"{value:,.1f}{suffix}" if rule.metric != "current_price" else f"{value:,.0f}",
            evidence=f"{rule.label} hiện tại {value:,.1f}{suffix} {'đã' if hit else 'chưa'} thỏa {rule.operator} {float(rule.threshold):,.1f}{suffix}.",
        )
        return result

    if rule.kind == "statement_new":
        baseline = result["baseline"]
        previous_as_of = str(baseline.get("statement_as_of") or "")
        if not data_as_of:
            result.update(status="missing_data", evidence="Chưa có kỳ BCTC canonical để kiểm tra trigger.")
            return result
        if not previous_as_of:
            result["baseline"] = {**baseline, "statement_as_of": data_as_of}
            result.update(status="armed", observed_value=data_as_of, evidence=f"Đã đặt mốc BCTC ban đầu: {data_as_of}.")
            return result
        hit = data_as_of != previous_as_of
        result.update(
            triggered=hit,
            status="triggered" if hit else "armed",
            observed_value=data_as_of,
            evidence=(f"Có kỳ dữ liệu mới: {previous_as_of} → {data_as_of}." if hit else f"Chưa có BCTC mới so với mốc {previous_as_of}."),
        )
        if hit:
            result["baseline"] = {**baseline, "statement_as_of": data_as_of}
        return result

    if rule.kind == "event_new":
        current = _current_event_signatures(auto_data)
        baseline = result["baseline"]
        previous = set(baseline.get("event_signatures") or [])
        if not baseline.get("event_initialized"):
            result["baseline"] = {**baseline, "event_initialized": True, "event_signatures": current}
            result.update(status="armed", observed_value=str(len(current)), evidence=f"Đã đặt mốc {len(current)} event candidate hiện có.")
            return result
        new_items = [sig for sig in current if sig not in previous]
        hit = bool(new_items)
        result.update(
            triggered=hit,
            status="triggered" if hit else "armed",
            observed_value=str(len(new_items)),
            evidence=(f"Phát hiện {len(new_items)} event/CBTT candidate mới cần xác minh." if hit else "Chưa có event candidate mới so với lần kiểm tra trước."),
            baseline={**baseline, "event_initialized": True, "event_signatures": current},
        )
        return result

    return result


def _insert_queue_if_transition(conn: sqlite3.Connection, result: dict[str, Any], previous_triggered: bool) -> None:
    if not result.get("triggered") or previous_triggered:
        return
    metric_key = str(result.get("metric") or result.get("kind") or "")
    priority = PRIORITY_BY_METRIC.get(metric_key, "Trung bình")
    conn.execute(
        """
        INSERT INTO chapter1_review_queue (
            ticker, trigger_text, trigger_kind, priority, reason, observed_value,
            threshold, data_as_of, detected_at, status, resolved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', '')
        """,
        (
            result.get("ticker", ""),
            result.get("trigger_text", ""),
            result.get("kind", ""),
            priority,
            result.get("evidence", ""),
            str(result.get("observed_value", "") or ""),
            "" if result.get("threshold") is None else str(result.get("threshold")),
            result.get("data_as_of", ""),
            _now(),
        ),
    )


def evaluate_and_persist(ticker: str, record: dict[str, Any], auto_data: dict[str, Any]) -> list[dict[str, Any]]:
    init_monitoring_db()
    safe = str(ticker or "").upper().strip()
    triggers = [str(x).strip() for x in (record.get("triggers") or []) if str(x).strip()]
    results: list[dict[str, Any]] = []
    with _connect() as conn:
        for trigger_text in triggers:
            state = conn.execute(
                "SELECT * FROM chapter1_trigger_state WHERE ticker = ? AND trigger_text = ?",
                (safe, trigger_text),
            ).fetchone()
            previous_triggered = bool(state["last_triggered"]) if state else False
            result = evaluate_trigger(safe, trigger_text, auto_data, state)
            results.append(result)
            _insert_queue_if_transition(conn, result, previous_triggered)
            conn.execute(
                """
                INSERT INTO chapter1_trigger_state (
                    ticker, trigger_text, trigger_kind, metric, operator, threshold,
                    last_status, last_triggered, last_value, baseline_json, evidence,
                    data_as_of, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, trigger_text) DO UPDATE SET
                    trigger_kind=excluded.trigger_kind,
                    metric=excluded.metric,
                    operator=excluded.operator,
                    threshold=excluded.threshold,
                    last_status=excluded.last_status,
                    last_triggered=excluded.last_triggered,
                    last_value=excluded.last_value,
                    baseline_json=excluded.baseline_json,
                    evidence=excluded.evidence,
                    data_as_of=excluded.data_as_of,
                    checked_at=excluded.checked_at
                """,
                (
                    safe,
                    trigger_text,
                    result.get("kind", ""),
                    result.get("metric", ""),
                    result.get("operator", ""),
                    result.get("threshold"),
                    result.get("status", ""),
                    1 if result.get("triggered") else 0,
                    str(result.get("observed_value", "") or ""),
                    json.dumps(result.get("baseline", {}), ensure_ascii=False),
                    result.get("evidence", ""),
                    result.get("data_as_of", ""),
                    _now(),
                ),
            )
    return results


def load_trigger_state(ticker: str = "") -> pd.DataFrame:
    init_monitoring_db()
    sql = "SELECT * FROM chapter1_trigger_state"
    params: tuple[Any, ...] = ()
    if ticker:
        sql += " WHERE ticker = ?"
        params = (str(ticker).upper().strip(),)
    sql += " ORDER BY checked_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return pd.DataFrame([dict(row) for row in rows])


def load_review_queue(open_only: bool = True) -> pd.DataFrame:
    init_monitoring_db()
    sql = """
        SELECT q.id, q.priority, q.ticker, c.company_name, c.gate,
               q.trigger_text, q.reason, q.observed_value, q.data_as_of,
               q.detected_at, q.status, q.resolved_at
        FROM chapter1_review_queue q
        LEFT JOIN chapter1_current c ON c.ticker = q.ticker
    """
    if open_only:
        sql += " WHERE q.status = 'open'"
    sql += " ORDER BY CASE q.priority WHEN 'Cao' THEN 1 WHEN 'Trung bình' THEN 2 ELSE 3 END, q.detected_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    data = []
    gate_labels = {"continue": "🟢 Continue", "watch": "🟡 Watch", "pause": "🟠 Pause", "reject": "🔴 Reject"}
    for row in rows:
        item = dict(row)
        data.append({
            "ID": item.get("id"),
            "Ưu tiên": item.get("priority"),
            "Mã": item.get("ticker"),
            "Doanh nghiệp": item.get("company_name") or "—",
            "Gate": gate_labels.get(item.get("gate"), item.get("gate") or "—"),
            "Trigger": item.get("trigger_text"),
            "Lý do review": item.get("reason"),
            "Giá trị": item.get("observed_value") or "—",
            "Kỳ dữ liệu": item.get("data_as_of") or "—",
            "Phát hiện": item.get("detected_at"),
            "Trạng thái": item.get("status"),
        })
    return pd.DataFrame(data)


def resolve_review_item(item_id: int) -> None:
    init_monitoring_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE chapter1_review_queue SET status = 'resolved', resolved_at = ? WHERE id = ? AND status = 'open'",
            (_now(), int(item_id)),
        )


def _html_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<div style='padding:12px;border:1px solid #d7cfbe;border-radius:8px'>Không có item cần review.</div>"
    cols = list(df.columns)
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    body = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(str(row[c]))}</td>" for c in cols)
        body.append(f"<tr>{cells}</tr>")
    return f"""
    <div style='overflow-x:auto;width:100%'>
      <table style='width:100%;table-layout:fixed;border-collapse:collapse;font-size:.88rem'>
        <thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody>
      </table>
    </div>
    <style>
      table th, table td {{border:1px solid #d7cfbe;padding:8px;vertical-align:top;white-space:normal;overflow-wrap:anywhere}}
      table th {{background:#f3efe4;color:#0b2a25}}
    </style>
    """


def render_monitoring_panel(current_ticker: str, evaluation_results: list[dict[str, Any]] | None = None) -> None:
    st.subheader("Monitoring / Review Queue")
    st.caption(
        "Engine chỉ phát hiện điều kiện cần xem lại. Nó không tự đổi Research Gate, không tự đưa ra BUY/HOLD/SELL. "
        "Numeric trigger được kiểm tra bằng dữ liệu Trecapital; BCTC/event trigger dùng cơ chế baseline để chỉ cảnh báo khi có thay đổi mới."
    )
    if evaluation_results:
        triggered = [row for row in evaluation_results if row.get("triggered")]
        missing = [row for row in evaluation_results if row.get("status") in {"missing_data", "unsupported"}]
        c1, c2, c3 = st.columns(3)
        c1.metric("Trigger đang thỏa", len(triggered))
        c2.metric("Trigger đã kiểm tra", len(evaluation_results))
        c3.metric("Thiếu/chưa hỗ trợ", len(missing))
        with st.expander(f"Chi tiết kiểm tra — {current_ticker}", expanded=bool(triggered)):
            for row in evaluation_results:
                icon = "🔔" if row.get("triggered") else ("⚪" if row.get("status") == "armed" else "⚠️")
                st.markdown(f"{icon} **{row.get('trigger_text')}** — {row.get('evidence')}")

    queue = load_review_queue(open_only=True)
    display = queue.drop(columns=["ID", "Trạng thái"], errors="ignore")
    if hasattr(st, "html"):
        st.html(_html_table(display))
    else:
        st.markdown(_html_table(display), unsafe_allow_html=True)

    if not queue.empty:
        options = queue["ID"].astype(int).tolist()
        selected = st.selectbox(
            "Đánh dấu item đã review",
            options,
            format_func=lambda item_id: next(
                (f"#{item_id} | {row['Mã']} | {row['Trigger']}" for _, row in queue.iterrows() if int(row["ID"]) == int(item_id)),
                f"#{item_id}",
            ),
            key=f"dca_review_queue_select_{current_ticker}",
        )
        if st.button("✅ Đã review item này", key=f"dca_review_queue_resolve_{current_ticker}"):
            resolve_review_item(int(selected))
            st.success("Đã chuyển item sang resolved. Research Gate không thay đổi.")
            st.rerun()
