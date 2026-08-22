# V23.87 — Phase 5 route + responsive Industry tables

## Sửa lỗi

- Nối `👥 Management & Human Intel` vào đúng dispatcher Fast Entry V3 đang được trang Investment Checklist sử dụng.
- Chọn Phase 5 không còn rơi xuống nhánh mặc định `Công thức & giả định`.
- Đồng bộ cảnh báo xóa review trong shell V3 với bốn nhóm dữ liệu Phase 5.

## Industry & Moat trên tablet

- Chuyển KPI ngành, KPI coverage, Operating Driver, Porter/Moat, Value Chain và Bridge sang Checklist sang bảng HTML responsive.
- Nội dung dài tự xuống dòng; không còn bị cắt trong ô.
- Bảng nhiều cột có vùng cuộn ngang riêng, hỗ trợ thao tác cảm ứng và không làm tràn toàn trang.
- Header/cell dùng `overflow-wrap:anywhere`, `word-break:break-word` và cỡ chữ/padding riêng cho màn hình dưới 900 px.

## Regression

- Test khóa đúng entrypoint `integration_preview_v3` và nhánh render Phase 5.
- Test khóa CSS wrap, tablet scrolling và tối thiểu bốn bảng Industry responsive trong Streamlit smoke.
