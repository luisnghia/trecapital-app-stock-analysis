from __future__ import annotations

"""Chapter 7 Phase 7B — Structured Management Data Bridge.

Boundary:
- Primary/official disclosure first.
- Raw -> Candidate -> Analyst-confirmed apply.
- Event/as-of data; no fabricated TTM.
- Registered insider shares != executed shares.
- Actual shares != options != RSU != ESOP.
- No automatic OO/LT/HH, Lion/Hyena, Management Quality, MOS or BUY/SELL signal.

The bridge is intentionally deterministic and structured. It can ingest CSV/JSON/HTML tables
from official URLs or local files, normalize them, retain provenance, detect conflicts/possible
identity matches, and stage candidate records for analyst review. General unstructured/PDF research
belongs to Phase 7C and is never silently guessed here.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha1
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Iterable
import json
import re
import sqlite3
import unicodedata

import httpx
import pandas as pd

from modules.deep_company_analysis.chapter7 import (
    APP_DIR,
    DB_PATH,
    CAREER_TIMELINE_COLUMNS,
    COMPENSATION_HISTORY_COLUMNS,
    EVENT_COLUMNS,
    INSIDER_TRANSACTION_COLUMNS,
    MANAGEMENT_PROFILE_COLUMNS,
    OWNERSHIP_HISTORY_COLUMNS,
)


BRIDGE_SCHEMA_VERSION = 1
BRIDGE_BOUNDARY = "No automatic OO/LT/HH, Lion/Hyena or Management Quality conclusion; no MOS/Research Gate/BUY/SELL; insider activity is not a buy/sell signal."
RECORD_TYPES = ("roster", "career", "compensation", "ownership", "insider", "event")
SOURCE_GRADES = ("A — Primary official", "B — Company official", "C — Secondary structured")
SOURCE_TYPES = (
    "Annual report",
    "Governance report",
    "Financial statement note",
    "AGM document",
    "Board resolution",
    "Exchange/regulator disclosure",
    "Insider disclosure",
    "Official IR page",
    "Company press release",
    "Structured secondary source",
    "Other",
)
ROLE_OPTIONS = (
    "Chairman", "Vice Chairman", "CEO", "COO", "CFO", "Chief Accountant",
    "Board Director", "Independent Director", "Deputy CEO", "Other Executive", "Other",
)
TRANSACTION_TYPES = (
    "Open market", "ESOP", "Option exercise", "Transfer", "Gift", "Inheritance",
    "Employee-plan transaction", "Related-party transfer", "Tax withholding", "Unknown",
)
EVENT_REVIEW_MAP: dict[str, str] = {
    "CEO appointed": "Q33,Q34,Q36",
    "CEO resigned": "Q33,Q34,Q36",
    "Chairman changed": "Q33,Q34,Q36",
    "CFO changed": "Q33,Q36",
    "COO changed": "Q33,Q36",
    "Board changed": "Q33,Q36",
    "Founder exits executive role": "Q33,Q36",
    "Major executive departure": "Q34,Q36",
    "Compensation plan changed": "Q37",
    "ESOP approved": "Q37",
    "Large insider transaction": "Q38",
    "Ownership structure changed": "Q37,Q38",
}

LOCAL_SOURCE_ROOT = APP_DIR / "data_cache" / "chapter7_sources"


@dataclass(frozen=True)
class SourceMeta:
    title: str
    source_type: str
    source_url_or_file: str
    source_grade: str = "A — Primary official"
    publication_date: str = ""
    effective_date: str = ""
    as_of_date: str = ""
    page_or_section: str = ""
    record_type: str = "roster"

    def normalized(self) -> "SourceMeta":
        record_type = self.record_type if self.record_type in RECORD_TYPES else "roster"
        grade = self.source_grade if self.source_grade in SOURCE_GRADES else SOURCE_GRADES[0]
        source_type = self.source_type if self.source_type in SOURCE_TYPES else "Other"
        return SourceMeta(
            title=str(self.title or "").strip(),
            source_type=source_type,
            source_url_or_file=str(self.source_url_or_file or "").strip(),
            source_grade=grade,
            publication_date=str(self.publication_date or "").strip(),
            effective_date=str(self.effective_date or "").strip(),
            as_of_date=str(self.as_of_date or "").strip(),
            page_or_section=str(self.page_or_section or "").strip(),
            record_type=record_type,
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_bridge_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chapter7_source_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT '',
                source_url_or_file TEXT NOT NULL DEFAULT '',
                source_grade TEXT NOT NULL DEFAULT '',
                publication_date TEXT NOT NULL DEFAULT '',
                effective_date TEXT NOT NULL DEFAULT '',
                as_of_date TEXT NOT NULL DEFAULT '',
                page_or_section TEXT NOT NULL DEFAULT '',
                record_type TEXT NOT NULL DEFAULT '',
                parser_status TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ch7_source_docs_ticker ON chapter7_source_documents(ticker);

            CREATE TABLE IF NOT EXISTS chapter7_raw_management_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                refresh_run_id INTEGER,
                source_document_id INTEGER,
                record_type TEXT NOT NULL,
                raw_json TEXT NOT NULL DEFAULT '{}',
                raw_fingerprint TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ch7_raw_ticker ON chapter7_raw_management_records(ticker);

            CREATE TABLE IF NOT EXISTS chapter7_candidate_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                refresh_run_id INTEGER,
                source_document_id INTEGER,
                record_type TEXT NOT NULL,
                record_key TEXT NOT NULL,
                manager_id TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                normalized_fingerprint TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Candidate',
                conflict_status TEXT NOT NULL DEFAULT '',
                identity_suggestions_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ch7_candidates_ticker ON chapter7_candidate_records(ticker);
            CREATE INDEX IF NOT EXISTS idx_ch7_candidates_key ON chapter7_candidate_records(ticker, record_type, record_key);

            CREATE TABLE IF NOT EXISTS chapter7_role_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                manager_id TEXT NOT NULL,
                raw_role TEXT NOT NULL DEFAULT '',
                normalized_role TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                effective_date TEXT NOT NULL DEFAULT '',
                source_document_id INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ch7_role_history_ticker ON chapter7_role_history(ticker);

            CREATE TABLE IF NOT EXISTS chapter7_data_conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                conflict_type TEXT NOT NULL,
                record_type TEXT NOT NULL DEFAULT '',
                record_key TEXT NOT NULL DEFAULT '',
                old_candidate_id INTEGER,
                new_candidate_id INTEGER,
                details TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Needs analyst review',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ch7_conflicts_ticker ON chapter7_data_conflicts(ticker);

            CREATE TABLE IF NOT EXISTS chapter7_data_refresh_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT '',
                source_count INTEGER NOT NULL DEFAULT 0,
                raw_count INTEGER NOT NULL DEFAULT 0,
                candidate_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                conflict_count INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                parser_version TEXT NOT NULL DEFAULT 'phase7b-v1',
                note TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_ch7_refresh_ticker ON chapter7_data_refresh_runs(ticker);

            CREATE TABLE IF NOT EXISTS chapter7_review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                candidate_id INTEGER,
                event_date TEXT NOT NULL DEFAULT '',
                event_type TEXT NOT NULL DEFAULT '',
                manager_id TEXT NOT NULL DEFAULT '',
                manager TEXT NOT NULL DEFAULT '',
                questions_to_review TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ch7_review_ticker ON chapter7_review_queue(ticker);
            """
        )


