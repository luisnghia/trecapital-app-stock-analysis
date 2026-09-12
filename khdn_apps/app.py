"""Compressed loader for KHDN Ops V2.28 production hosting.
Loads the engine with persistent paths and consistent SQLite backups.
"""
from pathlib import Path as _Path
import base64 as _base64
import gzip as _gzip

_parts = sorted((_Path(__file__).resolve().parent / "_src").glob("*.txt"))
_payload = "".join(_p.read_text(encoding="ascii") for _p in _parts)
_source = _gzip.decompress(_base64.b64decode(_payload)).decode("utf-8")
exec(compile(_source, str(_Path(__file__).resolve().parent / "app_v223_source.py"), "exec"), globals(), globals())

# V2.24: always keep the user guide available online even when the DOCX is not
# stored in Git.  The full Word file is still used when present; otherwise the
# embedded Markdown guide is rendered and can be downloaded from the app.
_ORIGINAL_GUIDE_PAGE = guide_page

def guide_page(u):
    page_title("Hướng dẫn sử dụng", "Tài liệu hướng dẫn KHDN Ops được đính kèm trực tiếp trong ứng dụng.")
    st.info("📘 Workflow CBHT/QLKH/Lãnh đạo/Admin, Dashboard, mục tiêu tuần-tháng, lịch sử, tỷ giá, sao lưu và xử lý sự cố.")
    md_path = _Path(__file__).resolve().parent / "GUIDE.md"
    if GUIDE_PATH.exists():
        data = GUIDE_PATH.read_bytes()
        st.download_button(
            "⬇️ Tải Hướng dẫn sử dụng KHDN Ops (.docx)",
            data=data,
            file_name="HUONG_DAN_SU_DUNG_KHDN_OPS_v2.22.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key="download_khdn_guide_docx",
        )
    elif md_path.exists():
        guide_text = md_path.read_text(encoding="utf-8")
        st.download_button(
            "⬇️ Tải Hướng dẫn sử dụng (.md)",
            data=guide_text.encode("utf-8"),
            file_name="HUONG_DAN_SU_DUNG_KHDN_OPS.md",
            mime="text/markdown",
            use_container_width=True,
            key="download_khdn_guide_md",
        )
        st.markdown(guide_text)
    else:
        st.warning("Chưa tìm thấy tài liệu hướng dẫn trong gói triển khai.")
