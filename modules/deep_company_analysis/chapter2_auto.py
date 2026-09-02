from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional
import json
import math
import re
import unicodedata

import pandas as pd

from adapters.module2_web_research import WebEvidenceAgent


class Chapter2EvidenceAgent(WebEvidenceAgent):
    """Targeted evidence search for Shearn Chapter 2.

    Results are research-assistant candidates only. They are never treated as analyst conclusions.
    """

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:  # type: ignore[override]
        clean_name = self._clean_company_name(company_name)
        name = clean_name or company_name or ticker
        return [
            f'"{ticker}" "{name}" sản phẩm OR dịch vụ OR "mảng kinh doanh" OR phân phối OR nhà máy OR quy trình',
            f'"{ticker}" "{name}" doanh thu OR "cơ cấu doanh thu" OR sản lượng OR giá bán OR chi phí OR khách hàng',
            f'"{ticker}" "{name}" lịch sử OR thành lập OR mua lại OR sáp nhập OR mở rộng OR "công suất" OR dự án',
            f'"{ticker}" "{name}" xuất khẩu OR quốc tế OR "thị trường nước ngoài" OR overseas OR export OR geography',
            f'"{ticker}" "{name}" USD OR EUR OR CNY OR JPY OR tỷ giá OR ngoại tệ OR hedging OR phòng ngừa',
        ]


Q3_KEYWORDS = (
    "sản phẩm", "san pham", "dịch vụ", "dich vu", "mảng kinh doanh", "mang kinh doanh",
    "phân phối", "phan phoi", "nhà máy", "nha may", "sản xuất", "san xuat", "customer",
    "distribution", "manufacturing", "product", "service", "segment",
)
Q4_KEYWORDS = (
    "doanh thu", "revenue", "sản lượng", "san luong", "giá bán", "gia ban", "chi phí", "chi phi",
    "biên lợi nhuận", "bien loi nhuan", "gross margin", "operating margin", "customer", "khách hàng",
)
Q5_KEYWORDS = (
    "thành lập", "thanh lap", "lịch sử", "lich su", "mua lại", "mua lai", "sáp nhập", "sap nhap",
    "mở rộng", "mo rong", "công suất", "cong suat", "dự án", "du an", "acquisition", "merger",
    "capacity", "founded", "established", "history", "restructur",
)
Q6_KEYWORDS = (
    "xuất khẩu", "xuat khau", "quốc tế", "quoc te", "nước ngoài", "nuoc ngoai", "overseas", "export",
    "international", "foreign", "usd", "eur", "cny", "jpy", "tỷ giá", "ty gia", "hedg", "ngoại tệ", "ngoai te",
)

COUNTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "Hoa Kỳ": ("hoa kỳ", "hoa ky", "united states", "u.s.", "usa", "thị trường mỹ", "thi truong my", "tại mỹ", "tai my", "sang mỹ", "sang my"),
    "Trung Quốc": ("trung quốc", "trung quoc", "china", "chinese"),
    "Nhật Bản": ("nhật bản", "nhat ban", "japan", "japanese"),
    "Hàn Quốc": ("hàn quốc", "han quoc", "south korea", "korea"),
    "Ấn Độ": ("ấn độ", "an do", "india", "indian"),
    "Thái Lan": ("thái lan", "thai lan", "thailand"),
    "Indonesia": ("indonesia",),
    "Malaysia": ("malaysia",),
    "Singapore": ("singapore",),
    "Philippines": ("philippines", "philippine"),
    "Campuchia": ("campuchia", "cambodia"),
    "Lào": ("laos", "thị trường lào", "thi truong lao", "tại lào", "tai lao", "sang lào", "sang lao"),
    "Đài Loan": ("đài loan", "dai loan", "taiwan"),
    "Úc": ("australia", "australian", "thị trường úc", "thi truong uc", "tại úc", "tai uc", "sang úc", "sang uc"),
    "New Zealand": ("new zealand",),
    "Đức": ("germany", "german", "thị trường đức", "thi truong duc", "tại đức", "tai duc", "sang đức", "sang duc", "ở đức", "o duc"),
    "Pháp": ("pháp", "phap", "france", "french"),
    "Anh": ("vương quốc anh", "vuong quoc anh", "united kingdom", "u.k.", "uk market"),
    "EU / Châu Âu": ("châu âu", "chau au", "europe", "european union", " eu "),
    "ASEAN": ("asean", "đông nam á", "dong nam a", "southeast asia"),
    "Châu Á": ("châu á", "chau a", "asia", "asian market"),
}