def normalize_person_name(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    text = text.replace("Đ", "D").replace("đ", "d")
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = re.sub(r"[^A-Za-z0-9 ]+", " ", folded).casefold()
    return " ".join(folded.split())


def stable_manager_id(ticker: str, name: Any) -> str:
    normalized = normalize_person_name(name)
    if not normalized:
        return ""
    digest = sha1(f"{_safe_ticker(ticker)}|{normalized}".encode("utf-8")).hexdigest()[:12]
    return f"mgr_{digest}"


def suggest_identity_matches(name: Any, existing_names: Iterable[Any], threshold: float = 0.84) -> list[dict[str, Any]]:
    target = normalize_person_name(name)
    if not target:
        return []
    out: list[dict[str, Any]] = []
    for existing in existing_names:
        other = normalize_person_name(existing)
        if not other or other == target:
            continue
        score = SequenceMatcher(None, target, other).ratio()
        if score >= threshold:
            out.append({"name": str(existing), "similarity": round(score, 3), "action": "Analyst review — do not auto-merge"})
    return sorted(out, key=lambda row: row["similarity"], reverse=True)


def normalize_role(raw_role: Any) -> str:
    raw = normalize_person_name(raw_role)
    if not raw:
        return "Other"
    # Specific titles must be tested before broader substrings (e.g. Phó TGĐ contains TGĐ).
    patterns = (
        (("pho chu tich", "vice chairman"), "Vice Chairman"),
        (("pho tong giam doc", "deputy ceo", "deputy general director"), "Deputy CEO"),
        (("thanh vien hdqt doc lap", "independent director"), "Independent Director"),
        (("giam doc tai chinh", "cfo", "chief financial"), "CFO"),
        (("giam doc van hanh", "coo", "chief operating"), "COO"),
        (("ke toan truong", "chief accountant"), "Chief Accountant"),
        (("chu tich hoi dong quan tri", "chu tich hdqt", "chairman"), "Chairman"),
        (("tong giam doc", "ceo", "chief executive"), "CEO"),
        (("thanh vien hoi dong quan tri", "thanh vien hdqt", "board director", "director"), "Board Director"),
    )
    for tokens, normalized in patterns:
        if any(token in raw for token in tokens):
            return normalized
    if any(token in raw for token in ("giam doc", "director", "executive")):
        return "Other Executive"
    return "Other"


def parse_date_with_precision(value: Any) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", "Unknown"
    if re.fullmatch(r"\d{4}", text):
        return text, "Year only"
    if re.fullmatch(r"\d{1,2}[/-]\d{4}", text):
        return text, "Month/Year"
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return text, "Unparsed"
    return parsed.strftime("%d/%m/%Y"), "Exact date"


def _first(row: dict[str, Any], aliases: Iterable[str], default: Any = "") -> Any:
    lookup = {normalize_person_name(k).replace(" ", ""): v for k, v in row.items()}
    for alias in aliases:
        key = normalize_person_name(alias).replace(" ", "")
        if key in lookup and lookup[key] not in (None, ""):
            return lookup[key]
    return default


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if pd.notna(out) else None
    except Exception:
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(round(number)) if number is not None else None


def _meta_dict(meta: SourceMeta) -> dict[str, Any]:
    m = meta.normalized()
    return {
        "source_title": m.title,
        "source_type": m.source_type,
        "source_url_or_file": m.source_url_or_file,
        "source_grade": m.source_grade,
        "publication_date": m.publication_date,
        "effective_date": m.effective_date,
        "as_of_date": m.as_of_date,
        "page_or_section": m.page_or_section,
        "record_type": m.record_type,
        "retrieved_at": _now(),
    }


def _source_label(meta: SourceMeta) -> str:
    m = meta.normalized()
    return m.title or m.source_url_or_file or m.source_type


def normalize_structured_row(ticker: str, record_type: str, row: dict[str, Any], meta: SourceMeta) -> dict[str, Any]:
    if record_type not in RECORD_TYPES:
        raise ValueError(f"Unsupported record_type: {record_type}")
    manager = _first(row, ("Manager", "Name", "Full Name", "Executive", "Insider", "Ho ten", "Họ tên", "Nguoi noi bo", "Người nội bộ"))
    manager_id = stable_manager_id(ticker, manager)
    source = _source_label(meta)
    provenance = _meta_dict(meta)

    if record_type == "roster":
        raw_role = _first(row, ("Current Role", "Role", "Title", "Chuc vu", "Chức vụ"))
        joined, _ = parse_date_with_precision(_first(row, ("Joined Company", "Joined", "Ngay gia nhap", "Ngày gia nhập")))
        role_start, _ = parse_date_with_precision(_first(row, ("Started Current Role", "Role Start Date", "Ngay bo nhiem", "Ngày bổ nhiệm", "Effective Date"), meta.effective_date))
        payload = {
            "Manager ID": manager_id,
            "Manager": str(manager or ""),
            "Current Role": normalize_role(raw_role),
            "Founder?": str(_first(row, ("Founder?", "Founder"), "Unknown")),
            "Family-controlled relationship": str(_first(row, ("Family-controlled relationship", "Family relation", "Quan he gia dinh", "Quan hệ gia đình"), "Unknown")),
            "Joined Company": joined,
            "Started Current Role": role_start,
            "Prior Company": str(_first(row, ("Prior Company", "Previous Company", "Cong ty truoc", "Công ty trước"))),
            "Prior Industry": str(_first(row, ("Prior Industry", "Previous Industry", "Nganh truoc", "Ngành trước"))),
            "Same Industry": str(_first(row, ("Same Industry",), "Unknown")),
            "Same Customer Base": str(_first(row, ("Same Customer Base",), "Unknown")),
            "Prior Functional Background": str(_first(row, ("Prior Functional Background", "Functional Background"))),
            "Actual Ownership (%)": _float(_first(row, ("Actual Ownership (%)", "Ownership (%)", "Ownership %", "Ty le so huu", "Tỷ lệ sở hữu"))),
            "Suggested Classification": "Unknown",
            "Analyst Classification": "Unknown",
            "Supporting Evidence": source,
            "Counter-Evidence": "",
            "Analyst Rationale": "",
            "Confidence": "Unknown",
            "_raw_role": str(raw_role or ""),
            "_provenance": provenance,
        }
        return payload

    if record_type == "career":
        start, start_precision = parse_date_with_precision(_first(row, ("From", "Start", "Start Date", "Tu", "Từ")))
        end, end_precision = parse_date_with_precision(_first(row, ("To", "End", "End Date", "Den", "Đến")))
        raw_role = _first(row, ("Role", "Title", "Chuc vu", "Chức vụ"))
        return {
            "Manager ID": manager_id,
            "Manager": str(manager or ""),
            "From": start,
            "To": end,
            "Company": str(_first(row, ("Company", "Cong ty", "Công ty"))),
            "Role": str(raw_role or ""),
            "Industry": str(_first(row, ("Industry", "Nganh", "Ngành"))),
            "Functional Area": str(_first(row, ("Functional Area", "Function", "Chuc nang", "Chức năng"))),
            "Customer-facing": str(_first(row, ("Customer-facing", "Customer Facing"), "Unknown")),
            "Operating Exposure": str(_first(row, ("Operating Exposure",), "")),
            "Employee Exposure": str(_first(row, ("Employee Exposure",), "")),
            "Corporate-suite Exposure": str(_first(row, ("Corporate-suite Exposure",), "")),
            "Promotion Type": str(_first(row, ("Promotion Type", "Internal / External"), "Unknown")),
            "Previous Company Culture": str(_first(row, ("Previous Company Culture",), "")),
            "Major Responsibility": str(_first(row, ("Major Responsibility", "Responsibility"), "")),
            "Observed Result": str(_first(row, ("Observed Result", "Result"), "")),
            "Source": source,
            "Career Gap?": "Unknown",
            "Gap Explanation": "Unknown",
            "Date Precision": f"From: {start_precision}; To: {end_precision}",
            "_normalized_role": normalize_role(raw_role),
            "_provenance": provenance,
        }

    if record_type == "compensation":
        scope = str(_first(row, ("Compensation Scope", "Scope", "Pham vi", "Phạm vi"), "Individual"))
        if not manager and "aggregate" in normalize_person_name(scope):
            manager = "Board aggregate"
            manager_id = ""
        return {
            "Year": str(_first(row, ("Year", "Fiscal Year", "Nam", "Năm"))),
            "Manager ID": manager_id,
            "Manager": str(manager or ""),
            "Role": str(_first(row, ("Role", "Title", "Chuc vu", "Chức vụ"))),
            "Compensation Scope": scope,
            "Salary (tỷ)": _float(_first(row, ("Salary (tỷ)", "Salary", "Luong", "Lương"))),
            "Cash Bonus (tỷ)": _float(_first(row, ("Cash Bonus (tỷ)", "Cash Bonus", "Bonus", "Thuong", "Thưởng"))),
            "Stock Awards (tỷ)": _float(_first(row, ("Stock Awards (tỷ)", "Stock Awards"))),
            "Options Granted": _int(_first(row, ("Options Granted", "Options"))),
            "RSU / Restricted Stock": _int(_first(row, ("RSU / Restricted Stock", "RSU", "Restricted Stock"))),
            "ESOP Benefit": _int(_first(row, ("ESOP Benefit", "ESOP"))),
            "Pension / Other (tỷ)": _float(_first(row, ("Pension / Other (tỷ)", "Other Benefits", "Other"))),
            "Severance (tỷ)": _float(_first(row, ("Severance (tỷ)", "Severance"))),
            "Total Compensation (tỷ)": _float(_first(row, ("Total Compensation (tỷ)", "Total Compensation", "Tong thu lao", "Tổng thù lao"))),
            "Performance Metric": str(_first(row, ("Performance Metric", "Metric"))),
            "Measurement Horizon": str(_first(row, ("Measurement Horizon", "Horizon"))),
            "Target": str(_first(row, ("Target",))),
            "Actual": str(_first(row, ("Actual",))),
            "Target Met": str(_first(row, ("Target Met",), "Unknown")),
            "Payout Despite Missing Target": str(_first(row, ("Payout Despite Missing Target",), "Unknown")),
            "Guaranteed Component": str(_first(row, ("Guaranteed Component",), "Unknown")),
            "Compensation Consultant": str(_first(row, ("Compensation Consultant",), "Unknown")),
            "Source": source,
            "Data Quality Flags": _compensation_quality_flags(row, scope),
            "Analyst Note": "",
            "_provenance": provenance,
        }

    if record_type == "ownership":
        as_of, precision = parse_date_with_precision(_first(row, ("As-of Date", "As of Date", "Date", "Ngay", "Ngày"), meta.as_of_date or meta.effective_date))
        return {
            "As-of Date": as_of,
            "Manager ID": manager_id,
            "Manager": str(manager or ""),
            "Actual Shares": _int(_first(row, ("Actual Shares", "Shares", "So co phieu", "Số cổ phiếu"))),
            "Ownership (%)": _float(_first(row, ("Ownership (%)", "Ownership %", "Ty le so huu", "Tỷ lệ sở hữu"))),
            "Options": _int(_first(row, ("Options",))),
            "RSU / Restricted": _int(_first(row, ("RSU / Restricted", "RSU", "Restricted"))),
            "Unvested Awards": _int(_first(row, ("Unvested Awards", "Unvested"))),
            "Ownership Origin": str(_first(row, ("Ownership Origin", "Origin", "Nguon hinh thanh", "Nguồn hình thành"), "Unknown")),
            "Shares Added": _int(_first(row, ("Shares Added",))),
            "Shares Reduced": _int(_first(row, ("Shares Reduced",))),
            "Ownership Requirement": str(_first(row, ("Ownership Requirement",), "")),
            "Requirement Met": str(_first(row, ("Requirement Met",), "Unknown")),
            "Source": source,
            "Analyst Note": "",
            "_date_precision": precision,
            "_provenance": provenance,
        }

    if record_type == "insider":
        dfrom, pfrom = parse_date_with_precision(_first(row, ("Transaction Date From", "From", "Start Date", "Ngay bat dau", "Ngày bắt đầu")))
        dto, pto = parse_date_with_precision(_first(row, ("Transaction Date To", "To", "End Date", "Ngay ket thuc", "Ngày kết thúc")))
        txdate, pdate = parse_date_with_precision(_first(row, ("Transaction Date", "Transaction Date From", "Date"), dfrom))
        disclosure, _ = parse_date_with_precision(_first(row, ("Disclosure Date", "Publication Date", "Ngay cong bo", "Ngày công bố"), meta.publication_date))
        registered = _int(_first(row, ("Registered Shares", "Registered", "Dang ky", "Đăng ký")))
        executed = _int(_first(row, ("Executed Shares", "Executed", "Thuc hien", "Thực hiện", "Shares")))
        direction = str(_first(row, ("Transaction", "Direction", "Buy/Sell", "Mua/Ban", "Mua/Bán"), "Other"))
        low = normalize_person_name(direction)
        if low in {"mua", "buy", "purchase"}:
            direction = "Buy"
        elif low in {"ban", "sell", "sale"}:
            direction = "Sell"
        else:
            direction = "Other"
        tx_type = _normalize_transaction_type(_first(row, ("Transaction Type", "Type", "Hinh thuc", "Hình thức"), "Unknown"))
        before = _int(_first(row, ("Ownership Before", "Shares Before", "So huu truoc", "Sở hữu trước")))
        after = _int(_first(row, ("Ownership After", "Shares After", "So huu sau", "Sở hữu sau")))
        pct_existing = (executed / before * 100.0) if executed is not None and before not in (None, 0) else None
        value_bil = _float(_first(row, ("Transaction Value (tỷ)", "Transaction Value")))
        price = _float(_first(row, ("Price", "Gia", "Giá")))
        if value_bil is None and executed is not None and price is not None:
            value_bil = executed * price / 1_000_000_000.0
        return {
            "Transaction Date": txdate,
            "Transaction Date From": dfrom,
            "Transaction Date To": dto,
            "Disclosure Date": disclosure,
            "Manager ID": manager_id,
            "Insider": str(manager or ""),
            "Role": str(_first(row, ("Role", "Title", "Chuc vu", "Chức vụ"))),
            "Transaction": direction,
            "Transaction Type": tx_type,
            "Registered Shares": registered,
            "Executed Shares": executed,
            "Shares": executed,
            "Price": price,
            "Transaction Value (tỷ)": value_bil,
            "Ownership Before": before,
            "Ownership After": after,
            "Change in Ownership (%)": ((after - before) / before * 100.0) if before not in (None, 0) and after is not None else None,
            "% of Existing Ownership": pct_existing,
            "Funding Source": str(_first(row, ("Funding Source",), "Unknown")),
            "Stated Reason": str(_first(row, ("Stated Reason", "Reason", "Ly do", "Lý do"))),
            "Discretionary Transaction": str(_first(row, ("Discretionary Transaction",), "Unknown")),
            "Source": source,
            "Analyst Materiality": "Unknown",
            "Analyst Interpretation": "",
            "_date_precision": f"Transaction: {pdate}; From: {pfrom}; To: {pto}",
            "_provenance": provenance,
        }

    # event
    effective, precision = parse_date_with_precision(_first(row, ("Effective Date", "Event Date", "Date", "Ngay hieu luc", "Ngày hiệu lực"), meta.effective_date))
    publication, _ = parse_date_with_precision(_first(row, ("Publication Date", "Disclosure Date", "Ngay cong bo", "Ngày công bố"), meta.publication_date))
    as_of, _ = parse_date_with_precision(_first(row, ("As-of Date", "As of Date"), meta.as_of_date))
    event_type = str(_first(row, ("Event Type", "Type", "Su kien", "Sự kiện"), "Other"))
    return {
        "Event Date": effective,
        "Publication Date": publication,
        "Effective Date": effective,
        "As-of Date": as_of,
        "Manager ID": manager_id,
        "Manager": str(manager or ""),
        "Event Type": event_type,
        "Event": str(_first(row, ("Event", "Description", "Noi dung", "Nội dung"))),
        "Questions to Review": EVENT_REVIEW_MAP.get(event_type, str(_first(row, ("Questions to Review",), ""))),
        "Source": source,
        "Review Status": "Open",
        "Analyst Note": "",
        "_date_precision": precision,
        "_provenance": provenance,
    }


def _compensation_quality_flags(row: dict[str, Any], scope: str) -> str:
    flags: list[str] = []
    scope_norm = normalize_person_name(scope)
    if "aggregate" in scope_norm or "tong" in scope_norm:
        flags.append("aggregate_only")
    if not _first(row, ("Manager", "Name", "Full Name", "Executive", "Ho ten", "Họ tên")):
        flags.append("individual_amount_missing")
    if not any(_first(row, aliases) not in (None, "") for aliases in (("Stock Awards",), ("Options",), ("RSU",), ("ESOP",))):
        flags.append("equity_component_unknown")
    if not _first(row, ("Measurement Horizon", "Horizon", "Vesting Period")):
        flags.append("vesting_terms_missing")
    if not _first(row, ("Performance Metric", "Metric")):
        flags.append("metric_not_disclosed")
    return ", ".join(flags)


def _normalize_transaction_type(value: Any) -> str:
    low = normalize_person_name(value)
    mapping = (
        (("open market", "khop lenh", "thoa thuan", "market"), "Open market"),
        (("esop",), "ESOP"),
        (("option exercise", "exercise option"), "Option exercise"),
        (("tax withholding", "tax"), "Tax withholding"),
        (("gift", "tang cho", "cho tang"), "Gift"),
        (("inheritance", "thua ke"), "Inheritance"),
        (("related party", "nguoi lien quan"), "Related-party transfer"),
        (("employee plan", "employee"), "Employee-plan transaction"),
        (("transfer", "chuyen nhuong"), "Transfer"),
    )
    for tokens, out in mapping:
        if any(token in low for token in tokens):
            return out
    return "Unknown"


def _json_fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return sha1(raw.encode("utf-8")).hexdigest()


def _record_key(record_type: str, payload: dict[str, Any]) -> str:
    manager_id = str(payload.get("Manager ID") or "")
    if record_type == "roster":
        basis = (manager_id, payload.get("Current Role"), payload.get("Started Current Role"))
    elif record_type == "career":
        basis = (manager_id, payload.get("Company"), payload.get("Role"), payload.get("From"), payload.get("To"))
    elif record_type == "compensation":
        basis = (manager_id, payload.get("Manager"), payload.get("Year"), payload.get("Compensation Scope"))
    elif record_type == "ownership":
        basis = (manager_id, payload.get("As-of Date"))
    elif record_type == "insider":
        basis = (manager_id, payload.get("Transaction Date From") or payload.get("Transaction Date"), payload.get("Transaction"), payload.get("Registered Shares"), payload.get("Executed Shares"))
    else:
        basis = (manager_id, payload.get("Effective Date") or payload.get("Event Date"), payload.get("Event Type"), payload.get("Event"))
    return _json_fingerprint(basis)[:24]


def _register_source(conn: sqlite3.Connection, ticker: str, meta: SourceMeta, parser_status: str = "Registered") -> int:
    m = meta.normalized()
    now = _now()
    existing = conn.execute(
        "SELECT id FROM chapter7_source_documents WHERE ticker=? AND source_url_or_file=? AND record_type=? ORDER BY id DESC LIMIT 1",
        (_safe_ticker(ticker), m.source_url_or_file, m.record_type),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE chapter7_source_documents SET title=?,source_type=?,source_grade=?,publication_date=?,effective_date=?,as_of_date=?,page_or_section=?,parser_status=?,active=1,updated_at=? WHERE id=?",
            (m.title, m.source_type, m.source_grade, m.publication_date, m.effective_date, m.as_of_date, m.page_or_section, parser_status, now, existing["id"]),
        )
        return int(existing["id"])
    cur = conn.execute(
        "INSERT INTO chapter7_source_documents (ticker,title,source_type,source_url_or_file,source_grade,publication_date,effective_date,as_of_date,page_or_section,record_type,parser_status,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (_safe_ticker(ticker), m.title, m.source_type, m.source_url_or_file, m.source_grade, m.publication_date, m.effective_date, m.as_of_date, m.page_or_section, m.record_type, parser_status, 1, now, now),
    )
    return int(cur.lastrowid)


def register_source(ticker: str, meta: SourceMeta, parser_status: str = "Registered") -> int:
    init_bridge_db()
    with _connect() as conn:
        return _register_source(conn, ticker, meta, parser_status)


def list_sources(ticker: str) -> list[dict[str, Any]]:
    init_bridge_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id,title,source_type,source_url_or_file,source_grade,publication_date,effective_date,as_of_date,page_or_section,record_type,parser_status,active,updated_at FROM chapter7_source_documents WHERE ticker=? ORDER BY id DESC",
            (_safe_ticker(ticker),),
        ).fetchall()
    return [dict(row) for row in rows]


