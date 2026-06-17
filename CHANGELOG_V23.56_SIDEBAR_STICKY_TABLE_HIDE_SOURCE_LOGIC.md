# V23.56 - Sidebar màu tab, cố định tiêu đề bảng, ẩn Nguồn/logic

## Cập nhật

1. Sidebar/slide điều hướng dùng màu giống các tab: nền vàng/xanh nhạt, hover vàng/xanh, page đang chọn nền xanh đậm và viền vàng.
2. Bổ sung CSS cố định dòng tiêu đề cho `st.dataframe`/`st.data_editor`; các bảng HTML có note cũng tăng z-index và shadow cho header sticky.
3. `_show_table` của Tổng quan doanh nghiệp và Định giá chuyên sâu có chiều cao mặc định để bảng cuộn nội bộ, hỗ trợ header cố định.
4. Ẩn cột `Nguồn/logic` khỏi 4 bảng phân tích thao túng tài chính: Beneish M-Score, Accrual Quality/Sloan, Modified Jones/Kothari, Real Earnings Management. Nội dung nguồn/logic vẫn giữ trong note dòng nếu cần truy vết.

## Kiểm tra

- `python -m py_compile module1_dashboard.py module2_dashboard.py module2_engine.py report_exporter.py`: OK.
- `python tools/run_module2_self_check.py`: OK.
