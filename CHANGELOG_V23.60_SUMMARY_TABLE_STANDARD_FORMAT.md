# V23.60 - Chuẩn hóa bảng tổng hợp thao túng tài chính 4 lớp

## Nội dung cập nhật

- Sửa bảng **Tổng hợp thao túng tài chính 4 lớp** trong tab **Thao túng tài chính**:
  - Chuyển từ `st.dataframe` về bảng HTML cùng phong cách với các bảng phân tích chuẩn trong app.
  - Giữ header xanh nhạt, viền bo góc, hover dòng, màu tín hiệu/cảnh báo/điểm nhiệt tương tự các bảng chi tiết.
  - Bỏ phần note/click riêng của bảng này theo yêu cầu.
  - Tăng chiều cao hiển thị để xem đủ 4 lớp, không cần cuộn dọc.

## Kiểm tra

- `python -m py_compile module2_engine.py module2_dashboard.py`
- `python tools/run_module2_self_check.py`