def _start_refresh(conn: sqlite3.Connection, ticker: str, note: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO chapter7_data_refresh_runs (ticker,started_at,note) VALUES (?,?,?)",
        (_safe_ticker(ticker), _now(), note),
    )
    return int(cur.lastrowid)


def _finish_refresh(conn: sqlite3.Connection, run_id: int, **stats: Any) -> None:
    conn.execute(
        "UPDATE chapter7_data_refresh_runs SET completed_at=?,source_count=?,raw_count=?,candidate_count=?,duplicate_count=?,conflict_count=?,error_count=?,note=? WHERE id=?",
        (
            _now(), int(stats.get("source_count", 0)), int(stats.get("raw_count", 0)), int(stats.get("candidate_count", 0)),
            int(stats.get("duplicate_count", 0)), int(stats.get("conflict_count", 0)), int(stats.get("error_count", 0)),
            str(stats.get("note", "")), run_id,
        ),
    )


def _existing_manager_names(ticker: str) -> list[str]:
    init_bridge_db()
    names: list[str] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT payload_json FROM chapter7_candidate_records WHERE ticker=? AND status IN ('Candidate','Applied') ORDER BY id DESC",
            (_safe_ticker(ticker),),
        ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except Exception:
            continue
        name = payload.get("Manager") or payload.get("Insider")
        if name and str(name) not in names:
            names.append(str(name))
    return names


