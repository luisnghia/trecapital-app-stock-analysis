# V23.14 – Sửa UI tab, MOS đồng bộ và note nhận xét

## Nội dung sửa

1. Sửa giao diện tab Tổng quan doanh nghiệp/Định giá chuyên sâu bằng CSS global mạnh hơn cho Streamlit:
   - tab to hơn, bo tròn, viền xanh teal;
   - tab active nền xanh teal, chữ trắng, viền vàng Trecapital;
   - ép hiển thị tablist để tránh trường hợp tab biến mất sau khi đổi MOS.

2. Sửa hiển thị nhận xét quan trọng:
   - dùng hàm `render_important_red` chung;
   - nền đỏ nhạt, viền trái đỏ, tiêu đề đỏ đậm, chữ lớn hơn;
   - chuyển markdown `**...**` sang HTML `<b>...</b>` để không còn hiện dấu `**` trên màn hình.

3. Sửa đồng bộ MOS:
   - dùng canonical key `target_mos_pct`;
   - Tổng quan doanh nghiệp dùng widget key riêng `phần1_mos_widget`;
   - Định giá chuyên sâu dùng widget key riêng `phần2_mos_widget`;
   - khi đổi MOS ở một phần, callback cập nhật `target_mos_pct`, `phần1_target_mos_pct`, `phần2_target_mos_pct`.

4. Công thức giữ nguyên:
   - MOS hiện tại = (Giá trị nội tại - Giá hiện tại) / Giá trị nội tại.
   - Giá mua theo MOS chọn = Giá trị nội tại × (1 - MOS yêu cầu).
   - Khi đổi MOS, MOS hiện tại không đổi; giá mua theo MOS chọn, chênh lệch so với MOS yêu cầu và tín hiệu đạt/chưa đạt MOS phải đổi.
