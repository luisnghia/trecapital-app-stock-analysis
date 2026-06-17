# V23.58 - Financial Manipulation Summary + Report Table Fit

## Cập nhật

1. Tab **Thao túng tài chính**
   - Thêm bảng **Tổng hợp thao túng tài chính 4 lớp** phía trên các nút/tab lớp chi tiết.
   - Bảng tổng hợp hiển thị kỳ mới nhất, chỉ tiêu chính, giá trị, mức cảnh báo, điểm nhiệt, tín hiệu và nội dung cần kiểm tra cho 4 lớp: Beneish, Sloan/Accrual Quality, Modified Jones/Kothari và REM.
   - Bảng có note giải thích khi nhấp vào từng dòng.

2. **Báo cáo tổng hợp toàn bộ nội dung**
   - Bỏ cột **Lớp** khỏi các bảng thao túng tài chính theo từng lớp để bảng gọn hơn.
   - Giữ cột **Kỳ/Kỳ mới nhất** không xuống dòng khi hiển thị/in báo cáo.
   - Bổ sung CSS `col-period` cho bảng HTML trong báo cáo tổng hợp.

3. Kiểm tra
   - `python -m py_compile module2_dashboard.py report_exporter.py module2_engine.py`: OK.
   - `python tools/run_module2_self_check.py`: OK.
