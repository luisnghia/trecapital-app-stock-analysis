from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter4_evidence_c3 import Phase4C3Result, SHEARN_Q19_SUBTOPICS
from modules.deep_company_analysis.chapter4_lock import build_lock_audit


def _q19(subtopic: str, i: int) -> dict:
    snippets = {
        "Limited / Direct Competition": "DGC đối thủ cạnh tranh trực tiếp và thị phần ngành hóa chất.",
        "How Competitors Compete": "DGC cạnh tranh bằng giá, chi phí, chất lượng và phân phối.",
        "Fierceness / Price Competition": "Ngành hóa chất có cạnh tranh giá và áp lực biên lợi nhuận.",
        "Substitute Products": "DGC đối mặt sản phẩm thay thế trong một số phân khúc.",
        "Low-cost Country Competition": "DGC chịu cạnh tranh nhập khẩu giá rẻ từ Trung Quốc.",
        "Industry Standard / Market Position": "DGC có vị thế thị phần và nhà sản xuất dẫn đầu.",
        "Industry Change / Capacity Competition": "Ngành hóa chất có mở rộng công suất và nhà máy mới.",
    }
    return {
        "Question": "Q19", "Subtopic": subtopic, "Direction": "Neutral — Candidate",
        "Evidence Quality": "B — Independent financial source", "Explicitness": "candidate — analyst verify",
        "Period Candidate": "2025", "Title": f"DGC competition {i}", "URL": f"https://research{i}.vn/q19",
        "Snippet": snippets[subtopic], "Source Group": "Independent", "Source Method": "test direct source",
    }


def test_nonconfirmed_q16_corroboration_becomes_visible_gap_not_false_positive():
    q19 = pd.DataFrame([_q19(label, i) for i, label in enumerate(SHEARN_Q19_SUBTOPICS[:-1])])
    pricing = pd.DataFrame([{
        "Question": "Q16", "Subtopic": "Actual Pricing / Customer Response", "Direction": "Neutral — Candidate",
        "Evidence Quality": "B — Independent financial source", "Explicitness": "Explicit price + customer/volume candidate",
        "Event Type Candidate": "Price + reaction with commodity/cost context — analyst verify", "Period Candidate": "2025",
        "Title": "DGC pricing", "URL": "https://research.vn/pricing",
        "Snippet": "DGC giá bán tăng trong khi sản lượng tăng nhưng bối cảnh giá hàng hóa cũng tăng.",
        "Source Group": "Independent", "Source Method": "test direct source",
    }])
    corroboration = pd.DataFrame([{
        "Period": "2025", "Explicit candidates": 1, "Distinct domains": 1, "Independent candidates": 1,
        "Commodity/pass-through candidates": 1,
        "Corroboration status": "Needs more independent corroboration — analyst verify",
    }])
    result = Phase4C3Result(
        pricing_candidates=pricing,
        pricing_corroboration=corroboration,
        q19_evidence=q19,
        q19_coverage=pd.DataFrame(),
        combined_candidates=pd.concat([pricing, q19], ignore_index=True, sort=False),
        gaps=[], note="test", audit={},
    )
    audit = build_lock_audit(result, "DGC", "Tập đoàn Hóa chất Đức Giang", "Hóa chất")
    q16_check = audit.checks[audit.checks["Check"].eq("Q16 corroboration is confirmed or explicit Research Gap")].iloc[0]
    assert bool(q16_check["Passed"]) is True
    assert "confirmed=False" in str(q16_check["Detail"])
    assert any(gap.startswith("Q16") for gap in audit.research_gaps)
    assert audit.lock_ready is True
