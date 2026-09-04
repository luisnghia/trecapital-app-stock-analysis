from __future__ import annotations

"""Phase 4C.2 deep evidence engines for Shearn Chapter 4 Q16 and Q19.

This module focuses on the two evidence gaps left by Phase 4C.1:
- Q16 Pricing Power: explicit price evidence paired with volume/customer/retention response;
- Q19 Competitor Intelligence: real same-industry peer context plus evidence on direct competition,
  competition mode/intensity, substitutes, low-cost foreign competition and competitor failures.

Everything produced here remains *candidate evidence*. It never changes analyst judgement, trend,
confidence, Research Gate, Ideal Company selection, or BUY/HOLD/SELL.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import re

import httpx
import pandas as pd

from adapters.module2_web_research import HEADERS, WebEvidenceAgent
from modules.deep_company_analysis.chapter2_evidence import (
    CHAPTER2_OFFICIAL_PAGES,
    CHAPTER2_OFFICIAL_PDFS,
    SourceFirstChapter2EvidenceAgent,
    _main_text_from_html,
)
from modules.deep_company_analysis.chapter4_evidence import (
    OFFICIAL_EVIDENCE_STATUS_PREFIX,
    _clean_lines,
    _context,
    _norm,
    _source_quality,
)


PRICE_TERMS = (
    "tăng giá", "giảm giá", "giá bán", "giá bán bình quân", "average selling price", "selling price",
    "asp", "price increase", "price decrease", "pricing", "premium price", "điều chỉnh giá",
)
REACTION_TERMS = (
    "sản lượng", "volume", "khách hàng", "customer", "retention", "churn", "mất khách", "demand",
    "nhu cầu", "đơn hàng", "order", "thị phần", "market share", "tiêu thụ", "consumption",
)
COST_MARKET_TERMS = (
    "nguyên liệu", "raw material", "commodity", "giá thị trường", "market price", "phosphorus", "phốt pho",
    "apatit", "apatite", "lưu huỳnh", "sulfur", "điện", "electricity", "pass-through", "pass through",
    "thiếu cung", "shortage", "cung cầu", "supply demand", "input cost", "chi phí đầu vào",
)

Q19_CLASSIFIERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Substitute Products", ("substitute", "sản phẩm thay thế", "thay thế", "replacement")),
    ("Low-cost Country Competition", ("trung quốc", "china", "foreign", "nước ngoài", "nhập khẩu", "import", "low cost", "giá rẻ")),
    ("Why Competitors Failed", ("thất bại", "phá sản", "bankrupt", "bankruptcy", "failed", "failure", "lỗ nặng", "rút lui", "exit market")),
    ("Fierceness / Price Competition", ("price war", "chiến tranh giá", "giảm giá", "discount", "cạnh tranh giá", "price competition")),
    ("Industry Standard / Market Position", ("dẫn đầu", "leader", "market leader", "thị phần", "market share", "chuẩn ngành", "industry standard")),
    ("Industry Change / Capacity Competition", ("công suất", "capacity", "new entrant", "đối thủ mới", "mở rộng nhà máy", "expansion", "new plant")),
    ("How Competitors Compete", ("dịch vụ", "service", "vốn", "capital", "copy", "sao chép", "distribution", "phân phối")),
    ("Limited / Direct Competition", ("đối thủ", "competitor", "competition", "cạnh tranh")),
)


@dataclass
class Phase4C2Result:
    pricing_candidates: pd.DataFrame
    competitor_universe: pd.DataFrame
    competitor_evidence: pd.DataFrame
    combined_candidates: pd.DataFrame
    note: str
    audit: dict[str, Any]


def _contains(text: str, terms: Iterable[str]) -> bool:
    normalized = _norm(text)
    return any(_norm(term) in normalized for term in terms)


def _year_from_text(text: str) -> str:
    years = re.findall(r"\b(?:19|20)\d{2}\b", str(text or ""))
    return years[0] if years else ""


def _search_rows(
    raw_dir: str | Path,
    queries: list[str],
    *,
    max_results_per_query: int = 3,
    source_method: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Execute all targeted queries rather than the generic two-query latency guardrail."""
    agent = WebEvidenceAgent(raw_dir)
    rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(3.0, connect=1.2), follow_redirects=True) as client:
        for query in list(dict.fromkeys(q for q in queries if str(q).strip())):
            found, payload = agent._search_duckduckgo(client, query, max_results_per_query)
            if not found:
                found, fallback = agent._search_bing(client, query, max_results_per_query)
                payload["fallback_bing"] = fallback
            for row in found:
                item = dict(row)
                item["_SourceMethod"] = source_method
                rows.append(item)
            audit.append(payload)
    if not rows:
        return pd.DataFrame(), audit
    frame = pd.DataFrame(rows)
    for col in ("Tiêu đề", "Nguồn/URL", "Trích yếu"):
        if col not in frame.columns:
            frame[col] = ""
    return frame.drop_duplicates(subset=["Nguồn/URL", "Trích yếu"], keep="first").reset_index(drop=True), audit