CURRENCY_ALIASES: dict[str, tuple[str, ...]] = {
    "USD": ("usd", "đô la mỹ", "do la my", "us dollar"),
    "EUR": ("eur", "euro"),
    "CNY": ("cny", "nhân dân tệ", "nhan dan te", "rmb", "yuan"),
    "JPY": ("jpy", "yên nhật", "yen nhat", "japanese yen"),
    "KRW": ("krw", "won hàn", "won han", "korean won"),
    "VND": ("vnd", "đồng việt nam", "dong viet nam"),
}

EVENT_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("M&A", ("mua lại", "mua lai", "sáp nhập", "sap nhap", "acquisition", "merger", "m&a")),
    ("New Capacity", ("công suất", "cong suat", "nhà máy", "nha may", "capacity", "factory", "plant")),
    ("New Product", ("sản phẩm mới", "san pham moi", "new product", "ra mắt", "ra mat")),
    ("Geography", ("xuất khẩu", "xuat khau", "thị trường", "thi truong", "overseas", "export", "international")),
    ("Business-model Change", ("tái cấu trúc", "tai cau truc", "restructur", "business model", "chuyển đổi", "chuyen doi")),
    ("Founding", ("thành lập", "thanh lap", "founded", "established")),
    ("Regulatory Turning Point", ("giấy phép", "giay phep", "quy định", "quy dinh", "regulation", "license")),
)


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip()


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _preferred_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    rows: list[dict[str, Any]] = []
    if "period" in df.columns:
        ttm = df[df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]
        rows.extend(row.to_dict() for _, row in ttm.iloc[::-1].iterrows())
    work = df
    if "period_type" in work.columns:
        annual = work[work["period_type"].astype(str).eq("Y")]
        if not annual.empty:
            work = annual
    if "year" in work.columns:
        work = work.assign(_year=pd.to_numeric(work["year"], errors="coerce")).sort_values("_year")
    for _, row in work.iloc[::-1].iterrows():
        data = row.to_dict()
        if "TTM" in str(data.get("period") or "").upper() or "T12M" in str(data.get("period") or "").upper():
            continue
        rows.append(data)
    return rows


