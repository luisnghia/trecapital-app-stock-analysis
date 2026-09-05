from __future__ import annotations

"""Chapter 6 Phase 6C — evidence/research assistant.

The agent only surfaces candidate evidence and research gaps. It never changes analyst-owned
Q27-Q32 assessments, Distribution Width, MOS, Research Gate, or BUY/HOLD/SELL.
Module-2 manipulation diagnostics are consumed through a read-only published snapshot; this
module does not import or recalculate Beneish/Jones/REM models.
"""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re

import pandas as pd

from adapters.module2_web_research import KNOWN_COMPANY_DOMAINS, WebEvidenceAgent


FOCUS_TERMS: dict[str, tuple[str, ...]] = {
    "Q27": (
        "revenue recognition", "ghi nhận doanh thu", "accounting policy", "chính sách kế toán",
        "capitalize", "capitalised", "vốn hóa", "depreciation", "khấu hao", "useful life",
        "provision", "dự phòng", "reserve", "restructuring", "tái cấu trúc", "impairment",
        "kiểm toán", "auditor", "inventory obsolescence", "bad debt", "phải thu khó đòi",
    ),
    "Q28": (
        "recurring revenue", "doanh thu định kỳ", "subscription", "thuê bao", "contracted revenue",
        "hợp đồng", "renewal", "gia hạn", "churn", "retention", "backlog", "repeat purchase",
    ),
    "Q29": (
        "cyclical", "chu kỳ", "recession", "suy thoái", "downturn", "suy giảm", "capacity",
        "công suất", "oversupply", "dư cung", "commodity", "hàng hóa", "deferrable", "nhu cầu",
    ),
    "Q30": (
        "operating leverage", "đòn bẩy hoạt động", "fixed cost", "chi phí cố định", "variable cost",
        "chi phí biến đổi", "capacity utilization", "công suất sử dụng", "lease", "thuê", "payroll",
    ),
    "Q31": (
        "working capital", "vốn lưu động", "receivable", "phải thu", "inventory", "tồn kho",
        "payable", "phải trả", "payment terms", "điều khoản thanh toán", "supplier advance",
        "customer advance", "cash conversion cycle", "ccc",
    ),
    "Q32": (
        "capital expenditure", "capex", "maintenance capex", "sustaining capex", "growth capex",
        "đầu tư duy trì", "đầu tư mở rộng", "depreciation", "khấu hao", "ppe", "fixed assets",
        "tài sản cố định", "replacement", "thay thế", "expansion project", "dự án mở rộng",
    ),
}

SUBTOPICS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "Q27": (
        ("Revenue recognition", ("revenue recognition", "ghi nhận doanh thu")),
        ("Expense / capitalization", ("capitalize", "capitalised", "vốn hóa")),
        ("Depreciation / estimates", ("depreciation", "khấu hao", "useful life")),
        ("Reserves / provisions", ("provision", "dự phòng", "reserve", "bad debt", "phải thu khó đòi")),
        ("Audit / accounting changes", ("auditor", "kiểm toán", "accounting policy", "chính sách kế toán", "impairment", "restructuring")),
    ),
    "Q28": (
        ("Contractual recurrence", ("contract", "hợp đồng", "contracted revenue")),
        ("Subscription / renewal", ("subscription", "thuê bao", "renewal", "gia hạn", "churn", "retention")),
        ("Backlog / repeat purchase", ("backlog", "repeat purchase", "recurring revenue", "doanh thu định kỳ")),
    ),
    "Q29": (
        ("Demand cycle", ("cyclical", "chu kỳ", "recession", "suy thoái", "downturn", "suy giảm")),
        ("Supply / capacity", ("capacity", "công suất", "oversupply", "dư cung")),
        ("Commodity exposure", ("commodity", "hàng hóa")),
    ),
    "Q30": (
        ("Fixed / variable cost", ("fixed cost", "chi phí cố định", "variable cost", "chi phí biến đổi")),
        ("Capacity utilization", ("capacity utilization", "công suất sử dụng")),
        ("Cost commitments", ("lease", "thuê", "payroll")),
    ),
    "Q31": (
        ("Receivables", ("receivable", "phải thu")),
        ("Inventory", ("inventory", "tồn kho")),
        ("Payables / terms", ("payable", "phải trả", "payment terms", "điều khoản thanh toán")),
        ("Advances / negative WC", ("supplier advance", "customer advance", "working capital", "vốn lưu động", "cash conversion cycle")),
    ),
    "Q32": (
        ("Maintenance vs growth capex", ("maintenance capex", "sustaining capex", "growth capex", "đầu tư duy trì", "đầu tư mở rộng")),
        ("Asset age / replacement", ("ppe", "fixed assets", "tài sản cố định", "replacement", "thay thế", "depreciation", "khấu hao")),
        ("Expansion / regulatory projects", ("expansion project", "dự án mở rộng", "capital expenditure", "capex")),
    ),
}