def _pricing_raw_from_text(
    *,
    ticker: str,
    page_title: str,
    url: str,
    text: str,
    source_method: str,
) -> list[dict[str, Any]]:
    lines = _clean_lines(text)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, line in enumerate(lines):
        if not _contains(line, PRICE_TERMS):
            continue
        snippet = _context(lines, idx, radius=2, limit=1200)
        key = _norm(snippet)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append({
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR | Q16",
            "Tiêu đề": f"{ticker} — {page_title} — Q16 pricing evidence {len(seen)}",
            "Nguồn/URL": url,
            "Tên miền": re.sub(r"^www\.", "", httpx.URL(url).host or "") if url else "",
            "Trích yếu": snippet,
            "Trạng thái": OFFICIAL_EVIDENCE_STATUS_PREFIX,
            "Gợi ý sử dụng": "Pricing evidence candidate; analyst phải xác minh price change, customer/volume response và nature của event.",
            "Truy vấn": "Official source direct extraction — Q16 deep",
            "Điểm phù hợp": 80 if "PDF" in source_method else 75,
            "_SourceMethod": source_method,
        })
        if len(seen) >= 16:
            break
    return rows


def _pricing_candidate_rows(raw: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness", "Event Type Candidate",
        "Period Candidate", "Title", "URL", "Snippet", "Source Group", "Source Method",
    ]
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame(columns=columns)
    out: list[dict[str, Any]] = []
    for _, row in raw.iterrows():
        data = row.to_dict()
        status = str(data.get("Trạng thái") or "")
        if status != "Tìm thấy" and not status.startswith(OFFICIAL_EVIDENCE_STATUS_PREFIX):
            continue
        # Classification deliberately excludes the query text so targeted search terms cannot create
        # a false positive when the returned title/snippet does not contain pricing evidence.
        evidence_text = f"{data.get('Tiêu đề','')} {data.get('Trích yếu','')}"
        if not _contains(evidence_text, PRICE_TERMS):
            continue
        has_reaction = _contains(evidence_text, REACTION_TERMS)
        has_cost_market = _contains(evidence_text, COST_MARKET_TERMS)
        if has_reaction:
            explicit = "Explicit price + customer/volume candidate"
        else:
            explicit = "Price mention only — insufficient for Pricing Power"
        if has_cost_market and not has_reaction:
            event_type = "Commodity / Cost-pass-through candidate — not Pricing Power conclusion"
        elif has_cost_market and has_reaction:
            event_type = "Price + reaction with commodity/cost context — analyst separate pass-through from Pricing Power"
        elif has_reaction:
            event_type = "Price + customer/volume response candidate — analyst verify"
        else:
            event_type = "Price-only candidate — insufficient"
        out.append({
            "Question": "Q16",
            "Subtopic": "Actual Pricing / Customer Response",
            "Direction": "Neutral — Candidate",
            "Evidence Quality": _source_quality(data),
            "Explicitness": explicit,
            "Event Type Candidate": event_type,
            "Period Candidate": _year_from_text(evidence_text),
            "Title": str(data.get("Tiêu đề") or ""),
            "URL": str(data.get("Nguồn/URL") or ""),
            "Snippet": str(data.get("Trích yếu") or ""),
            "Source Group": str(data.get("Nhóm thông tin") or ""),
            "Source Method": str(data.get("_SourceMethod") or "Targeted search snippet"),
        })
    result = pd.DataFrame(out, columns=columns)
    if result.empty:
        return result
    return result.drop_duplicates(subset=["URL", "Snippet"], keep="first").reset_index(drop=True)


