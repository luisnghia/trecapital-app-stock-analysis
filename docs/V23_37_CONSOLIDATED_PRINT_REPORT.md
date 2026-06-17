# V23.37 - Báo cáo tổng hợp toàn bộ nội dung để in PDF

## Nội dung cập nhật

1. Thêm trang mới `Báo cáo tổng hợp toàn bộ nội dung` tại sidebar.
2. Trang này render toàn bộ nội dung chính của:
   - Tổng quan doanh nghiệp - Tổng quan doanh nghiệp;
   - Định giá chuyên sâu - Định giá chuyên sâu;
   - So sánh doanh nghiệp cùng ngành nếu đã chạy.
3. Nút PDF trong khung xuất báo cáo không còn chỉ hướng người dùng in tab hiện tại, mà điều hướng sang trang báo cáo tổng hợp.
4. Trên trang báo cáo tổng hợp có nút `In Báo cáo tổng hợp toàn bộ nội dung / Save as PDF` để in toàn trang dài, giữ format app tốt hơn: card, màu, bảng và biểu đồ Plotly.
5. Có tùy chọn độ dài bảng:
   - Đầy đủ: giữ toàn bộ dòng.
   - Gọn để in nhanh: giới hạn 40 dòng mỗi bảng.

## Hướng dẫn xuất PDF đẹp

1. Mở trang `Báo cáo tổng hợp toàn bộ nội dung`.
2. Chọn mã cổ phiếu, nguồn dữ liệu, MOS.
3. Bấm `In Báo cáo tổng hợp toàn bộ nội dung / Save as PDF`.
4. Trong hộp thoại in:
   - Destination: Save as PDF hoặc Microsoft Print to PDF.
   - Layout: Landscape / A4 ngang.
   - Bật Background graphics để giữ màu card/bảng.

## Kiểm tra kỹ thuật

Đã kiểm tra cú pháp bằng `py_compile` cho các file chính và page mới.
