# V23.45 - Sửa card Phân loại doanh nghiệp và chuyển Lý do phân loại

Ngày cập nhật: 2026-06-14

## Nội dung chỉnh sửa

1. Sửa card vàng **Phân loại doanh nghiệp** trong tab **Định giá chuyên sâu**:
   - Thêm hàm chuẩn hóa alias loại doanh nghiệp để engine trả `Financial / Bank / Insurance` vẫn map đúng sang hướng dẫn `Bank/Insurance`.
   - Engine trả `Asset Play / Deep Value` vẫn map đúng sang hướng dẫn `Asset Play`.
   - Bổ sung nhóm `Chưa có dữ liệu tài chính` để tránh rơi về `Normal Business` khi chưa đủ BCTC.
   - Dòng **Định giá nên ưu tiên** ưu tiên hiển thị `preferred_methods` do engine tính theo chính mã đang phân tích, thay vì chỉ dùng mô tả tĩnh.

2. Chuyển card vàng **Lý do phân loại**:
   - Bỏ card này khỏi tab **Porter Moat Score**.
   - Lồng trực tiếp vào card vàng **Phân loại doanh nghiệp** trong tab **Định giá chuyên sâu**.
   - Lý do phân loại lấy từ `cls.reasons`, tức các tín hiệu định lượng/định tính mà engine dùng cho mã đang xem.

3. Giữ nguyên logic định giá, MOS, Porter Moat Score, chuỗi giá trị, dữ liệu và báo cáo; chỉ sửa phần hiển thị/ánh xạ giao diện.

## Kiểm tra

- `python -m compileall -q .`: OK
- `python tools/run_module2_self_check.py`: OK
- `python tools/run_self_check.py data_sources/Financial-v1.3.0.xlsm --ticker DCM`: OK