class PricingPowerEvidenceEngine:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def search(self, ticker: str, company_name: str = "", industry_name: str = "") -> tuple[pd.DataFrame, dict[str, Any]]:
        safe = str(ticker or "").upper().strip()
        name = WebEvidenceAgent._clean_company_name(company_name) or company_name or safe
        industry = industry_name or "ngành"
        queries = [
            f'"{safe}" "{name}" "giá bán" sản lượng doanh thu khách hàng',
            f'"{safe}" "{name}" "average selling price" volume demand',
            f'"{safe}" "{name}" tăng giá sản lượng thị phần khách hàng',
            f'"{safe}" "{industry}" giá bán sản lượng cung cầu nguyên liệu',
        ]
        raw_frames: list[pd.DataFrame] = []
        search_df, search_audit = _search_rows(
            self.raw_dir, queries, max_results_per_query=3, source_method="Q16 targeted search snippet"
        )
        if not search_df.empty:
            raw_frames.append(search_df)

        official_audit: list[dict[str, Any]] = []
        pdf_helper = SourceFirstChapter2EvidenceAgent(self.raw_dir)
        with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(7.0, connect=1.8), follow_redirects=True) as client:
            for label, url in CHAPTER2_OFFICIAL_PAGES.get(safe, ()):
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    title, text = _main_text_from_html(response.text)
                    extracted = _pricing_raw_from_text(
                        ticker=safe,
                        page_title=label or title or "Official page",
                        url=url,
                        text=text,
                        source_method="Official HTML Q16 deep extraction",
                    )
                    if extracted:
                        raw_frames.append(pd.DataFrame(extracted))
                    official_audit.append({"url": url, "status": response.status_code, "rows": len(extracted)})
                except Exception as exc:
                    official_audit.append({"url": url, "error": str(exc)[:200], "rows": 0})
            for label, url in CHAPTER2_OFFICIAL_PDFS.get(safe, ()):
                text, status = pdf_helper._official_pdf_text(safe, label, url, client)
                extracted = _pricing_raw_from_text(
                    ticker=safe,
                    page_title=label,
                    url=url,
                    text=text,
                    source_method="Official annual-report PDF Q16 deep extraction",
                ) if text else []
                if extracted:
                    raw_frames.append(pd.DataFrame(extracted))
                official_audit.append({"url": url, "status": status, "rows": len(extracted)})

        raw = pd.concat(raw_frames, ignore_index=True) if raw_frames else pd.DataFrame()
        candidates = _pricing_candidate_rows(raw)
        return candidates, {"queries": queries, "search": search_audit, "official": official_audit}


def build_competitor_universe(peer_df: pd.DataFrame, target: str, max_peers: int = 12) -> pd.DataFrame:
    columns = [
        "Ticker", "Company Name", "Exchange", "Industry", "Sub-industry", "Peer Group", "Market Cap (tỷ)", "Status",
    ]
    if not isinstance(peer_df, pd.DataFrame) or peer_df.empty:
        return pd.DataFrame(columns=columns)
    target = str(target or "").upper().strip()
    frame = peer_df.copy()
    if "ticker" not in frame.columns:
        return pd.DataFrame(columns=columns)
    frame["ticker"] = frame["ticker"].fillna("").astype(str).str.upper().str.strip()
    frame = frame[frame["ticker"].ne(target) & frame["ticker"].ne("")].copy()
    if "market_cap_bil" in frame.columns:
        frame["market_cap_bil"] = pd.to_numeric(frame["market_cap_bil"], errors="coerce")
        frame = frame.sort_values(["market_cap_bil", "ticker"], ascending=[False, True], na_position="last")
    else:
        frame = frame.sort_values("ticker")
    frame = frame.drop_duplicates("ticker", keep="first").head(max(1, int(max_peers or 1)))
    rows: list[dict[str, Any]] = []
    for _, item in frame.iterrows():
        rows.append({
            "Ticker": item.get("ticker", ""),
            "Company Name": item.get("company_name", ""),
            "Exchange": item.get("exchange", ""),
            "Industry": item.get("industry", ""),
            "Sub-industry": item.get("sub_industry", ""),
            "Peer Group": item.get("peer_group", ""),
            "Market Cap (tỷ)": item.get("market_cap_bil"),
            "Status": "Same-industry candidate — analyst verify meaningful competitive overlap",
        })
    return pd.DataFrame(rows, columns=columns)


def _q19_subtopic(text: str) -> str:
    for label, terms in Q19_CLASSIFIERS:
        if _contains(text, terms):
            return label
    return ""


