from __future__ import annotations

import re

import streamlit as st

from ..services.integration_service import build_repository
from ..services.extension_schema_cache import ensure_extension_schema
from ..services.reporting import build_investment_checklist_docx_bytes


def _filename_token(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text.strip("_") or "REPORT"


def render_word_report_export(host, *, review_id: int | None, data_provider=None, repo=None) -> None:
    """Lazy Word export: no DB/financial work until the analyst explicitly prepares the report."""
    st.markdown("#### 📄 Investment Checklist Word Report — V99")
    st.caption(
        "Báo cáo lấy Analyst Assessment hiện tại + Research Evidence đã liên kết + financial evidence 10 năm/TTM "
        "từ Trecapital Data Layer. Không gọi nguồn dữ liệu mới và không tái tính công thức tài chính."
    )
    if not review_id:
        st.info("Hãy tạo/chọn một review trước khi xuất báo cáo Word.")
        return

    cache_key = f"_checklist_v99_word_report_{int(review_id)}"
    if st.button(
        "🧾 Tạo / làm mới báo cáo Word",
        type="primary",
        use_container_width=True,
        key=f"prepare_checklist_word_{int(review_id)}",
    ):
        try:
            with st.spinner("Đang dựng Investment Research Report từ dữ liệu đã lưu và Trecapital Data Layer..."):
                active_repo = repo or build_repository(host)
                ensure_extension_schema(active_repo)
                company = active_repo.get_company_ref_by_host_key(host.company.company_key)
                if not company:
                    raise ValueError("Chưa tìm thấy company context của review hiện tại.")
                review = active_repo.get_review(int(review_id))
                if not review or int(review.get("company_ref_id")) != int(company["id"]):
                    raise ValueError("Review đang chọn không còn thuộc company context hiện tại.")
                docx_bytes, payload = build_investment_checklist_docx_bytes(
                    active_repo,
                    int(company["id"]),
                    int(review_id),
                    data_provider=data_provider,
                    max_financial_years=10,
                )
                st.session_state[cache_key] = {
                    "data": docx_bytes,
                    "ticker": company.get("ticker") or host.company.ticker,
                    "as_of_date": review.get("as_of_date") or "ASOF",
                    "generated_at": payload.get("generated_at"),
                    "answered": payload.get("metrics", {}).get("answered", 0),
                    "research_gaps": payload.get("metrics", {}).get("research_gaps", 0),
                }
            st.success("Đã dựng báo cáo Word V99. File chỉ phản ánh trạng thái tại thời điểm bấm tạo/làm mới.")
        except Exception as exc:
            st.error(f"Chưa tạo được báo cáo Word: {exc}")

    cached = st.session_state.get(cache_key)
    if not isinstance(cached, dict) or not cached.get("data"):
        st.info("Bấm “Tạo / làm mới báo cáo Word” để tạo snapshot báo cáo hiện tại.")
        return

    cols = st.columns(3)
    cols[0].metric("Checklist answered", cached.get("answered", 0))
    cols[1].metric("Research gaps", cached.get("research_gaps", 0))
    cols[2].metric("Review", f"#{int(review_id)}")
    st.caption(f"Snapshot báo cáo tạo lúc: {cached.get('generated_at') or '—'}")

    filename = (
        f"Trecapital_Investment_Checklist_{_filename_token(cached.get('ticker'))}_"
        f"{_filename_token(cached.get('as_of_date'))}_Review_{int(review_id)}_V99.docx"
    )
    st.download_button(
        "⬇️ Tải báo cáo Word (.docx)",
        data=cached["data"],
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
        key=f"download_checklist_word_{int(review_id)}",
    )
    st.warning(
        "Nếu analyst vừa sửa Assessment/Evidence sau thời điểm snapshot ở trên, hãy bấm “Tạo / làm mới báo cáo Word” trước khi tải."
    )


__all__ = ["render_word_report_export"]
