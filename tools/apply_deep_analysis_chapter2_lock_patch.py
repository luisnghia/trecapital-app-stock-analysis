from __future__ import annotations

"""One-time idempotent source transformation for the unified Chapter 1/2 deep-analysis page."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return False
    if old not in text:
        raise RuntimeError(f"Expected source block not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def patch_chapter2_bias() -> None:
    path = ROOT / "modules" / "deep_company_analysis" / "chapter2.py"
    old = 'bias_check = st.text_area("Bias check — tôi có đang yêu thích sản phẩm/ngành hoặc dựa quá nhiều vào người khác không?", value=q1.get("bias_check", ""), height=80, key=f"ch2_bias_{ticker}")'
    new = 'bias_check = st.text_area("Bias check — Tôi có đang thích sản phẩm quá mức? Tôi có thành kiến với ngành? Tôi có đang dựa vào người khác vì bản thân chưa hiểu? Tôi có đang ép mình nghiên cứu một ngành tôi thực sự không quan tâm?", value=q1.get("bias_check", ""), height=110, key=f"ch2_bias_{ticker}")'
    replace_once(path, old, new)


def patch_q6_extraction() -> None:
    path = ROOT / "modules" / "deep_company_analysis" / "chapter2_auto.py"
    text = path.read_text(encoding="utf-8")
    old_geo = '''def _find_geographies(text: str) -> list[str]:\n    normalized = f" {_norm(text)} "\n    found: list[str] = []\n    for canonical, aliases in COUNTRY_ALIASES.items():\n        if any(f" {_norm(alias)} " in normalized or _norm(alias) in normalized for alias in aliases):\n            found.append(canonical)\n    return found\n'''
    new_geo = '''def _alias_present(normalized_text: str, alias: str) -> bool:\n    token = _norm(alias)\n    if not token:\n        return False\n    pattern = r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"\n    return re.search(pattern, normalized_text) is not None\n\n\ndef _find_geographies(text: str) -> list[str]:\n    normalized = _norm(text)\n    found: list[str] = []\n    for canonical, aliases in COUNTRY_ALIASES.items():\n        if any(_alias_present(normalized, alias) for alias in aliases):\n            found.append(canonical)\n    return found\n'''
    if new_geo not in text:
        if old_geo not in text:
            raise RuntimeError("Expected geography extractor block not found")
        text = text.replace(old_geo, new_geo, 1)

    old_year = '''def _entry_year(text: str) -> str:\n    normalized = _norm(text)\n    match = re.search(r"(?:tu nam|since|bat dau tu|gia nhap|tham gia).*?((?:19|20)\\d{2})", normalized)\n    return match.group(1) if match else ""\n'''
    new_year = '''def _entry_year(text: str) -> str:\n    normalized = _norm(text)\n    patterns = (\n        r"(?:bat dau tu(?: nam)?|tu nam|since|gia nhap|tham gia)[^0-9]{0,50}((?:19|20)\\d{2})",\n        r"((?:19|20)\\d{2})[^.]{0,35}(?:bat dau|gia nhap|tham gia|entered|since)",\n    )\n    for pattern in patterns:\n        match = re.search(pattern, normalized)\n        if match:\n            return match.group(1)\n    return ""\n'''
    if new_year not in text:
        if old_year not in text:
            raise RuntimeError("Expected entry-year extractor block not found")
        text = text.replace(old_year, new_year, 1)
    path.write_text(text, encoding="utf-8")


def patch_package_init() -> None:
    path = ROOT / "modules" / "deep_company_analysis" / "__init__.py"
    path.write_text('"""Deep company analysis module for Trecapital."""\n', encoding="utf-8")


def patch_sidebar() -> None:
    path = ROOT / "tre_sidebar_nav.py"
    text = path.read_text(encoding="utf-8")
    old = '''    st.page_link("pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py", label="Phân tích chuyên sâu — Chương 1", icon="🔬")\n    st.page_link("pages/08_Phan_tich_chuyen_sau_Chuong_2.py", label="Phân tích chuyên sâu — Chương 2", icon="🔎")\n'''
    new = '''    st.page_link("pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py", label="Phân tích chuyên sâu doanh nghiệp", icon="🔬")\n'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Expected sidebar Chapter 1/2 links not found")
        text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")


def patch_unified_page() -> None:
    path = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
    text = path.read_text(encoding="utf-8")
    import_line = "from modules.deep_company_analysis.chapter2_page_support import render_chapter2_tab\n"
    anchor = "from modules.deep_company_analysis.trecapital_auto import build_chapter1_auto_data\n"
    if import_line not in text:
        if anchor not in text:
            raise RuntimeError("Could not find page07 import anchor")
        text = text.replace(anchor, anchor + import_line, 1)

    marker = 'st.title("Phân tích chuyên sâu doanh nghiệp")\n'
    if marker not in text:
        raise RuntimeError("Could not find page07 render marker")
    prefix = text.split(marker, 1)[0]
    tail = r'''st.title("Phân tích chuyên sâu doanh nghiệp")
st.caption("Khung phân tích doanh nghiệp theo The Investment Checklist — mỗi chương là một tab trong cùng workspace, dùng chung dữ liệu Trecapital.")

st.markdown(
    """
    <style>
    div[data-testid="stTabs"] {margin-top: 12px !important;}
    div[data-testid="stTabs"] div[role="tablist"] {
        display:flex !important; flex-wrap:wrap !important; gap:14px !important;
        background:rgba(234,247,241,.96) !important; padding:14px 16px !important;
        border-radius:26px !important; border:2px solid rgba(11,127,117,.30) !important;
        box-shadow:0 10px 26px rgba(11,127,117,.12) !important;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        min-height:58px !important; height:58px !important; border-radius:999px !important;
        padding:0 28px !important; border:2.5px solid rgba(11,127,117,.40) !important;
        background:#FFFFFF !important; color:#0B5F58 !important; font-size:1.04rem !important;
        font-weight:900 !important; box-shadow:0 6px 16px rgba(11,127,117,.10) !important;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background:linear-gradient(135deg,#0B7F75,#128C7E) !important; color:#FFFFFF !important;
        border-color:#F5B21B !important; box-shadow:0 10px 24px rgba(11,127,117,.28) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

default_ticker = _safe_ticker(
    str(
        st.session_state.get("dca_ch1_ticker")
        or st.session_state.get("dca_ch2_ticker")
        or st.session_state.get("active_ticker")
        or st.session_state.get("shared_ticker")
        or st.session_state.get("module2_ticker")
        or "DGC"
    )
) or "DGC"

chapter1_tab, chapter2_tab = st.tabs([
    "📗 Chương 1 — Cơ hội đầu tư",
    "📘 Chương 2 — Hiểu doanh nghiệp",
])

with chapter1_tab:
    with st.expander("📘 Hướng dẫn sử dụng Chương 1 — Hình thành & Sàng lọc Cơ hội đầu tư", expanded=True):
        st.markdown(
            """
**Mục tiêu của Chương 1:** biến một ý tưởng cổ phiếu thành một hồ sơ nghiên cứu có cấu trúc, sàng lọc nhanh chất lượng, ghi nhận định giá ban đầu và đưa doanh nghiệp vào đúng **Research Gate** để tiếp tục theo dõi.

**Quy trình sử dụng khuyến nghị:**

1. **Nhập mã cổ phiếu → bấm `🔄 Cập nhật dữ liệu & signals`.** Trecapital lấy dữ liệu canonical hiện có để prefill phần định lượng. Nếu quote đã cũ, các chỉ tiêu phụ thuộc giá sẽ được để trống thay vì dùng số cũ.
2. **A. Idea Origin:** ghi vì sao doanh nghiệp xuất hiện trên radar, tại sao thị trường có thể đang định giá sai và luận điểm ban đầu.
3. **B. Opportunity Signals:** xem drawdown 52 tuần, valuation percentile, price/fundamental divergence và event candidate. Đây chỉ là **research signal, không phải Buy Signal**.
4. **C. Quality Filter — Table 1.1:** đánh giá 10 tiêu chí `✓ Có / X Không / — Chưa biết / N/A`. `Data Suggested` chỉ hỗ trợ analyst; **Analyst Assessment mới là kết luận chính**. Confidence chỉ có **Thấp / Trung bình / Cao** và không cộng vào Quality Score.
5. **D–E. Research Gaps & Valuation Snapshot:** ghi các điểm chưa biết cần nghiên cứu thêm; kiểm tra Target Price, MOS, FCF Yield, TEV/EBIT, Debt/EBITDA... trước khi lưu snapshot.
6. **F. Research Gate:** chọn `🟢 Continue / 🟡 Watch / 🟠 Pause / 🔴 Reject` và bắt buộc ghi **Reason for Gate**. App **không tự đổi Gate**.
7. **Monitoring Trigger:** đặt điều kiện cần xem lại như `MOS > 25%`, `ROIC < 15%`, `Debt/EBITDA > 2x`, `có BCTC mới`, `BCTC Q3/2026` hoặc `event/CBTT mới`. Nên dùng **Structured Trigger Builder** thay vì gõ câu tự do khi có thể.

**Cách hiểu Monitoring / Review Queue:**  
`Opportunity Inventory` = danh sách cơ hội đang theo dõi → `Monitoring Trigger` = điều kiện anh muốn app kiểm tra → `Review Queue` = các điều kiện đã xảy ra và cần analyst mở hồ sơ xem lại → `Research Gate` = quyết định của analyst sau khi review.

Khi một trigger chuyển từ **chưa thỏa → thỏa**, app tạo một item trong **Review Queue** và tránh tạo cảnh báo trùng khi điều kiện vẫn tiếp tục thỏa. Sau khi đã xem xét, chọn item và bấm **`✅ Đã review item này`**; thao tác này chỉ đóng cảnh báo, **không thay đổi Research Gate**.

**Nguyên tắc cốt lõi:** **AI/Data = Research Assistant; người dùng = Investment Analyst.** Chương 1 không tự đưa ra BUY/HOLD/SELL.
            """
        )

    auto_data, auto_company_name, auto_error = _prepare_auto_data(default_ticker)
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            if auto_data:
                as_of = auto_data.get("as_of") or "—"
                source_label = auto_data.get("source_label") or auto_data.get("source_module") or "Trecapital"
                if auto_data.get("quote_fresh"):
                    st.success(f"Đã nối dữ liệu Trecapital cho {default_ticker} | kỳ dữ liệu: {as_of} | {source_label}")
                else:
                    st.warning(f"Đã nối BCTC Trecapital cho {default_ticker}, nhưng quote không còn đủ mới | kỳ dữ liệu: {as_of} | {source_label}")
                st.caption("Valuation Snapshot, 4 tiêu chí định lượng Table 1.1 và Opportunity Signals được prefill từ pipeline chung; event candidate luôn cần analyst xác minh.")
                event_note = str(st.session_state.get("dca_event_refresh_note", "") or "")
                if event_note:
                    st.caption(event_note)
            else:
                st.info(f"{default_ticker}: {auto_error}")
        with c2:
            if st.button("🔄 Cập nhật dữ liệu & signals", use_container_width=True, key="dca_refresh_trecapital"):
                with st.spinner(f"Đang cập nhật {default_ticker} qua pipeline chung của Trecapital..."):
                    ok = _refresh_trecapital(default_ticker)
                if ok:
                    st.success("Đã cập nhật dữ liệu và Opportunity Signals.")
                    st.rerun()
                else:
                    st.warning("Chưa lấy được bộ dữ liệu chuẩn. App không trộn dữ liệu từ mã khác.")

    if st.button("🔎 Quét Review Queue từ dữ liệu cache", use_container_width=True, key="dca_scan_review_queue"):
        with st.spinner("Đang kiểm tra trigger của Opportunity Inventory bằng dữ liệu local đã có..."):
            checked, skipped = _scan_review_queue_from_cache()
        st.success(f"Đã kiểm tra {checked} mã; bỏ qua {skipped} mã chưa có cache hoặc chưa đặt trigger.")
        st.rerun()

    render_chapter1(default_ticker=default_ticker, auto_data=auto_data, auto_company_name=auto_company_name)

with chapter2_tab:
    chapter2_ticker = _safe_ticker(
        str(
            st.session_state.get("dca_ch2_ticker")
            or st.session_state.get("dca_ch1_ticker")
            or st.session_state.get("active_ticker")
            or default_ticker
        )
    ) or default_ticker
    render_chapter2_tab(chapter2_ticker)

apply_full_width()
'''
    path.write_text(prefix + tail, encoding="utf-8")


def patch_legacy_page() -> None:
    path = ROOT / "pages" / "08_Phan_tich_chuyen_sau_Chuong_2.py"
    path.write_text('''from __future__ import annotations\n\nimport streamlit as st\n\nfrom tre_full_width import apply_full_width\nfrom tre_sidebar_nav import render_tre_sidebar_nav\nfrom ui_oaktree_theme import inject_oaktree_theme\n\nst.set_page_config(page_title="Chương 2 đã chuyển tab | Trecapital", page_icon="🔬", layout="wide")\ninject_oaktree_theme()\nwith st.sidebar:\n    render_tre_sidebar_nav()\n\nst.title("Phân tích chuyên sâu doanh nghiệp")\nst.info("Chương 2 đã được hợp nhất thành một tab trong trang Phân tích chuyên sâu doanh nghiệp để các chương dùng chung một workspace.")\nst.page_link("pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py", label="🔬 Mở Phân tích chuyên sâu doanh nghiệp")\napply_full_width()\n''', encoding="utf-8")


def main() -> None:
    patch_chapter2_bias()
    patch_q6_extraction()
    patch_package_init()
    patch_sidebar()
    patch_unified_page()
    patch_legacy_page()
    print("Deep-analysis Chapter 2 lock patch applied.")


if __name__ == "__main__":
    main()