NEGATIVE_TERMS = (
    "qualified opinion", "adverse", "material weakness", "restatement", "bất thường", "ngoại trừ",
    "suy giảm", "downturn", "oversupply", "dư cung", "delay", "chậm", "write-off", "impairment",
    "tăng mạnh tồn kho", "tăng mạnh phải thu", "cắt giảm", "cut", "one-off", "không lặp lại",
)
POSITIVE_TERMS = (
    "recurring", "renewal", "retention", "stable", "ổn định", "contracted", "backlog",
    "cash generative", "conservative", "thận trọng", "recession resistant", "kháng suy thoái",
)


@dataclass
class Chapter6EvidenceResult:
    candidates: pd.DataFrame
    raw_tables: list[pd.DataFrame]
    raw_paths: list[str]
    note: str


class _FocusedAgent(WebEvidenceAgent):
    def __init__(self, raw_dir: str | Path, focus: str):
        super().__init__(raw_dir)
        self.focus = focus

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:
        clean = self._clean_company_name(company_name)
        name = clean or company_name or ticker
        terms = {
            "Q27": ["revenue recognition provision depreciation accounting policy auditor", "dự phòng khấu hao ghi nhận doanh thu kiểm toán"],
            "Q28": ["recurring revenue subscription renewal contracted revenue backlog", "doanh thu định kỳ hợp đồng gia hạn"],
            "Q29": ["cyclical recession downturn capacity oversupply commodity", "chu kỳ suy giảm công suất dư cung"],
            "Q30": ["operating leverage fixed cost variable cost capacity utilization", "đòn bẩy hoạt động chi phí cố định công suất"],
            "Q31": ["working capital receivables inventory payables payment terms", "vốn lưu động phải thu tồn kho phải trả"],
            "Q32": ["maintenance capex growth capex depreciation fixed assets replacement", "capex duy trì đầu tư mở rộng khấu hao tài sản cố định"],
        }[self.focus]
        return [f'"{ticker}" "{name}" {term}' for term in terms]


def _known_company_domains(ticker: str) -> set[str]:
    out: set[str] = set()
    for url in KNOWN_COMPANY_DOMAINS.get(str(ticker).upper().strip(), []):
        domain = WebEvidenceAgent._domain(url)
        if domain:
            out.add(domain)
    return out


def _source_quality(row: dict[str, Any], ticker: str) -> str:
    domain = str(row.get("Tên miền") or "").lower().replace("www.", "")
    group = str(row.get("Nhóm thông tin") or "")
    known = _known_company_domains(ticker)
    if any(domain == d or domain.endswith("." + d) for d in known):
        return "A — Company/Official disclosure"
    if "Nguồn công bố chính thức" in group or "Nguồn doanh nghiệp/IR" in group:
        return "A — Company/Official disclosure"
    if "Dữ liệu/tin tài chính" in group:
        return "B — Independent financial source/research"
    return "C — Secondary/context source"


def _subtopic(question: str, text: str) -> str:
    low = text.casefold()
    for label, terms in SUBTOPICS.get(question, ()):
        if any(term.casefold() in low for term in terms):
            return label
    return "General Chapter-6 evidence"


def _direction(text: str) -> str:
    low = text.casefold()
    neg = sum(1 for term in NEGATIVE_TERMS if term.casefold() in low)
    pos = sum(1 for term in POSITIVE_TERMS if term.casefold() in low)
    if neg > pos and neg > 0:
        return "Contradicting / widening candidate"
    if pos > neg and pos > 0:
        return "Supporting / narrowing candidate"
    return "Neutral / context"


def _period_candidate(text: str) -> str:
    years = re.findall(r"\b(20\d{2}|19\d{2})\b", text or "")
    return years[-1] if years else ""