def _q19_candidate_rows(raw: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness", "Period Candidate",
        "Title", "URL", "Snippet", "Source Group", "Source Method",
    ]
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame(columns=columns)
    out: list[dict[str, Any]] = []
    for _, row in raw.iterrows():
        data = row.to_dict()
        status = str(data.get("Trạng thái") or "")
        if status != "Tìm thấy" and not status.startswith(OFFICIAL_EVIDENCE_STATUS_PREFIX):
            continue
        evidence_text = f"{data.get('Tiêu đề','')} {data.get('Trích yếu','')}"
        subtopic = _q19_subtopic(evidence_text)
        if not subtopic:
            continue
        normalized = _norm(evidence_text)
        counter = any(token in normalized for token in (
            "price war", "chien tranh gia", "mat thi phan", "lost share", "substitute", "thay the", "pha san",
            "bankrupt", "lo nang", "canh tranh tang", "import competition",
        ))
        direction = "Contradicting — Candidate" if counter else "Neutral — Candidate"
        out.append({
            "Question": "Q19",
            "Subtopic": subtopic,
            "Direction": direction,
            "Evidence Quality": _source_quality(data),
            "Explicitness": "Competitor-intelligence candidate — analyst verify relevance/root cause",
            "Period Candidate": _year_from_text(evidence_text),
            "Title": str(data.get("Tiêu đề") or ""),
            "URL": str(data.get("Nguồn/URL") or ""),
            "Snippet": str(data.get("Trích yếu") or ""),
            "Source Group": str(data.get("Nhóm thông tin") or ""),
            "Source Method": str(data.get("_SourceMethod") or "Q19 targeted search snippet"),
        })
    result = pd.DataFrame(out, columns=columns)
    if result.empty:
        return result
    return result.drop_duplicates(subset=["Subtopic", "URL", "Snippet"], keep="first").reset_index(drop=True)


class CompetitorIntelligenceEngine:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def search(
        self,
        ticker: str,
        company_name: str,
        industry_name: str,
        peer_df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        safe = str(ticker or "").upper().strip()
        name = WebEvidenceAgent._clean_company_name(company_name) or company_name or safe
        industry = industry_name or "ngành"
        universe = build_competitor_universe(peer_df, safe, max_peers=12)
        top = universe.head(5) if not universe.empty else pd.DataFrame()
        peer_tokens = " ".join(str(x) for x in top.get("Ticker", pd.Series(dtype=str)).tolist())
        queries = [
            f'"{safe}" "{name}" đối thủ cạnh tranh thị phần {peer_tokens}',
            f'"{safe}" "{industry}" cạnh tranh giá price war công suất thị phần',
            f'"{safe}" "{industry}" substitute thay thế nhập khẩu Trung Quốc China',
            f'"{industry}" đối thủ thất bại phá sản lỗ rút lui cạnh tranh',
        ]
        for peer in top.get("Ticker", pd.Series(dtype=str)).tolist()[:3]:
            queries.append(f'"{safe}" "{peer}" cạnh tranh thị phần công suất giá')
        raw, audit = _search_rows(
            self.raw_dir, queries, max_results_per_query=3, source_method="Q19 competitor targeted search snippet"
        )
        candidates = _q19_candidate_rows(raw)
        return universe, candidates, {"queries": queries, "search": audit}


class Phase4C2Engine:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)

    def search(
        self,
        ticker: str,
        company_name: str,
        industry_name: str,
        peer_df: pd.DataFrame,
    ) -> Phase4C2Result:
        pricing, pricing_audit = PricingPowerEvidenceEngine(self.raw_dir).search(ticker, company_name, industry_name)
        universe, q19, q19_audit = CompetitorIntelligenceEngine(self.raw_dir).search(
            ticker, company_name, industry_name, peer_df
        )
        combined = pd.concat([pricing, q19], ignore_index=True, sort=False) if (not pricing.empty or not q19.empty) else pd.DataFrame()
        explicit = int(pricing["Explicitness"].astype(str).str.startswith("Explicit price + customer/volume").sum()) if not pricing.empty else 0
        q19_subtopics = int(q19["Subtopic"].nunique()) if not q19.empty else 0
        note = (
            f"Phase 4C.2: Q16 {len(pricing)} candidate(s), explicit price+reaction={explicit}; "
            f"Q19 {len(q19)} evidence candidate(s) across {q19_subtopics} subtopic(s); "
            f"peer universe {len(universe)} candidate(s). Analyst vẫn là người kết luận."
        )
        return Phase4C2Result(
            pricing_candidates=pricing,
            competitor_universe=universe,
            competitor_evidence=q19,
            combined_candidates=combined,
            note=note,
            audit={"pricing": pricing_audit, "q19": q19_audit},
        )


