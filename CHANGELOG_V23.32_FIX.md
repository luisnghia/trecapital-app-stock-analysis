# V23.34 - Full report export

- Thêm nút/khung xuất báo cáo phân tích đầy đủ ra Excel/PDF/Word ở Tổng quan doanh nghiệp, Định giá chuyên sâu và So sánh doanh nghiệp.
- Thêm `report_exporter.py` để gom toàn bộ bảng dữ liệu, đánh giá, cảnh báo, internet evidence, peer comparison và đồ thị vào file báo cáo.
- Bổ sung dependencies: `python-docx`, `reportlab`, `kaleido`, `Pillow`.

# V23.32-fix-note-mos

Các thay đổi chính:

1. Bảng **Kết quả định giá MOS** ở Tổng quan doanh nghiệp hiển thị full bảng, không còn cuộn bên trong bảng.
2. Card đỏ **Tóm tắt tự động** ở Định giá chuyên sâu không còn tự chèn nội dung **Đặc điểm cần kiểm tra**.
3. Sửa lỗi chọn dòng không hiện note: phục hồi cơ chế click ổn định theo v23.31 (`data-note` + listener trực tiếp từng dòng), áp dụng cho cả Tổng quan doanh nghiệp và Định giá chuyên sâu.
4. Giữ cơ chế hiển thị full bảng cho **Đánh giá trọng yếu theo dữ liệu doanh nghiệp** ở Định giá chuyên sâu.

Đã kiểm tra:
- `python -m py_compile` với các file app/phần chính.
- `python tools/run_self_check.py data_sources/Financial-v1.3.0.xlsm --ticker DCM`.
- `python tools/run_phần2_self_check.py`.

## Bổ sung - Value Chain Brand Card

- Thêm card đánh giá màu vàng thương hiệu trong tab Chuỗi giá trị, phần Bản đồ chuỗi giá trị theo Porter.
- Card tổng hợp điểm nhiệt, số hoạt động tốt/trung bình/yếu/cần bổ sung, hoạt động nổi bật và điểm cần kiểm tra.
- Giữ nguyên cơ chế click note ổn định và bảng MOS full không cuộn trong bảng.