def ingest_structured_rows(
    ticker: str,
    record_type: str,
    rows: Iterable[dict[str, Any]],
    meta: SourceMeta,
    *,
    note: str = "Structured source ingest",
) -> dict[str, Any]:
    init_bridge_db()
    safe = _safe_ticker(ticker)
    if not safe:
        raise ValueError("Ticker is required")
    if record_type not in RECORD_TYPES:
        raise ValueError(f"Unsupported record type: {record_type}")
    m = SourceMeta(**{**meta.__dict__, "record_type": record_type}).normalized()
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    existing_names = _existing_manager_names(safe)
    stats = {"source_count": 1, "raw_count": 0, "candidate_count": 0, "duplicate_count": 0, "conflict_count": 0, "error_count": 0, "note": note}
    candidate_ids: list[int] = []

    with _connect() as conn:
        run_id = _start_refresh(conn, safe, note)
        source_id = _register_source(conn, safe, m, "Parsed structured source")
        for raw in rows:
            try:
                raw_fp = _json_fingerprint(raw)
                conn.execute(
                    "INSERT INTO chapter7_raw_management_records (ticker,refresh_run_id,source_document_id,record_type,raw_json,raw_fingerprint,created_at) VALUES (?,?,?,?,?,?,?)",
                    (safe, run_id, source_id, record_type, json.dumps(raw, ensure_ascii=False, default=str), raw_fp, _now()),
                )
                stats["raw_count"] += 1
                payload = normalize_structured_row(safe, record_type, raw, m)
                key = _record_key(record_type, payload)
                fp_payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
                if isinstance(fp_payload.get('_provenance'), dict):
                    fp_payload['_provenance'].pop('retrieved_at', None)
                fp = _json_fingerprint(fp_payload)
                duplicate = conn.execute(
                    "SELECT id,normalized_fingerprint,payload_json FROM chapter7_candidate_records WHERE ticker=? AND record_type=? AND record_key=? ORDER BY id DESC LIMIT 1",
                    (safe, record_type, key),
                ).fetchone()
                if duplicate and duplicate["normalized_fingerprint"] == fp:
                    stats["duplicate_count"] += 1
                    continue
                suggestions = suggest_identity_matches(payload.get("Manager") or payload.get("Insider"), existing_names)
                conflict_status = ""
                old_id = None
                if duplicate and duplicate["normalized_fingerprint"] != fp:
                    conflict_status = "Needs analyst review"
                    old_id = int(duplicate["id"])
                now = _now()
                cur = conn.execute(
                    "INSERT INTO chapter7_candidate_records (ticker,refresh_run_id,source_document_id,record_type,record_key,manager_id,payload_json,normalized_fingerprint,status,conflict_status,identity_suggestions_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (safe, run_id, source_id, record_type, key, str(payload.get("Manager ID") or ""), json.dumps(payload, ensure_ascii=False, default=str), fp, "Candidate", conflict_status, json.dumps(suggestions, ensure_ascii=False), now, now),
                )
                candidate_id = int(cur.lastrowid)
                candidate_ids.append(candidate_id)
                stats["candidate_count"] += 1
                name = payload.get("Manager") or payload.get("Insider")
                if name and str(name) not in existing_names:
                    existing_names.append(str(name))
                if old_id is not None:
                    conn.execute(
                        "INSERT INTO chapter7_data_conflicts (ticker,conflict_type,record_type,record_key,old_candidate_id,new_candidate_id,details,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (safe, "Source conflict / changed normalized record", record_type, key, old_id, candidate_id, "Same canonical record key has different normalized values. Keep both until analyst review.", "Needs analyst review", now, now),
                    )
                    stats["conflict_count"] += 1
                if suggestions:
                    conn.execute(
                        "INSERT INTO chapter7_data_conflicts (ticker,conflict_type,record_type,record_key,old_candidate_id,new_candidate_id,details,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (safe, "Possible manager identity match", record_type, key, None, candidate_id, json.dumps(suggestions, ensure_ascii=False), "Needs analyst review", now, now),
                    )
                    stats["conflict_count"] += 1
                if record_type == "roster":
                    conn.execute(
                        "INSERT INTO chapter7_role_history (ticker,manager_id,raw_role,normalized_role,start_date,end_date,effective_date,source_document_id,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (safe, str(payload.get("Manager ID") or ""), str(payload.get("_raw_role") or ""), str(payload.get("Current Role") or ""), str(payload.get("Started Current Role") or ""), "", m.effective_date, source_id, now),
                    )
                if record_type == "event":
                    _create_review_item(conn, safe, candidate_id, payload)
            except Exception:
                stats["error_count"] += 1
        _finish_refresh(conn, run_id, **stats)
    return {"run_id": run_id, "candidate_ids": candidate_ids, **stats}


