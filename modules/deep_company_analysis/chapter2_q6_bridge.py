from __future__ import annotations

from typing import Any
import re

import pandas as pd

from modules.deep_company_analysis import chapter2_auto as base

_BASE_BUILD = base.build_chapter2_assistant_draft


def _alias_present(normalized_text: str, alias: str) -> bool:
    token = base._norm(alias)
    if not token:
        return False
    # Require lexical boundaries so aliases such as "an do" (Ấn Độ) do not match across
    # the boundary in "Thai Lan doanh thu".
    pattern = r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def find_geographies(text: str) -> list[str]:
    normalized = base._norm(text)
    found: list[str] = []
    for canonical, aliases in base.COUNTRY_ALIASES.items():
        if any(_alias_present(normalized, alias) for alias in aliases):
            found.append(canonical)
    return found


def entry_year(text: str) -> str:
    normalized = base._norm(text)
    patterns = (
        r"(?:bat dau tu(?: nam)?|tu nam|since|gia nhap|tham gia)[^0-9]{0,50}((?:19|20)\d{2})",
        r"((?:19|20)\d{2})[^.]{0,35}(?:bat dau|gia nhap|tham gia|entered|since)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(1)
    return ""


def explicit_revenue_share(text: str) -> str:
    normalized = base._norm(text)
    if not any(keyword in normalized for keyword in ("doanh thu", "revenue", "xuat khau", "export")):
        return ""
    patterns = (
        r"(?:doanh thu|revenue|xuat khau|export)[^%]{0,80}?(\d{1,3}(?:[.,]\d+)?)\s*%",
        r"(\d{1,3}(?:[.,]\d+)?)\s*%[^.]{0,80}?(?:doanh thu|revenue|xuat khau|export)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        try:
            value = float(match.group(1).replace(",", "."))
        except Exception:
            continue
        if 0 <= value <= 100:
            return f"{value:.1f}"
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
        geographies = find_geographies(text)
        share = explicit_revenue_share(text) if len(geographies) == 1 else ""
        year = entry_year(text) if len(geographies) == 1 else ""
        for geography in geographies:
            if geography in seen:
                continue
            seen.add(geography)
            out.append({
                "Country / Region": geography,
                "Entry year": year,
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


def build_chapter2_assistant_draft(
    company: Any,
    annual_df: pd.DataFrame,
    evidence_df: pd.DataFrame | None = None,
    *,
    source_label: str = "Trecapital canonical data",
) -> dict[str, Any]:
    draft = _BASE_BUILD(company, annual_df, evidence_df, source_label=source_label)
    evidence_df = evidence_df if isinstance(evidence_df, pd.DataFrame) else pd.DataFrame()
    sections = base.classify_evidence(evidence_df)
    q6_df = sections.get("Q6", pd.DataFrame())
    draft.setdefault("q6", {})["foreign_markets"] = extract_foreign_market_candidates(q6_df)
    return draft