def classify_evidence_rows(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Classify only returned title/snippet evidence text, never query text or direct-link prompts."""
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, item in raw.iterrows():
        row = item.to_dict()
        question = str(row.get("_Focus") or "")
        if question not in FOCUS_TERMS:
            continue
        status = str(row.get("Trạng thái") or "")
        if status not in {"Tìm thấy", "Evidence trích từ nguồn chính thức", "Evidence trích từ PDF chính thức"}:
            continue
        title = str(row.get("Tiêu đề") or "")
        snippet = str(row.get("Trích yếu") or "")
        text = f"{title} {snippet}".strip()
        if not text:
            continue
        low = text.casefold()
        if not any(term.casefold() in low for term in FOCUS_TERMS[question]):
            continue
        rows.append({
            "Question": question,
            "Subtopic": _subtopic(question, text),
            "Direction": _direction(text),
            "Evidence Quality": _source_quality(row, ticker),
            "Explicitness": "Explicit text candidate",
            "Period Candidate": _period_candidate(text),
            "Title": title[:240],
            "URL": str(row.get("Nguồn/URL") or ""),
            "Snippet": snippet[:900],
            "Source Group": str(row.get("Nhóm thông tin") or ""),
            "Source Method": "Phase 6C focused web evidence",
            "Data Origin": "External evidence candidate — analyst verification required",
            "Status": "Candidate — analyst verify",
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.drop_duplicates(subset=["Question", "URL", "Snippet"], keep="first").reset_index(drop=True)


class Chapter6EvidenceAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def search(self, ticker: str, company_name: str = "", max_results_per_query: int = 3) -> Chapter6EvidenceResult:
        raw_tables: list[pd.DataFrame] = []
        raw_paths: list[str] = []
        candidate_parts: list[pd.DataFrame] = []
        notes: list[str] = []
        for focus in ("Q27", "Q28", "Q29", "Q30", "Q31", "Q32"):
            agent = _FocusedAgent(self.raw_dir, focus)
            result = agent.search(ticker, company_name, max_results_per_query=max_results_per_query)
            raw = result.table.copy()
            raw["_Focus"] = focus
            raw_tables.append(raw)
            if result.raw_path:
                raw_paths.append(str(result.raw_path))
            notes.append(result.note)
            candidate = classify_evidence_rows(raw, ticker)
            if not candidate.empty:
                candidate_parts.append(candidate)
        candidates = pd.concat(candidate_parts, ignore_index=True) if candidate_parts else pd.DataFrame()
        if not candidates.empty:
            candidates = candidates.drop_duplicates(subset=["Question", "URL", "Snippet"], keep="first").reset_index(drop=True)
        return Chapter6EvidenceResult(candidates, raw_tables, raw_paths, " | ".join(notes))


def evidence_quality_summary(candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for question in ("Q27", "Q28", "Q29", "Q30", "Q31", "Q32"):
        sub = candidates[candidates["Question"].eq(question)] if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Question" in candidates.columns else pd.DataFrame()
        quality = sub.get("Evidence Quality", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        direction = sub.get("Direction", pd.Series(dtype="object")).astype(str) if not sub.empty else pd.Series(dtype="object")
        rows.append({
            "Question": question,
            "Candidates": int(len(sub)),
            "A — Official": int(quality.str.startswith("A —").sum()) if not quality.empty else 0,
            "B — Independent": int(quality.str.startswith("B —").sum()) if not quality.empty else 0,
            "C — Secondary": int(quality.str.startswith("C —").sum()) if not quality.empty else 0,
            "Counter / widening candidates": int(direction.str.startswith("Contradicting").sum()) if not direction.empty else 0,
            "Boundary": "Evidence coverage only — not a quality score",
        })
    return pd.DataFrame(rows)


def research_gaps(candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    task = {
        "Q27": "Verify accounting policies, estimates/reserves, auditor notes and revenue recognition in original filings.",
        "Q28": "Find first-party disclosure for recurring/contracted revenue, renewals, churn/retention or explicitly mark Unknown.",
        "Q29": "Find company-specific downturn and supply/demand evidence; do not infer cycle causality from history alone.",
        "Q30": "Find disclosed fixed/variable cost structure, utilization and adjustment lag evidence.",
        "Q31": "Reconcile working-capital movements with receivable/inventory/payable terms and business mechanism.",
        "Q32": "Find maintenance/growth/regulatory capex disclosure and asset replacement evidence; do not infer maintenance capex silently.",
    }
    for question in task:
        sub = candidates[candidates["Question"].eq(question)] if isinstance(candidates, pd.DataFrame) and not candidates.empty and "Question" in candidates.columns else pd.DataFrame()
        if sub.empty:
            rows.append({
                "Question": question,
                "Research Gap": "No usable external evidence candidate found in this run.",
                "Materiality": "Analyst decide",
                "Next Action": task[question],
                "Status": "Open — evidence gap",
                "Analyst Note": "",
            })
            continue
        has_a = sub["Evidence Quality"].astype(str).str.startswith("A —").any()
        if not has_a:
            rows.append({
                "Question": question,
                "Research Gap": "No A-quality company/official disclosure candidate yet.",
                "Materiality": "Analyst decide",
                "Next Action": task[question],
                "Status": "Open — source-quality gap",
                "Analyst Note": "",
            })
    return pd.DataFrame(rows)


def manipulation_snapshot_table(snapshot: dict[str, Any] | None) -> pd.DataFrame:
    if not isinstance(snapshot, dict):
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for layer in snapshot.get("layers") or []:
        if not isinstance(layer, dict):
            continue
        value = layer.get("latest_score")
        try:
            value_text = "—" if value is None or pd.isna(value) else f"{float(value):,.3f}"
        except Exception:
            value_text = str(value or "—")
        rows.append({
            "Kỳ": str(layer.get("latest_period") or "Latest annual"),
            "Lớp": str(layer.get("layer") or ""),
            "Giá trị mô hình": value_text,
            "Mức cảnh báo": str(layer.get("latest_risk") or "N/A"),
            "Ghi chú": str(layer.get("latest_note") or ""),
            "Data Origin": "Module 2 — read-only published diagnostic",
        })
    if rows:
        rows.append({
            "Kỳ": "TTM",
            "Lớp": "TTM applicability",
            "Giá trị mô hình": "—",
            "Mức cảnh báo": "N/A",
            "Ghi chú": "Beneish/Jones/REM are annual-statement diagnostics; Phase 6C does not fabricate a TTM model value. Latest valid annual result remains visible above.",
            "Data Origin": "Methodology guardrail",
        })
    return pd.DataFrame(rows)


def manipulation_snapshot_candidates(snapshot: dict[str, Any] | None) -> pd.DataFrame:
    if not isinstance(snapshot, dict):
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for layer in snapshot.get("layers") or []:
        if not isinstance(layer, dict):
            continue
        layer_name = str(layer.get("layer") or "")
        period = str(layer.get("latest_period") or "")
        score = layer.get("latest_score")
        risk = str(layer.get("latest_risk") or "N/A")
        note = str(layer.get("latest_note") or "")
        rows.append({
            "Question": "Q27",
            "Subtopic": "Read-only manipulation/accounting-quality diagnostic",
            "Direction": "Neutral / context",
            "Evidence Quality": "T — Trecapital Module 2 diagnostic",
            "Explicitness": "Computed by source Module 2; not recomputed by Chapter 6",
            "Period Candidate": period,
            "Title": f"Module 2 — {layer_name}",
            "URL": "",
            "Snippet": f"Latest score={score}; risk={risk}. {note}",
            "Source Group": "Trecapital internal analytical evidence",
            "Source Method": "Read-only Module 2 bridge",
            "Data Origin": "Module 2 Financial Manipulation 4-layer diagnostics",
            "Status": "Candidate — analyst verify",
        })
    return pd.DataFrame(rows)


def merge_candidates_into_record(record: dict[str, Any], candidates: pd.DataFrame, gaps: pd.DataFrame | None = None) -> dict[str, Any]:
    """Merge only Evidence Matrix / Research Gaps. Analyst assessments are immutable here."""
    out = deepcopy(record)
    existing = out.get("evidence_matrix") if isinstance(out.get("evidence_matrix"), list) else []
    seen = {
        (str(r.get("Question") or ""), str(r.get("Source URL / File") or ""), str(r.get("Evidence Text") or ""))
        for r in existing if isinstance(r, dict)
    }
    iterator = candidates.iterrows() if isinstance(candidates, pd.DataFrame) and not candidates.empty else []
    for _, row in iterator:
        item = row.to_dict()
        evidence = {
            "Question": str(item.get("Question") or ""),
            "Claim": str(item.get("Subtopic") or "Evidence candidate"),
            "Evidence Type": str(item.get("Evidence Quality") or "Candidate evidence"),
            "Source Title": str(item.get("Title") or ""),
            "Source URL / File": str(item.get("URL") or ""),
            "Source Date": "",
            "Period": str(item.get("Period Candidate") or ""),
            "Evidence Text": str(item.get("Snippet") or ""),
            "Direction": str(item.get("Direction") or "Neutral / context"),
            "Status": "Candidate — analyst verify",
            "Data Origin": str(item.get("Data Origin") or "Phase 6C Research Assistant"),
            "Analyst Note": "",
        }
        key = (evidence["Question"], evidence["Source URL / File"], evidence["Evidence Text"])
        if key not in seen:
            existing.append(evidence)
            seen.add(key)
    out["evidence_matrix"] = existing

    if isinstance(gaps, pd.DataFrame) and not gaps.empty:
        existing_gaps = out.get("research_gaps_table") if isinstance(out.get("research_gaps_table"), list) else []
        gap_seen = {(str(r.get("Question") or ""), str(r.get("Research Gap") or "")) for r in existing_gaps if isinstance(r, dict)}
        for _, row in gaps.iterrows():
            item = row.to_dict()
            key = (str(item.get("Question") or ""), str(item.get("Research Gap") or ""))
            if key not in gap_seen:
                existing_gaps.append(item)
                gap_seen.add(key)
        out["research_gaps_table"] = existing_gaps
    return out


__all__ = [
    "Chapter6EvidenceAgent", "Chapter6EvidenceResult", "classify_evidence_rows", "evidence_quality_summary",
    "manipulation_snapshot_candidates", "manipulation_snapshot_table", "merge_candidates_into_record", "research_gaps",
]