def _number(row: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _period(row: dict[str, Any]) -> str:
    return str(row.get("period") or row.get("year") or "kỳ gần nhất")


def _fmt(value: Optional[float], decimals: int = 0, suffix: str = "") -> str:
    return "—" if value is None else f"{value:,.{decimals}f}{suffix}"


def build_financial_economics(annual_df: pd.DataFrame) -> dict[str, Any]:
    rows = _preferred_rows(annual_df)
    if not rows:
        return {}
    row = rows[0]
    revenue = _number(row, "revenue_bil", "net_revenue_bil")
    gross_profit = _number(row, "gross_profit_bil")
    ebit = _number(row, "ebit_bil", "operating_profit_bil", "core_operating_profit_bil")
    cfo = _number(row, "cfo_bil", "operating_cash_flow_bil")
    capex = _number(row, "capex_bil")
    fcf = _number(row, "free_cash_flow_bil")
    if fcf is None and cfo is not None and capex is not None:
        fcf = cfo - abs(capex)
    net_profit = _number(row, "net_profit_bil", "net_income_bil")
    gross_margin = gross_profit / revenue * 100.0 if revenue and gross_profit is not None else None
    ebit_margin = ebit / revenue * 100.0 if revenue and ebit is not None else None
    fcf_margin = fcf / revenue * 100.0 if revenue and fcf is not None else None
    capex_ratio = abs(capex) / revenue * 100.0 if revenue and capex is not None else None

    previous = next((r for r in rows[1:] if _number(r, "revenue_bil", "net_revenue_bil") is not None), {})
    prev_revenue = _number(previous, "revenue_bil", "net_revenue_bil") if previous else None
    revenue_growth = (revenue / prev_revenue - 1.0) * 100.0 if revenue and prev_revenue and prev_revenue != 0 else None

    return {
        "period": _period(row),
        "revenue_bil": revenue,
        "revenue_growth_pct": revenue_growth,
        "gross_profit_bil": gross_profit,
        "gross_margin_pct": gross_margin,
        "ebit_bil": ebit,
        "ebit_margin_pct": ebit_margin,
        "net_profit_bil": net_profit,
        "cfo_bil": cfo,
        "capex_bil": capex,
        "capex_revenue_pct": capex_ratio,
        "fcf_bil": fcf,
        "fcf_margin_pct": fcf_margin,
    }


def build_money_summary(metrics: dict[str, Any]) -> str:
    if not metrics:
        return ""
    period = metrics.get("period") or "kỳ gần nhất"
    return (
        f"Research Assistant — financial economics context ({period}): "
        f"Doanh thu {_fmt(metrics.get('revenue_bil'), 0)} tỷ; tăng trưởng so kỳ annual gần trước {_fmt(metrics.get('revenue_growth_pct'), 1, '%')}; "
        f"gross margin {_fmt(metrics.get('gross_margin_pct'), 1, '%')}; EBIT {_fmt(metrics.get('ebit_bil'), 0)} tỷ "
        f"(EBIT margin {_fmt(metrics.get('ebit_margin_pct'), 1, '%')}); CFO {_fmt(metrics.get('cfo_bil'), 0)} tỷ; "
        f"Capex {_fmt(metrics.get('capex_bil'), 0)} tỷ ({_fmt(metrics.get('capex_revenue_pct'), 1, '%')} doanh thu); "
        f"FCF {_fmt(metrics.get('fcf_bil'), 0)} tỷ (FCF margin {_fmt(metrics.get('fcf_margin_pct'), 1, '%')}). "
        "Các số này chỉ mô tả economics tài chính; payer, volume driver, price driver và segment profit engine vẫn cần analyst xác minh từ business disclosure."
    )


def _iter_evidence_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if any(key in value for key in ("Tiêu đề", "Trích yếu", "Nguồn/URL")):
            yield value
        for child in value.values():
            yield from _iter_evidence_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_evidence_dicts(child)


def load_cached_evidence(raw_dir: str | Path, ticker: str, max_files: int = 4) -> pd.DataFrame:
    folder = Path(raw_dir) / "internet_evidence" / str(ticker or "").upper().strip()
    if not folder.exists():
        return pd.DataFrame()
    files = sorted(folder.glob("evidence_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:max_files]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in _iter_evidence_dicts(payload):
            title = str(item.get("Tiêu đề") or "").strip()
            url = str(item.get("Nguồn/URL") or "").strip()
            snippet = str(item.get("Trích yếu") or "").strip()
            if not title and not snippet:
                continue
            key = (title, url)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "Nhóm thông tin": item.get("Nhóm thông tin") or "Tin tham khảo",
                "Tiêu đề": title,
                "Nguồn/URL": url,
                "Tên miền": item.get("Tên miền") or "",
                "Trích yếu": snippet,
                "Gợi ý sử dụng": item.get("Gợi ý sử dụng") or "",
            })
    return pd.DataFrame(rows)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = _norm(text)
    return any(_norm(keyword) in normalized for keyword in keywords)


def classify_evidence(evidence_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sections = {key: [] for key in ("Q3", "Q4", "Q5", "Q6")}
    if not isinstance(evidence_df, pd.DataFrame) or evidence_df.empty:
        return {key: pd.DataFrame() for key in sections}
    for _, row in evidence_df.iterrows():
        data = row.to_dict()
        text = " ".join(str(data.get(k) or "") for k in ("Tiêu đề", "Trích yếu", "Nhóm thông tin"))
        if _contains_any(text, Q3_KEYWORDS):
            sections["Q3"].append(data)
        if _contains_any(text, Q4_KEYWORDS):
            sections["Q4"].append(data)
        if _contains_any(text, Q5_KEYWORDS):
            sections["Q5"].append(data)
        if _contains_any(text, Q6_KEYWORDS):
            sections["Q6"].append(data)
    return {key: pd.DataFrame(value).drop_duplicates(subset=["Tiêu đề", "Nguồn/URL"], keep="first") if value else pd.DataFrame() for key, value in sections.items()}


def _evidence_draft(df: pd.DataFrame, heading: str, max_items: int = 4) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    lines = [f"Research Assistant evidence draft — {heading}; analyst cần mở nguồn và viết lại bằng lời của mình:"]
    for _, row in df.head(max_items).iterrows():
        title = str(row.get("Tiêu đề") or "").strip()
        snippet = re.sub(r"\s+", " ", str(row.get("Trích yếu") or "")).strip()
        url = str(row.get("Nguồn/URL") or "").strip()
        body = snippet[:300] if snippet else title
        lines.append(f"- {title or 'Evidence'}: {body}" + (f" | Nguồn: {url}" if url else ""))
    return "\n".join(lines)


def _event_type(text: str) -> str:
    normalized = _norm(text)
    for label, keywords in EVENT_TYPES:
        if any(_norm(keyword) in normalized for keyword in keywords):
            return label
    return "Other"


def extract_timeline_candidates(q5_df: pd.DataFrame, max_rows: int = 12) -> list[dict[str, Any]]:
    if not isinstance(q5_df, pd.DataFrame) or q5_df.empty:
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _, row in q5_df.iterrows():
        title = str(row.get("Tiêu đề") or "").strip()
        snippet = str(row.get("Trích yếu") or "").strip()
        url = str(row.get("Nguồn/URL") or "").strip()
        text = f"{title} {snippet}"
        years = re.findall(r"\b(?:19|20)\d{2}\b", text)
        if not years:
            continue
        year = years[0]
        key = (year, title or snippet[:100])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "Year": year,
            "Event": title or re.sub(r"\s+", " ", snippet)[:180],
            "Type": _event_type(text),
            "Why it happened": "",
            "Impact": "",
            "Evidence": url or re.sub(r"\s+", " ", snippet)[:250],
        })
        if len(out) >= max_rows:
            break
    return out