def merge_c2_candidates_into_evidence_matrix(
    record: dict[str, Any], candidates: pd.DataFrame, max_rows: int = 120
) -> dict[str, Any]:
    """Append Phase 4C.2 candidates without modifying analyst conclusions or structured tables."""
    if not isinstance(record, dict) or not isinstance(candidates, pd.DataFrame) or candidates.empty:
        return record
    existing = record.get("evidence_matrix")
    rows = list(existing) if isinstance(existing, list) else []
    seen = {
        (str(r.get("Question") or ""), str(r.get("Source URL / File") or ""), str(r.get("Evidence Text") or ""))
        for r in rows if isinstance(r, dict)
    }
    for _, item in candidates.head(max_rows).iterrows():
        key = (str(item.get("Question") or ""), str(item.get("URL") or ""), str(item.get("Snippet") or ""))
        if key in seen:
            continue
        seen.add(key)
        extra = str(item.get("Event Type Candidate") or "")
        rows.append({
            "Question": str(item.get("Question") or ""),
            "Claim": f"{item.get('Subtopic','')} — {item.get('Title','')}".strip(" —"),
            "Evidence Type": str(item.get("Evidence Quality") or ""),
            "Source Title": str(item.get("Title") or ""),
            "Source URL / File": str(item.get("URL") or ""),
            "Source Date": "",
            "Period": str(item.get("Period Candidate") or ""),
            "Evidence Text": str(item.get("Snippet") or ""),
            "Direction": str(item.get("Direction") or "Neutral — Candidate"),
            "Status": "Candidate — Analyst verify",
            "Data Origin": "Chapter 4 Research Assistant Evidence Bridge Phase 4C.2",
            "Analyst Note": " | ".join(x for x in [str(item.get("Explicitness") or ""), extra, f"Source method: {item.get('Source Method','')}"] if x),
        })
    record["evidence_matrix"] = rows
    return record


def c2_quality_summary(result: Phase4C2Result) -> pd.DataFrame:
    pricing = result.pricing_candidates
    q19 = result.competitor_evidence
    explicit = int(pricing["Explicitness"].astype(str).str.startswith("Explicit price + customer/volume").sum()) if not pricing.empty else 0
    price_only = int(pricing["Explicitness"].astype(str).str.startswith("Price mention only").sum()) if not pricing.empty else 0
    commodity = int(pricing["Event Type Candidate"].astype(str).str.contains("Commodity|pass-through", case=False, regex=True).sum()) if not pricing.empty and "Event Type Candidate" in pricing.columns else 0
    source_a_q19 = int(q19["Evidence Quality"].astype(str).str.startswith("A —").sum()) if not q19.empty else 0
    source_b_q19 = int(q19["Evidence Quality"].astype(str).str.startswith("B —").sum()) if not q19.empty else 0
    return pd.DataFrame([
        {
            "Area": "Q16 Pricing Power evidence",
            "Candidates": len(pricing),
            "Strong/Explicit": explicit,
            "Price-only": price_only,
            "Commodity/Pass-through candidates": commodity,
            "Coverage": "Có explicit price + reaction" if explicit else "Gap — chưa có explicit price + reaction",
        },
        {
            "Area": "Q19 Competitor Intelligence",
            "Candidates": len(q19),
            "Strong/Explicit": int(q19["Subtopic"].nunique()) if not q19.empty else 0,
            "Price-only": "—",
            "Commodity/Pass-through candidates": "—",
            "Coverage": f"{int(q19['Subtopic'].nunique()) if not q19.empty else 0}/8 nhóm logic Q19 có evidence; A={source_a_q19}, B={source_b_q19}",
        },
    ])


def guardrails() -> dict[str, bool]:
    return {
        "auto_pricing_power_conclusion": False,
        "infer_pricing_power_from_margin_only": False,
        "infer_pricing_power_from_price_only": False,
        "treat_commodity_price_as_pricing_power": False,
        "auto_competition_intensity_conclusion": False,
        "auto_meaningful_competitor_confirmation": False,
        "auto_ideal_company_selection": False,
        "auto_competitor_failure_root_cause": False,
        "auto_research_gate_change": False,
    }
