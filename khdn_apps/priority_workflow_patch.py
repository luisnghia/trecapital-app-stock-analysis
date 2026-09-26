"""Final priority UX bridge for KHDN planning.

This patch is intentionally installed after planning_priority_patch:
- QLKH always sees a priority selector while planning the week.
- Each quick-input line may override the default with Q1/Q2/Q3/Q4.
- Important-category catalog explicitly states that category assignment starts at Q2.
The existing planning_priority_patch remains the single owner of heat dashboard,
priority persistence, badges and leader approval editing.
"""
from __future__ import annotations

import re

VERSION="1.1.0"


def install(customer_ui, weekly_core, weekly_ui, logger=None):
    if getattr(weekly_core,"_PRIORITY_WORKFLOW_BRIDGE_INSTALLED",False):
        return

    if not getattr(weekly_core,"_PLANNING_PRIORITY_V2_INSTALLED",False):
        raise RuntimeError("priority_workflow_patch requires planning_priority_patch first")

    priority_label=getattr(weekly_core,"priority_label",lambda q:f"Q{int(q)}")

    # ---- Weekly Plan input: visible default + per-line override ----
    original_parse_line=weekly_core.parse_line
    def parse_line(line,ws,cs,forced=None):
        x=original_parse_line(line,ws,cs,forced)
        if not x or x.get("error"):
            return x
        m=re.search(r"(?:^|\s)Q\s*([1-4])(?:\s|$)",str(line or ""),flags=re.I)
        if m:
            x["priority_quadrant"]=int(m.group(1))
            # Keep title clean when the priority token is written into quick input.
            x["title"]=re.sub(r"(?:^|\s)Q\s*[1-4](?=\s|$)"," ",str(x.get("title") or ""),flags=re.I).strip()
        elif not x.get("priority_quadrant"):
            x["priority_quadrant"]=int(getattr(weekly_core,"_DEFAULT_PRIORITY_QUADRANT",4) or 4)
        return x
    weekly_core.parse_line=parse_line

    original_render=weekly_ui.render_page
    def render_page(st,u,get_conn,page_title=None,logger=None):
        role=str(u.get("role") or "")
        if role=="Cán bộ QLKH":
            st.markdown("#### 🎯 Mức ưu tiên kế hoạch")
            current=int(st.session_state.get("wp_priority_default",4) or 4)
            if current not in (1,2,3,4): current=4
            chosen=st.selectbox(
                "Ưu tiên mặc định cho công việc mới",
                [1,2,3,4],
                index=[1,2,3,4].index(current),
                format_func=priority_label,
                key="wp_priority_default",
            )
            weekly_core._DEFAULT_PRIORITY_QUADRANT=int(chosen)
            st.caption("Mức này áp dụng cho công việc mới. Khi nhập nhanh nhiều dòng, có thể ghi Q1/Q2/Q3/Q4 trong từng dòng để đặt ưu tiên riêng; sau khi Phân tích vẫn có thể chỉnh từng việc.")
        else:
            weekly_core._DEFAULT_PRIORITY_QUADRANT=4
        return original_render(st,u,get_conn,page_title,logger)
    weekly_ui.render_page=render_page

    # ---- Important category: category master only, default semantic = Q2 ----
    original_catalog=customer_ui.render_catalog_page
    def render_catalog_page(st,u,get_conn,page_title=None,logger=None):
        st.info("**Danh mục công việc quan trọng** chỉ là danh sách nhóm để tạo/sửa/xóa. Khi một danh mục được gán cho công việc, hệ thống mặc định xếp **Q2 – Quan trọng & Chưa khẩn cấp**. Chỉ khi Lãnh đạo/Admin chủ động đánh dấu khẩn cấp thì công việc mới chuyển sang Q1.")
        return original_catalog(st,u,get_conn,page_title,logger)
    customer_ui.render_catalog_page=render_catalog_page

    weekly_core._PRIORITY_WORKFLOW_BRIDGE_INSTALLED=True
    if logger:
        logger.info("PRIORITY_WORKFLOW_BRIDGE_INSTALLED version=%s",VERSION)