def _alias_present(normalized_text: str, alias: str) -> bool:
    token = _norm(alias)
    if not token:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def _find_geographies(text: str) -> list[str]:
    normalized = _norm(text)
    found: list[str] = []
    for canonical, aliases in COUNTRY_ALIASES.items():
        if any(_alias_present(normalized, alias) for alias in aliases):
            found.append(canonical)
    return found


def _explicit_revenue_share(text: str) -> str:
    normalized = _norm(text)
    if not any(keyword in normalized for keyword in ("doanh thu", "revenue", "xuat khau", "export")):
        return ""
    patterns = (
        r"(?:doanh thu|revenue|xuat khau|export)[^%]{0,80}?(\d{1,3}(?:[.,]\d+)?)\s*%",
        r"(\d{1,3}(?:[.,]\d+)?)\s*%[^.]{0,80}?(?:doanh thu|revenue|xuat khau|export)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            try:
                value = float(match.group(1).replace(",", "."))
                if 0 <= value <= 100:
                    return f"{value:.1f}"
            except Exception:
                pass
    return ""


def _entry_year(text: str) -> str:
    normalized = _norm(text)
    patterns = (
        r"(?:bat dau tu(?: nam)?|tu nam|since|gia nhap|tham gia)[^0-9]{0,50}((?:19|20)\d{2})",
        r"((?:19|20)\d{2})[^.]{0,35}(?:bat dau|gia nhap|tham gia|entered|since)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(1)
    return ""


def extract_foreign_market_candidates(q6_df: pd.DataFrame, max_rows: int = 12) -> list[dict[str, Any]]:
    if not isinstance(q6_df, pd.DataFrame) or q6_df.empty:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, row in q6_df.iterrows():
        title = str(row.get("Tiêu đề") or "").strip()
        snippet = str(row.get("Trích yếu") or "").strip()
        url = str(row.get("Nguồn/URL") or "").strip()
        text = f"{title} {snippet}"
        geographies = _find_geographies(text)
        share = _explicit_revenue_share(text) if len(geographies) == 1 else ""
        entry_year = _entry_year(text) if len(geographies) == 1 else ""
        normalized = _norm(text)
        if any(token in normalized for token in ("xuat khau", "export")):
            exposure_type = "Thị trường xuất khẩu"
        elif any(token in normalized for token in ("cong ty con", "subsidiary", "nha may", "factory", "plant", "van phong", "office")):
            exposure_type = "Hiện diện/hoạt động trực tiếp"
        else:
            exposure_type = "Thị trường nước ngoài — cần xác minh loại exposure"
        for geography in geographies:
            if geography in seen:
                continue
            seen.add(geography)
            out.append({
                "Country / Region": geography,
                "Exposure type": exposure_type,
                "Entry year": entry_year,
                "Revenue share %": share,
                "Operating profit": "",
                "Assets": "",
                "Capex": "",
                "Localization / R&D": "",
                "Dedicated regional management": "",
                "Evidence": (url + (" | " if url and title else "") + title)[:600],
            })
            if len(out) >= max_rows:
                return out
    return out


def extract_currency_candidates(q6_df: pd.DataFrame) -> list[dict[str, str]]:
    if not isinstance(q6_df, pd.DataFrame) or q6_df.empty:
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, row in q6_df.iterrows():
        title = str(row.get("Tiêu đề") or "").strip()
        snippet = str(row.get("Trích yếu") or "").strip()
        url = str(row.get("Nguồn/URL") or "").strip()
        normalized = _norm(f"{title} {snippet}")
        for currency, aliases in CURRENCY_ALIASES.items():
            if any(_norm(alias) in normalized for alias in aliases):
                key = (currency, url or title)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"Currency": currency, "Evidence": (url + (" | " if url and title else "") + title)[:600]})
    return out


