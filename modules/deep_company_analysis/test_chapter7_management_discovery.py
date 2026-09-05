from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter7_management_discovery import (
    MANAGER_CANDIDATE_COLUMNS,
    choose_research_targets,
    extract_management_candidates_from_documents,
)


def _docs():
    return [
        {
            "title": "DGC personnel disclosure 2025",
            "url": "https://example.com/2025-management.html",
            "text": (
                "Hội đồng quản trị: Ông Đào Hữu Huyền Chủ tịch HĐQT. "
                "Ngày 03/03/2025 bổ nhiệm Ông Lưu Bách Đạt Tổng Giám đốc. "
                "Ông Đào Hữu Duy Anh Phó Chủ tịch Hội đồng Quản trị. "
                "Ông Phạm Văn Hùng Phó Tổng Giám đốc. Bà Đào Thị Mai Kế toán trưởng."
            ),
        },
        {
            "title": "Annual Report 2024",
            "url": "https://example.com/2024-ar.pdf",
            "text": "Ông Đào Hữu Duy Anh Tổng Giám đốc. Số cổ phần nắm giữ 11.441.791, tỷ lệ 3,01%.",
        },
    ]


def test_discovers_manager_role_candidates_without_auto_confirmation():
    frame = extract_management_candidates_from_documents(_docs())
    assert list(frame.columns) == MANAGER_CANDIDATE_COLUMNS
    assert {"Đào Hữu Huyền", "Lưu Bách Đạt", "Đào Hữu Duy Anh", "Phạm Văn Hùng"}.issubset(set(frame["Manager"]))
    assert "Chairman" in set(frame["Role Normalized"])
    assert "CEO" in set(frame["Role Normalized"])
    assert set(frame["Status"]) == {"Discovered candidate — analyst verify"}
    assert not any("OO1" in str(x) or "Lion" in str(x) for x in frame.astype(str).to_numpy().ravel())


def test_research_targets_prioritize_recent_senior_roles_but_do_not_merge_history():
    frame = extract_management_candidates_from_documents(_docs())
    # Historical Duy Anh CEO episode and newer vice-chair episode may coexist; no silent overwrite/merge.
    duy = frame[frame["Manager"].eq("Đào Hữu Duy Anh")]
    assert len(duy) >= 2
    targets = choose_research_targets(frame, max_targets=5)
    assert "Đào Hữu Huyền" in targets
    assert "Lưu Bách Đạt" in targets
    assert len(targets) <= 5


def test_empty_documents_return_schema_not_inferred_people():
    frame = extract_management_candidates_from_documents([])
    assert isinstance(frame, pd.DataFrame)
    assert frame.empty
    assert list(frame.columns) == MANAGER_CANDIDATE_COLUMNS