def _create_review_item(conn: sqlite3.Connection, ticker: str, candidate_id: int, payload: dict[str, Any]) -> None:
    event_type = str(payload.get("Event Type") or "")
    questions = str(payload.get("Questions to Review") or EVENT_REVIEW_MAP.get(event_type, ""))
    if not questions:
        return
    now = _now()
    conn.execute(
        "INSERT INTO chapter7_review_queue (ticker,candidate_id,event_date,event_type,manager_id,manager,questions_to_review,reason,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            ticker, candidate_id, str(payload.get("Effective Date") or payload.get("Event Date") or ""), event_type,
            str(payload.get("Manager ID") or ""), str(payload.get("Manager") or ""), questions,
            "New/changed management disclosure requires analyst review; prior conclusion is not auto-carried forward.", "Open", now, now,
        ),
    )


def parse_structured_bytes(data: bytes, filename: str, record_type: str) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(BytesIO(data))
        return frame.where(pd.notna(frame), None).to_dict("records")
    if suffix in {".json", ".jsonl"}:
        text = data.decode("utf-8-sig", errors="replace")
        if suffix == ".jsonl":
            values = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                values = parsed.get("records") or parsed.get("data") or parsed.get(record_type) or [parsed]
            else:
                values = parsed
        return [dict(item) for item in values if isinstance(item, dict)]
    if suffix in {".html", ".htm"}:
        return _parse_html_tables(data.decode("utf-8", errors="replace"), record_type)
    if suffix == ".pdf":
        raise ValueError("PDF is an unstructured source in Phase 7B. Keep it as source evidence for manual/Phase 7C extraction; no values are guessed.")
    raise ValueError(f"Unsupported structured file type: {suffix or 'unknown'}")