def _company_attr(company: Any, *names: str) -> str:
    for name in names:
        value = getattr(company, name, None) if company is not None else None
        if value not in (None, ""):
            return str(value)
    return ""


def build_chapter2_assistant_draft(
    company: Any,
    annual_df: pd.DataFrame,
    evidence_df: pd.DataFrame | None = None,
    *,
    source_label: str = "Trecapital canonical data",
) -> dict[str, Any]:
    evidence_df = evidence_df if isinstance(evidence_df, pd.DataFrame) else pd.DataFrame()
    sections = classify_evidence(evidence_df)
    metrics = build_financial_economics(annual_df)
    q3_evidence = sections.get("Q3", pd.DataFrame())
    q4_evidence = sections.get("Q4", pd.DataFrame())
    q5_evidence = sections.get("Q5", pd.DataFrame())
    q6_evidence = sections.get("Q6", pd.DataFrame())
    company_name = _company_attr(company, "company_name", "name", "company")
    industry = _company_attr(company, "industry", "industry_name", "sector", "sector_name")
    return {
        "provenance": {
            "source_label": source_label,
            "financial_period": metrics.get("period", ""),
            "evidence_count": int(len(evidence_df)),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "company_name": company_name,
            "industry": industry,
            "mode": "Research Assistant draft; analyst-controlled; no overwrite",
        },
        "q3": {
            "business_flow": _evidence_draft(q3_evidence, "Q3 Business Operations"),
            "evidence": q3_evidence.to_dict(orient="records") if not q3_evidence.empty else [],
        },
        "q4": {
            "money_summary": build_money_summary(metrics),
            "financial_metrics": metrics,
            "evidence": q4_evidence.to_dict(orient="records") if not q4_evidence.empty else [],
        },
        "q5": {
            "evolution": extract_timeline_candidates(q5_evidence),
            "evidence": q5_evidence.to_dict(orient="records") if not q5_evidence.empty else [],
        },
        "q6": {
            "foreign_markets": extract_foreign_market_candidates(q6_evidence),
            "foreign_strategy_summary": _evidence_draft(q6_evidence, "Q6 Foreign Markets / Commitment"),
            "currency_evidence": extract_currency_candidates(q6_evidence),
            "evidence": q6_evidence.to_dict(orient="records") if not q6_evidence.empty else [],
        },
    }


def merge_assistant_draft(record: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    """Fill only blank analyst-workspace fields; never overwrite analyst content.

    Deliberately NEVER fills Q3 `own_words`, Q5 `skill_vs_luck`, Q1 or Q2 because Shearn's
    learning/understanding tests require analyst judgement. The caller must explicitly choose to apply.
    """
    merged = deepcopy(record)
    merged.pop("_exists", None)
    for section in ("q3", "q4", "q5", "q6"):
        merged.setdefault(section, {})

    q3_draft = draft.get("q3", {}) if isinstance(draft, dict) else {}
    if not str(merged["q3"].get("business_flow", "") or "").strip():
        merged["q3"]["business_flow"] = str(q3_draft.get("business_flow", "") or "")

    q4_draft = draft.get("q4", {}) if isinstance(draft, dict) else {}
    if not str(merged["q4"].get("money_summary", "") or "").strip():
        merged["q4"]["money_summary"] = str(q4_draft.get("money_summary", "") or "")

    q5_draft = draft.get("q5", {}) if isinstance(draft, dict) else {}
    if not merged["q5"].get("evolution") and q5_draft.get("evolution"):
        merged["q5"]["evolution"] = deepcopy(q5_draft.get("evolution"))

    q6_draft = draft.get("q6", {}) if isinstance(draft, dict) else {}
    if not merged["q6"].get("foreign_markets") and q6_draft.get("foreign_markets"):
        merged["q6"]["foreign_markets"] = deepcopy(q6_draft.get("foreign_markets"))
    if not str(merged["q6"].get("foreign_strategy_summary", "") or "").strip():
        merged["q6"]["foreign_strategy_summary"] = str(q6_draft.get("foreign_strategy_summary", "") or "")

    merged["assistant_provenance"] = deepcopy(draft.get("provenance", {})) if isinstance(draft, dict) else {}
    merged["assistant_draft_applied_at"] = datetime.now().isoformat(timespec="seconds")
    return merged
