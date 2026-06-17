# V23.35 - Export layout fix

## Nội dung cập nhật

1. Tab **Định giá chuyên sâu**
   - Giảm chiều cao component của bảng **Đánh giá trọng yếu theo dữ liệu doanh nghiệp**.
   - Bỏ khoảng trống lớn giữa bảng đánh giá và các bảng/nội dung phía dưới.
   - Giữ chức năng click dòng để xem note giải thích.

2. Tab **Porter Moat Score**
   - Chuyển phần **Lý do phân loại** thành card vàng theo nhận diện Trecapital.
   - Nội dung lý do được hiển thị dạng danh sách dễ đọc hơn.

3. Xuất báo cáo Excel/Word
   - Đổi format báo cáo theo style app: xanh Trecapital, card vàng, bảng header xanh nhạt, heatmap xanh/đỏ/vàng.
   - Bổ sung sheet riêng **Biểu đồ** trong Excel để người dùng thấy biểu đồ ngay, không phải kéo qua bảng dài.
   - Word xuất trang ngang, card nhận xét, bảng style, biểu đồ đặt trước bảng dài.
   - Nếu máy chưa cài `kaleido`, app thử xuất biểu đồ bằng fallback Matplotlib.

4. Xuất báo cáo PDF
   - Không còn phụ thuộc cứng vào `reportlab`.
   - Nếu thiếu `reportlab`, app tự dùng fallback Pillow để tạo PDF dạng image-based report.
   - PDF vẫn có nội dung, bảng và biểu đồ nếu fallback chart render thành công.

## Dependency bổ sung

- `matplotlib==3.9.2` để làm fallback xuất ảnh biểu đồ khi `kaleido` chưa được cài.

Khuyến nghị chạy lại `install_and_run_app.bat` sau khi giải nén bản mới để cài đủ dependency.