def _table_score(frame: pd.DataFrame, record_type: str) -> int:
    tokens: dict[str, tuple[str, ...]] = {
        "roster": ("name", "manager", "ho ten", "role", "chuc vu"),
        "career": ("company", "role", "from", "to", "career"),
        "compensation": ("salary", "bonus", "compensation", "thu lao", "luong"),
        "ownership": ("ownership", "shares", "so huu", "co phieu"),
        "insider": ("registered", "executed", "transaction", "giao dich", "dang ky"),
        "event": ("event", "effective", "appointment", "resign", "bo nhiem", "mien nhiem"),
    }
    joined = " ".join(normalize_person_name(c) for c in frame.columns)
    return sum(1 for token in tokens[record_type] if token in joined)


def _parse_html_tables(text: str, record_type: str) -> list[dict[str, Any]]:
    tables = pd.read_html(StringIO(text))
    if not tables:
        return []
    best = max(tables, key=lambda frame: (_table_score(frame, record_type), len(frame)))
    if _table_score(best, record_type) == 0:
        raise ValueError("No structured table matched the selected Chapter 7 record type; source retained without guessed mapping.")
    best.columns = [" ".join(str(x) for x in col if str(x) != "nan") if isinstance(col, tuple) else str(col) for col in best.columns]
    return best.where(pd.notna(best), None).to_dict("records")


def fetch_structured_source(meta: SourceMeta, timeout: float = 20.0) -> list[dict[str, Any]]:
    m = meta.normalized()
    url = m.source_url_or_file
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Structured URL must start with http:// or https://")
    if url.lower().split("?", 1)[0].endswith(".pdf"):
        raise ValueError("PDF is unstructured in Phase 7B; no PDF value extraction is performed here.")
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Trecapital-Research/1.0"}) as client:
        response = client.get(url)
        response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    raw = response.content
    if "json" in content_type or url.lower().split("?", 1)[0].endswith((".json", ".jsonl")):
        filename = "source.jsonl" if url.lower().split("?", 1)[0].endswith(".jsonl") else "source.json"
        return parse_structured_bytes(raw, filename, m.record_type)
    if "csv" in content_type or url.lower().split("?", 1)[0].endswith(".csv"):
        return parse_structured_bytes(raw, "source.csv", m.record_type)
    if "html" in content_type or b"<html" in raw[:5000].lower():
        return parse_structured_bytes(raw, "source.html", m.record_type)
    raise ValueError("Source is not structured JSON/CSV/HTML. Phase 7B retains it as provenance but does not guess values.")


