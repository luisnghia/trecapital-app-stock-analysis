# V23.14 - Runtime CSS + MOS sync fix

## Lỗi đã sửa

1. Style tab/nhận xét bị mất sau khi đổi MOS do CSS trước đây được inject ở top-level import. Streamlit cache phần Python nên khi widget rerun, phần import không chạy lại. V23.14 chuyển CSS vào `_inject_runtime_ui_css()` và gọi ở đầu `render_dashboard()` của cả Tổng quan doanh nghiệp và Định giá chuyên sâu.

2. Tổng quan doanh nghiệp tab không nổi bật do style không được inject khi vào trang multipage đã cache import. V23.14 áp dụng lại CSS runtime cho mọi lần render và dùng selector rộng hơn cho `data-baseweb=tab-list`, `data-baseweb=tab`, `role=tablist`, `role=tab`.

3. Khi đổi MOS ở Định giá chuyên sâu, tab và font nhận xét biến mất do CSS không chạy lại sau rerun. Đã sửa bằng runtime CSS.

4. MOS đồng bộ Tổng quan doanh nghiệp ⇄ Định giá chuyên sâu qua khóa chuẩn `target_mos_pct`, còn widget mỗi trang dùng key riêng: `phần1_mos_widget`, `phần2_mos_widget`.

## Công thức MOS

- MOS hiện tại = (Giá trị nội tại - Giá hiện tại) / Giá trị nội tại.
- Giá mua tối đa theo MOS yêu cầu = Giá trị nội tại × (1 - MOS yêu cầu).
- Khi đổi MOS yêu cầu, MOS hiện tại không đổi; giá mua tối đa, tín hiệu đạt/chưa đạt MOS và chênh lệch so với MOS yêu cầu phải đổi.
