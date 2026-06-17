# V23.36 - Print PDF & note scroll fix

## Nội dung cập nhật

1. Tab **Định giá chuyên sâu**
   - Sửa vùng note của bảng **Đánh giá trọng yếu theo dữ liệu doanh nghiệp**.
   - Bảng vẫn giữ gọn để không tạo khoảng trống lớn.
   - Note có vùng hiển thị cao hơn, có `overflow-y:auto` và iframe được phép cuộn để đọc hết nội dung dài.

2. Xuất PDF
   - PDF mặc định chuyển sang cơ chế **in trang hiện tại thành PDF** bằng hộp thoại in của trình duyệt.
   - Cách này giữ layout, màu card, bảng, biểu đồ và bố cục gần đúng như app đang hiển thị.
   - Khi in, chọn **Save as PDF** hoặc **Microsoft Print to PDF**, khổ giấy **A4 ngang**, bật **Background graphics**.
   - Vẫn giữ tùy chọn PDF tổng hợp server-side trong expander dự phòng.

## Ghi chú kỹ thuật

- Thêm CSS `@media print` để ẩn sidebar/header/nút lệnh khi in PDF.
- Thêm nút HTML/JS `window.parent.print()` trong khung xuất báo cáo PDF.
- Không cần `reportlab` cho luồng PDF chính.