def refresh_registered_sources(ticker: str) -> dict[str, Any]:
    init_bridge_db()
    safe = _safe_ticker(ticker)
    sources = [row for row in list_sources(safe) if int(row.get("active", 1)) == 1 and str(row.get("source_url_or_file") or "").lower().startswith(("http://", "https://"))]
    total = {"source_count": 0, "raw_count": 0, "candidate_count": 0, "duplicate_count": 0, "conflict_count": 0, "error_count": 0}
    messages: list[str] = []
    for source in sources:
        meta = SourceMeta(
            title=source.get("title", ""), source_type=source.get("source_type", "Other"), source_url_or_file=source.get("source_url_or_file", ""),
            source_grade=source.get("source_grade", SOURCE_GRADES[0]), publication_date=source.get("publication_date", ""), effective_date=source.get("effective_date", ""),
            as_of_date=source.get("as_of_date", ""), page_or_section=source.get("page_or_section", ""), record_type=source.get("record_type", "roster"),
        )
        try:
            rows = fetch_structured_source(meta)
            result = ingest_structured_rows(safe, meta.record_type, rows, meta, note="Refresh registered official structured source")
            for key in total:
                total[key] += int(result.get(key, 0))
        except Exception as exc:
            total["source_count"] += 1
            total["error_count"] += 1
            messages.append(f"{meta.title or meta.source_url_or_file}: {exc}")
            with _connect() as conn:
                _register_source(conn, safe, meta, f"Refresh error: {exc}")
    local = scan_local_sources(safe)
    for key in total:
        total[key] += int(local.get(key, 0))
    messages.extend(local.get("messages", []))
    total["messages"] = messages
    return total


def scan_local_sources(ticker: str) -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    root = LOCAL_SOURCE_ROOT / safe
    total = {"source_count": 0, "raw_count": 0, "candidate_count": 0, "duplicate_count": 0, "conflict_count": 0, "error_count": 0, "messages": []}
    if not root.exists():
        return total
    for path in sorted(root.glob("*")):
        if path.suffix.lower() not in {".csv", ".json", ".jsonl", ".html", ".htm"}:
            continue
        # Naming convention: roster__title.csv, career__title.json, ...
        record_type = path.name.split("__", 1)[0].casefold()
        if record_type not in RECORD_TYPES:
            total["messages"].append(f"Skipped {path.name}: prefix must be one of {', '.join(RECORD_TYPES)}")
            continue
        meta = SourceMeta(title=path.stem, source_type="Other", source_url_or_file=str(path), source_grade="A — Primary official", record_type=record_type)
        try:
            rows = parse_structured_bytes(path.read_bytes(), path.name, record_type)
            result = ingest_structured_rows(safe, record_type, rows, meta, note="Local official structured source scan")
            for key in ("source_count", "raw_count", "candidate_count", "duplicate_count", "conflict_count", "error_count"):
                total[key] += int(result.get(key, 0))
        except Exception as exc:
            total["error_count"] += 1
            total["messages"].append(f"{path.name}: {exc}")
    return total


def list_candidates(ticker: str, statuses: tuple[str, ...] = ("Candidate",)) -> list[dict[str, Any]]:
    init_bridge_db()
    safe = _safe_ticker(ticker)
    placeholders = ",".join("?" for _ in statuses)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT c.*, s.title AS source_title, s.source_grade, s.publication_date, s.effective_date, s.as_of_date FROM chapter7_candidate_records c LEFT JOIN chapter7_source_documents s ON s.id=c.source_document_id WHERE c.ticker=? AND c.status IN ({placeholders}) ORDER BY c.id DESC",
            (safe, *statuses),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            payload = json.loads(item.pop("payload_json") or "{}")
        except Exception:
            payload = {}
        try:
            identity = json.loads(item.pop("identity_suggestions_json") or "[]")
        except Exception:
            identity = []
        item["payload"] = payload
        item["identity_suggestions"] = identity
        out.append(item)
    return out


