from __future__ import annotations

"""Phase 4C Research Assistant Evidence Bridge for Shearn Chapter 4.

The bridge searches and classifies *candidate evidence* for Q15-Q20.  It may populate the
Evidence Matrix with Candidate rows, but it never sets analyst assessment/trend/confidence or
BUY/HOLD/SELL. Supporting/counter-evidence direction is itself marked as candidate and requires
analyst verification.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re
import unicodedata

import pandas as pd

from adapters.module2_web_research import WebEvidenceAgent


FOCUSES = ("Q15_Q16", "Q17_Q18", "Q19", "Q20")


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip()


class _FocusedChapter4Agent(WebEvidenceAgent):
    def __init__(self, raw_dir: str | Path, focus: str, industry_name: str = ""):
        super().__init__(raw_dir)
        self.focus = focus
        self.industry_name = str(industry_name or "").strip()

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:  # type: ignore[override]
        name = self._clean_company_name(company_name) or company_name or ticker
        industry = self.industry_name or "ngành"
        if self.focus == "Q15_Q16":
            return [
                f'"{ticker}" "{name}" lợi thế cạnh tranh thương hiệu bằng sáng chế giấy phép switching cost quy mô nguồn nguyên liệu',
                f'"{ticker}" "{name}" tăng giá giá bán sản lượng khách hàng retention churn pricing power',
            ]
        if self.focus == "Q17_Q18":
            return [
                f'"{ticker}" "{industry}" ngành biên lợi nhuận ROIC chu kỳ rào cản công suất nhu cầu',
                f'"{industry}" lịch sử ngành công nghệ quy định hợp nhất công suất thay đổi cấu trúc',
            ]
        if self.focus == "Q19":
            return [
                f'"{ticker}" "{name}" đối thủ cạnh tranh thị phần price war substitute sản phẩm thay thế',
                f'"{ticker}" "{industry}" nhập khẩu đối thủ nước ngoài công suất cạnh tranh thất bại',
            ]
        return [
            f'"{ticker}" "{name}" nhà cung cấp nguyên liệu nguồn cung phụ thuộc supplier concentration',
            f'"{ticker}" "{name}" commodity giá nguyên liệu hedge hedging chuỗi cung ứng gián đoạn',
        ]


@dataclass
class Chapter4EvidenceResult:
    candidates: pd.DataFrame
    raw_tables: pd.DataFrame
    raw_paths: list[str]
    note: str


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _direction(text: str) -> str:
    counter = (
        "suy giam", "mat thi phan", "ap luc", "rui ro", "giam bien", "canh tranh tang", "gia giam",
        "khach hang roi", "churn tang", "thay the", "het han", "gia phep bi rut", "gian doan", "thieu hut",
        "phu thuoc", "price war", "erosion", "deteriorat", "declin", "lost share", "substitute", "disruption",
    )
    support = (
        "dan dau", "thi phan tang", "trung thanh", "premium", "gia tang", "retention cao", "doc quyen",
        "bang sang che", "giay phep", "chi phi thap", "quy mo", "loi the", "leader", "leading", "advantage",
        "strong retention", "exclusive", "cost advantage",
    )
    if _contains(text, counter):
        return "Contradicting — Candidate"
    if _contains(text, support):
        return "Supporting — Candidate"
    return "Neutral — Candidate"


def _source_quality(row: dict[str, Any]) -> str:
    group = str(row.get("Nhóm thông tin") or "")
    if "Nguồn công bố" in group or "Nguồn doanh nghiệp" in group or "BCTN" in group or "BCTC" in group:
        return "A — Company/Official disclosure"
    if "Dữ liệu/tin tài chính" in group:
        return "B — Independent financial source"
    return "C — Other candidate source"


def _q15_subtopic(text: str) -> str:
    if _contains(text, ("network effect", "network economics", "hieu ung mang", "he sinh thai", "platform")):
        return "Network Economics"
    if _contains(text, ("thuong hieu", "brand", "trung thanh", "loyalty")):
        return "Brand Loyalty"
    if _contains(text, ("bang sang che", "patent", "so huu tri tue", "intellectual property")):
        return "Patents"
    if _contains(text, ("giay phep", "license", "regulator", "quota", "permit", "quy dinh")):
        return "Regulatory Licenses"
    if _contains(text, ("switching cost", "chi phi chuyen doi", "migration", "retention", "churn")):
        return "Switching Costs"
    if _contains(text, ("quy mo", "scale", "chi phi thap", "cost advantage", "vi tri", "location", "mo apatit", "mo ", "nguon nguyen lieu", "unique asset", "vertical integration")):
        return "Cost Advantages — Scale / Location / Unique Asset"
    return "Competitive-advantage candidate"


def _candidate_rows(raw_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness",
        "Title", "URL", "Snippet", "Source Group", "Query", "Focus",
    ]
    if not isinstance(raw_df, pd.DataFrame) or raw_df.empty:
        return pd.DataFrame(columns=columns)
    out: list[dict[str, Any]] = []
    for _, row in raw_df.iterrows():
        data = row.to_dict()
        text = _norm(f"{data.get('Tiêu đề','')} {data.get('Trích yếu','')} {data.get('Truy vấn','')}")
        focus = str(data.get("_Focus") or "")
        base = {
            "Direction": _direction(text),
            "Evidence Quality": _source_quality(data),
            "Title": str(data.get("Tiêu đề") or ""),
            "URL": str(data.get("Nguồn/URL") or ""),
            "Snippet": str(data.get("Trích yếu") or ""),
            "Source Group": str(data.get("Nhóm thông tin") or ""),
            "Query": str(data.get("Truy vấn") or ""),
            "Focus": focus,
        }
        if focus == "Q15_Q16":
            moat_terms = ("loi the", "competitive", "moat", "thuong hieu", "brand", "patent", "giay phep", "switching", "quy mo", "scale", "nguon nguyen lieu", "location", "network")
            price_terms = ("tang gia", "gia ban", "pricing", "price increase", "premium price", "pass through", "pass-through")
            reaction_terms = ("san luong", "volume", "khach hang", "customer", "retention", "churn", "mat khach", "demand")
            if _contains(text, moat_terms) or not _contains(text, price_terms):
                out.append({**base, "Question": "Q15", "Subtopic": _q15_subtopic(text), "Explicitness": "Candidate — analyst verify mechanism/copyability"})
            if _contains(text, price_terms):
                explicit = "Explicit price + customer/volume candidate" if _contains(text, reaction_terms) else "Price mention only — insufficient for Pricing Power"
                out.append({**base, "Question": "Q16", "Subtopic": "Actual Pricing / Customer Response", "Explicitness": explicit})
        elif focus == "Q17_Q18":
            history_terms = ("lich su", "history", "thay doi", "chuyen dich", "consolidation", "hop nhat", "cong nghe", "technology", "regulation", "quy dinh", "cong suat", "capacity", "cau truc")
            industry_terms = ("nganh", "industry", "roic", "margin", "bien loi nhuan", "chu ky", "cyclical", "rao can", "barrier", "nhu cau", "demand")
            if _contains(text, industry_terms):
                out.append({**base, "Question": "Q17", "Subtopic": "Industry Economics", "Explicitness": "Industry-economics candidate"})
            if _contains(text, history_terms):
                out.append({**base, "Question": "Q18", "Subtopic": "Industry Evolution / Regime Change", "Explicitness": "Timeline/event candidate"})
            if not _contains(text, industry_terms + history_terms):
                out.append({**base, "Question": "Q17", "Subtopic": "Industry source to review", "Explicitness": "General industry candidate"})
        elif focus == "Q19":
            if _contains(text, ("thay the", "substitute")):
                subtopic = "Substitute Products"
            elif _contains(text, ("nhap khau", "nuoc ngoai", "foreign", "china", "trung quoc", "low cost")):
                subtopic = "Low-cost Country Competition"
            elif _contains(text, ("that bai", "pha san", "failure", "failed", "lo nang")):
                subtopic = "Why Competitors Failed"
            elif _contains(text, ("price war", "chien tranh gia", "gia re")):
                subtopic = "Fierceness / Price Competition"
            else:
                subtopic = "Competitive Landscape"
            out.append({**base, "Question": "Q19", "Subtopic": subtopic, "Explicitness": "Competitor/threat candidate"})
        elif focus == "Q20":
            if _contains(text, ("commodity", "gia nguyen lieu", "hedge", "hedging")):
                subtopic = "Commodity Resource Dependence"
            elif _contains(text, ("tap trung nha cung cap", "supplier concentration", "phu thuoc nha cung cap")):
                subtopic = "Supplier Concentration"
            elif _contains(text, ("gian doan", "supply disruption", "nguon cung", "supply chain")):
                subtopic = "Reliable Sources / Supply Chain"
            else:
                subtopic = "Supplier Relationship / Innovation"
            out.append({**base, "Question": "Q20", "Subtopic": subtopic, "Explicitness": "Supplier/commodity candidate"})
    result = pd.DataFrame(out, columns=columns)
    if result.empty:
        return result
    return result.drop_duplicates(subset=["Question", "Subtopic", "Title", "URL"], keep="first").reset_index(drop=True)


class Chapter4EvidenceAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)

    def search(self, ticker: str, company_name: str = "", industry_name: str = "", max_results_per_query: int = 4) -> Chapter4EvidenceResult:
        frames: list[pd.DataFrame] = []
        raw_paths: list[str] = []
        notes: list[str] = []
        for focus in FOCUSES:
            result = _FocusedChapter4Agent(self.raw_dir, focus, industry_name).search(
                ticker, company_name, max_results_per_query=max_results_per_query
            )
            frame = result.table.copy()
            frame["_Focus"] = focus
            frames.append(frame)
            if result.raw_path:
                raw_paths.append(str(result.raw_path))
            notes.append(result.note)
        raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not raw.empty:
            raw = raw.drop_duplicates(subset=[c for c in ["_Focus", "Tiêu đề", "Nguồn/URL"] if c in raw.columns], keep="first")
        candidates = _candidate_rows(raw)
        return Chapter4EvidenceResult(
            candidates=candidates,
            raw_tables=raw.reset_index(drop=True),
            raw_paths=raw_paths,
            note=f"Research Assistant đã phân loại {len(candidates)} evidence candidates cho Q15–Q20. Direction/explicitness vẫn cần analyst xác minh.",
        )


def merge_candidates_into_evidence_matrix(record: dict[str, Any], candidates: pd.DataFrame, max_rows: int = 120) -> dict[str, Any]:
    """Append Candidate evidence rows while preserving all analyst assessments and existing evidence."""
    if not isinstance(record, dict) or not isinstance(candidates, pd.DataFrame) or candidates.empty:
        return record
    existing = record.get("evidence_matrix")
    existing_rows = existing if isinstance(existing, list) else []
    rows = list(existing_rows)
    seen = {
        (str(r.get("Question") or ""), str(r.get("Source URL / File") or ""), str(r.get("Claim") or ""))
        for r in rows if isinstance(r, dict)
    }
    for _, item in candidates.head(max_rows).iterrows():
        claim = f"{item.get('Subtopic','')} — {item.get('Title','')}".strip(" —")
        key = (str(item.get("Question") or ""), str(item.get("URL") or ""), claim)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "Question": str(item.get("Question") or ""),
            "Claim": claim,
            "Evidence Type": str(item.get("Evidence Quality") or ""),
            "Source Title": str(item.get("Title") or ""),
            "Source URL / File": str(item.get("URL") or ""),
            "Source Date": "",
            "Period": "",
            "Evidence Text": str(item.get("Snippet") or ""),
            "Direction": str(item.get("Direction") or "Neutral — Candidate"),
            "Status": "Candidate — Analyst verify",
            "Data Origin": "Chapter 4 Research Assistant Evidence Bridge",
            "Analyst Note": f"{item.get('Explicitness','')} | Subtopic: {item.get('Subtopic','')}",
        })
    record["evidence_matrix"] = rows
    return record


def candidate_coverage(candidates: pd.DataFrame) -> dict[str, int]:
    if not isinstance(candidates, pd.DataFrame) or candidates.empty or "Question" not in candidates.columns:
        return {q: 0 for q in ("Q15", "Q16", "Q17", "Q18", "Q19", "Q20")}
    counts = candidates["Question"].value_counts().to_dict()
    return {q: int(counts.get(q, 0)) for q in ("Q15", "Q16", "Q17", "Q18", "Q19", "Q20")}


def guardrails() -> dict[str, bool]:
    return {
        "auto_moat_conclusion": False,
        "auto_pricing_power_conclusion": False,
        "auto_industry_quality_conclusion": False,
        "auto_competition_intensity_conclusion": False,
        "auto_supplier_quality_conclusion": False,
        "fabricate_interview": False,
        "fabricate_supplier_concentration": False,
        "infer_pricing_power_from_margin_only": False,
    }
