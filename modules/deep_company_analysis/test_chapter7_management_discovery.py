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



def test_action_words_are_not_captured_as_manager_name_v37_1_round3():
    docs = [{
        "title": "Official personnel disclosure 2025",
        "url": "https://example.com/official-personnel",
        "text": "Nghị quyết bổ nhiệm ông Lưu Bách Đạt giữ chức vụ Tổng Giám đốc. Nghị quyết bổ nhiệm ông Đào Hữu Duy Anh giữ chức vụ Phó Chủ tịch HĐQT.",
        "method": "HTML text extraction",
    }]
    frame = extract_management_candidates_from_documents(docs)
    names = set(frame["Manager"].astype(str))
    assert "Lưu Bách Đạt" in names
    assert "Đào Hữu Duy Anh" in names
    assert not any("giữ" in name.casefold() or "chức" in name.casefold() for name in names)


def test_official_roster_extracts_chairman_ceo_and_third_manager_v37_1_round3():
    docs = [{
        "title": "Official financial statement 2025",
        "url": "https://example.com/official-financial-statement.pdf",
        "text": "Ông Đào Hữu Huyền — Chủ tịch HĐQT\nÔng Lưu Bách Đạt — Tổng Giám đốc\nÔng Phạm Văn Hùng — Phó Tổng Giám đốc",
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    assert {"Đào Hữu Huyền", "Lưu Bách Đạt", "Phạm Văn Hùng"}.issubset(set(frame["Manager"].astype(str)))
    roles = set(frame["Role Normalized"].astype(str))
    assert "Chairman" in roles
    assert "CEO" in roles



def test_bare_official_table_rows_require_local_role_v37_1_round5():
    docs = [{
        "title": "Official Q4 financial statement 2025",
        "url": "https://example.com/q4-2025.pdf",
        "text": "Hội đồng Quản trị\nĐào Hữu Huyền    Chủ tịch HĐQT\nPhạm Văn Hùng    Phó Tổng Giám đốc\nNguyễn Thị Thu Hà    Thành viên HĐQT độc lập",
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    assert ("Phạm Văn Hùng", "Deputy CEO") in found
    assert ("Nguyễn Thị Thu Hà", "Independent Director") in found


def test_bare_names_without_local_role_are_not_discovered_v37_1_round5():
    docs = [{
        "title": "Generic company prose",
        "url": "https://example.com/news",
        "text": "Đào Hữu Huyền tham dự sự kiện. Nguyễn Văn An phát biểu tại hội nghị.",
        "method": "HTML text extraction",
    }]
    frame = extract_management_candidates_from_documents(docs)
    assert frame.empty



def test_compound_titles_beat_embedded_generic_titles_v37_1_round5b():
    docs = [{
        "title": "Official management roster 2025",
        "url": "https://example.com/management-2025.pdf",
        "text": (
            "Phạm Văn Hùng    Phó Tổng Giám đốc\n"
            "Đào Hữu Duy Anh    Phó Chủ tịch HĐQT\n"
            "Nguyễn Thị Thu Hà    Thành viên HĐQT độc lập"
        ),
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Phạm Văn Hùng", "Deputy CEO") in found
    assert ("Đào Hữu Duy Anh", "Vice Chairman") in found
    assert ("Nguyễn Thị Thu Hà", "Independent Director") in found



def test_adjacent_table_rows_do_not_leak_roles_v37_1_round5c():
    docs = [{
        "title": "Official roster 2025",
        "url": "https://example.com/roster.pdf",
        "text": (
            "Đào Hữu Huyền    Chủ tịch HĐQT\n"
            "Phạm Văn Hùng    Phó Tổng Giám đốc\n"
            "Nguyễn Thị Thu Hà    Thành viên HĐQT độc lập"
        ),
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    assert ("Phạm Văn Hùng", "Deputy CEO") in found
    assert ("Nguyễn Thị Thu Hà", "Independent Director") in found


def test_vice_chairman_compound_title_is_not_chairman_v37_1_round5c():
    docs = [{
        "title": "Official board roster 2025",
        "url": "https://example.com/board.pdf",
        "text": "Đào Hữu Duy Anh    Phó Chủ tịch HĐQT",
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Duy Anh", "Vice Chairman") in found
    assert ("Đào Hữu Duy Anh", "Chairman") not in found



def test_role_phrase_delimits_bare_name_when_layout_spaces_collapse_v37_1_round5d():
    docs = [{
        "title": "Official roster 2025",
        "url": "https://example.com/roster.pdf",
        "text": "Đào Hữu Huyền Chủ tịch HĐQT\nLưu Bách Đạt Tổng Giám đốc",
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    assert ("Lưu Bách Đạt", "CEO") in found



def test_flattened_multiple_honorific_people_keep_segment_local_roles_v37_1_round5e():
    docs = [{
        "title": "Official flattened roster 2025",
        "url": "https://example.com/flattened.html",
        "text": (
            "Ông Đào Hữu Huyền Chủ tịch HĐQT. "
            "Ông Lưu Bách Đạt Tổng Giám đốc. "
            "Ông Đào Hữu Duy Anh Phó Chủ tịch HĐQT. "
            "Ông Phạm Văn Hùng Phó Tổng Giám đốc."
        ),
        "method": "HTML text extraction",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    assert ("Lưu Bách Đạt", "CEO") in found
    assert ("Đào Hữu Duy Anh", "Vice Chairman") in found
    assert ("Phạm Văn Hùng", "Deputy CEO") in found



def test_role_before_name_signature_and_heading_noise_filter_v37_1_round5f():
    docs = [{
        "title": "Official personnel resolution 2025",
        "url": "https://example.com/personnel.pdf",
        "text": (
            "CHỦ TỊCH HĐQT\nĐào Hữu Huyền\n"
            "CBTT BIÊN BẢN HỌP NHÓM VÀ GIẤY ĐỀ CỬ THÀNH VIÊN HĐQT"
        ),
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    names = set(frame["Manager"].astype(str))
    assert "CBTT BIÊN BẢN" not in names
    assert "GIẤY ĐỀ CỬ" not in names
    assert "BOARD OF MANAGEMENT" not in names



def test_candidate_filter_rejects_org_navigation_places_and_related_person_v37_1_round5g():
    from modules.deep_company_analysis.chapter7_management_discovery import _plausible_manager_candidate

    assert _plausible_manager_candidate("Đào Hữu Huyền", "CHỦ TỊCH HĐQT Đào Hữu Huyền", "Tập đoàn Hóa chất Đức Giang")
    assert _plausible_manager_candidate("Lưu Bách Đạt", "Ông Lưu Bách Đạt Tổng Giám đốc", "Tập đoàn Hóa chất Đức Giang")
    for bad in [
        "BOARD OF MANAGEMENT", "DGC CHO THỜI GIAN CÒN", "DUC GIANG CHEMICALS GROUP JOINT",
        "MUA CỔ PHIẾU CỦA", "Phòng Kinh", "STT Họ", "Việt Nam", "Bình Dương", "Lào Cai", "Đức Giang",
    ]:
        assert not _plausible_manager_candidate(bad, f"{bad} Chủ tịch HĐQT", "Tập đoàn Hóa chất Đức Giang")
    assert not _plausible_manager_candidate(
        "Trần Thị Xuân", "Bà Trần Thị Xuân - mẹ TV HĐQT độc lập", "Tập đoàn Hóa chất Đức Giang"
    )


def test_research_targets_cover_chairman_ceo_and_exclude_noise_v37_1_round5g():
    frame = extract_management_candidates_from_documents(_docs(), company_name="Tập đoàn Hóa chất Đức Giang")
    targets = choose_research_targets(frame, max_targets=5, company_name="Tập đoàn Hóa chất Đức Giang")
    assert "Đào Hữu Huyền" in targets
    assert "Lưu Bách Đạt" in targets
    assert not any("BOARD" in name.upper() or "DGC CHO" in name.upper() for name in targets)



def test_relation_filter_is_immediate_and_does_not_reject_next_manager_named_anh_v37_1_round5h():
    from modules.deep_company_analysis.chapter7_management_discovery import _plausible_manager_candidate

    evidence = "Ông Lưu Bách Đạt Tổng Giám đốc. Ông Đào Hữu Duy Anh Phó Chủ tịch HĐQT."
    assert _plausible_manager_candidate("Lưu Bách Đạt", evidence, "Tập đoàn Hóa chất Đức Giang")
    assert _plausible_manager_candidate("Đào Hữu Duy Anh", evidence, "Tập đoàn Hóa chất Đức Giang")
    assert not _plausible_manager_candidate(
        "Trần Thị Xuân", "Bà Trần Thị Xuân - mẹ TV HĐQT độc lập", "Tập đoàn Hóa chất Đức Giang"
    )