def candidate_review_frame(ticker: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in list_candidates(ticker, ("Candidate",)):
        payload = item["payload"]
        rows.append({
            "Apply?": False,
            "Candidate ID": int(item["id"]),
            "Record Type": item["record_type"],
            "Manager": payload.get("Manager") or payload.get("Insider") or "",
            "Role / Event": payload.get("Current Role") or payload.get("Role") or payload.get("Event Type") or "",
            "Effective / As-of": payload.get("Effective Date") or payload.get("As-of Date") or payload.get("Transaction Date") or payload.get("Started Current Role") or payload.get("Year") or "",
            "Source Grade": item.get("source_grade") or "",
            "Source Title": item.get("source_title") or "",
            "Conflict": item.get("conflict_status") or "",
            "Possible Identity Match": "; ".join(str(x.get("name")) for x in item.get("identity_suggestions", [])),
            "Status": item.get("status") or "",
        })
    return pd.DataFrame(rows)


def _clean_for_target(payload: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    return {col: payload.get(col) for col in columns if col in payload}


def apply_candidate_ids(ticker: str, payload: dict[str, Any], candidate_ids: Iterable[int]) -> tuple[dict[str, Any], dict[str, int]]:
    """Apply analyst-selected candidates to Phase 7A tables only; never change analyst conclusions/classifications."""
    init_bridge_db()
    safe = _safe_ticker(ticker)
    ids = [int(x) for x in candidate_ids]
    if not ids:
        return json.loads(json.dumps(payload, ensure_ascii=False, default=str)), {"applied": 0, "skipped": 0}
    protected_before = {
        "question_status": json.loads(json.dumps(payload.get("question_status", {}), ensure_ascii=False)),
        "q33": json.loads(json.dumps(payload.get("q33", {}), ensure_ascii=False)),
        "q34": json.loads(json.dumps(payload.get("q34", {}), ensure_ascii=False)),
        "q35": json.loads(json.dumps(payload.get("q35", {}), ensure_ascii=False)),
        "q36": json.loads(json.dumps(payload.get("q36", {}), ensure_ascii=False)),
        "q37": json.loads(json.dumps(payload.get("q37", {}), ensure_ascii=False)),
        "q38": json.loads(json.dumps(payload.get("q38", {}), ensure_ascii=False)),
        "final_management_classification": payload.get("final_management_classification"),
        "analyst_summary": payload.get("analyst_summary"),
    }
    result = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    target_map = {
        "roster": ("management_profiles", MANAGEMENT_PROFILE_COLUMNS),
        "career": ("career_timeline", CAREER_TIMELINE_COLUMNS),
        "compensation": ("compensation_history", COMPENSATION_HISTORY_COLUMNS),
        "ownership": ("ownership_history", OWNERSHIP_HISTORY_COLUMNS),
        "insider": ("insider_transactions", INSIDER_TRANSACTION_COLUMNS),
        "event": ("management_events", EVENT_COLUMNS),
    }
    applied = 0
    skipped = 0
    with _connect() as conn:
        for candidate_id in ids:
            row = conn.execute(
                "SELECT * FROM chapter7_candidate_records WHERE id=? AND ticker=? AND status='Candidate'",
                (candidate_id, safe),
            ).fetchone()
            if not row:
                skipped += 1
                continue
            record_type = row["record_type"]
            table_key, columns = target_map[record_type]
            candidate_payload = json.loads(row["payload_json"] or "{}")
            clean = _clean_for_target(candidate_payload, columns)
            target_rows = result.setdefault(table_key, [])
            if not isinstance(target_rows, list):
                target_rows = []
                result[table_key] = target_rows
            # Candidate record key dedupe against existing analyst workspace rows.
            clean_key = _record_key(record_type, candidate_payload)
            existing_keys = {_record_key(record_type, dict(existing)) for existing in target_rows if isinstance(existing, dict)}
            if clean_key not in existing_keys:
                target_rows.append(clean)
            conn.execute(
                "UPDATE chapter7_candidate_records SET status='Applied',updated_at=? WHERE id=?",
                (_now(), candidate_id),
            )
            applied += 1
    # Hard boundary check: structured data bridge may not overwrite analyst-owned conclusions.
    for key, value in protected_before.items():
        result[key] = value
    result["phase7b_last_apply_at"] = _now()
    return result, {"applied": applied, "skipped": skipped}


def list_conflicts(ticker: str, status: str | None = None) -> list[dict[str, Any]]:
    init_bridge_db()
    sql = "SELECT * FROM chapter7_data_conflicts WHERE ticker=?"
    params: list[Any] = [_safe_ticker(ticker)]
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def list_review_queue(ticker: str, status: str | None = "Open") -> list[dict[str, Any]]:
    init_bridge_db()
    sql = "SELECT * FROM chapter7_review_queue WHERE ticker=?"
    params: list[Any] = [_safe_ticker(ticker)]
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def resolve_review_item(review_id: int, status: str = "Reviewed") -> None:
    init_bridge_db()
    with _connect() as conn:
        conn.execute("UPDATE chapter7_review_queue SET status=?,updated_at=? WHERE id=?", (status, _now(), int(review_id)))


def latest_refresh_runs(ticker: str, limit: int = 20) -> list[dict[str, Any]]:
    init_bridge_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM chapter7_data_refresh_runs WHERE ticker=? ORDER BY id DESC LIMIT ?",
            (_safe_ticker(ticker), int(limit)),
        ).fetchall()
    return [dict(row) for row in rows]


def bridge_status_frame(ticker: str) -> pd.DataFrame:
    init_bridge_db()
    safe = _safe_ticker(ticker)
    candidates = list_candidates(safe, ("Candidate", "Applied"))
    conflicts = list_conflicts(safe, "Needs analyst review")
    conflict_by_type: dict[str, int] = {}
    for conflict in conflicts:
        conflict_by_type[conflict.get("record_type", "")] = conflict_by_type.get(conflict.get("record_type", ""), 0) + 1
    rows: list[dict[str, Any]] = []
    for record_type in RECORD_TYPES:
        subset = [item for item in candidates if item["record_type"] == record_type]
        latest_dates: list[pd.Timestamp] = []
        missing = 0
        for item in subset:
            payload = item["payload"]
            date_value = payload.get("As-of Date") or payload.get("Effective Date") or payload.get("Transaction Date") or payload.get("Started Current Role") or payload.get("Year")
            parsed = pd.to_datetime(date_value, errors="coerce", dayfirst=True)
            if pd.notna(parsed):
                latest_dates.append(parsed)
            required = _required_fields(record_type)
            if any(payload.get(field) in (None, "", "Unknown") for field in required):
                missing += 1
        latest = max(latest_dates).strftime("%d/%m/%Y") if latest_dates else "—"
        rows.append({
            "Data Area": record_type,
            "Latest As-of / Effective": latest,
            "Rows": len(subset),
            "Candidate": sum(1 for item in subset if item["status"] == "Candidate"),
            "Applied": sum(1 for item in subset if item["status"] == "Applied"),
            "Conflicts": conflict_by_type.get(record_type, 0),
            "Rows with Missing Required Fields": missing,
        })
    return pd.DataFrame(rows)


def _required_fields(record_type: str) -> tuple[str, ...]:
    return {
        "roster": ("Manager", "Current Role"),
        "career": ("Manager", "Company", "Role"),
        "compensation": ("Year", "Compensation Scope"),
        "ownership": ("Manager", "As-of Date", "Actual Shares"),
        "insider": ("Insider", "Transaction", "Executed Shares"),
        "event": ("Event Type", "Effective Date"),
    }[record_type]


def staleness_warnings(ticker: str, days: int = 365) -> list[str]:
    warnings: list[str] = []
    now = pd.Timestamp.now(tz=None)
    for source in list_sources(ticker):
        value = source.get("publication_date") or source.get("as_of_date") or source.get("effective_date")
        parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
        if pd.notna(parsed):
            age = (now.normalize() - parsed.normalize()).days
            if age > days:
                warnings.append(f"{source.get('record_type')}: source '{source.get('title') or source.get('source_url_or_file')}' is {age} days old.")
    return warnings


__all__ = [
    "BRIDGE_SCHEMA_VERSION", "RECORD_TYPES", "SOURCE_GRADES", "SOURCE_TYPES", "ROLE_OPTIONS", "TRANSACTION_TYPES",
    "EVENT_REVIEW_MAP", "SourceMeta", "init_bridge_db", "normalize_person_name", "stable_manager_id",
    "suggest_identity_matches", "normalize_role", "parse_date_with_precision", "normalize_structured_row",
    "register_source", "list_sources", "ingest_structured_rows", "parse_structured_bytes", "fetch_structured_source",
    "refresh_registered_sources", "scan_local_sources", "list_candidates", "candidate_review_frame", "apply_candidate_ids",
    "list_conflicts", "list_review_queue", "resolve_review_item", "latest_refresh_runs", "bridge_status_frame",
    "staleness_warnings",
]
