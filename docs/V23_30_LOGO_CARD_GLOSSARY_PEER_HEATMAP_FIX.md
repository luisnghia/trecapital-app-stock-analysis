# V23.30 - Logo/card/glossary/peer table/heatmap fixes

## Các chỉnh sửa chính

1. Chỉ giữ một logo Trecapital ở sidebar, bỏ logo trùng trong phần nội dung Tổng quan doanh nghiệp để giao diện gọn hơn.
2. Giảm kích thước các card/hero/metric khoảng 10% so với V23.29.
3. Bảng "Diễn giải thuật ngữ và từ viết tắt" của Định giá chuyên sâu chuyển sang HTML table có cột STT/Thuật ngữ ôm sát nội dung, cột Diễn giải tự mở rộng và xuống dòng.
4. Bảng danh sách cổ phiếu cùng ngành từ Simplize:
   - Dòng mã đang phân tích được tô nền vàng thương hiệu.
   - Cột Vốn hóa được chuyển ngay sau cột Giá hiện tại.
   - Vẫn giữ cột tick chọn mã so sánh và mã đang phân tích được tick mặc định.
5. Bảng kết quả so sánh peer bổ sung heatmap đủ mức cho cột Moat level, bao gồm Lợi thế khá, Lợi thế trung bình/yếu/mạnh.

## Kiểm tra

- `python -m py_compile app.py phần1_dashboard.py phần2_dashboard.py phần1_engine.py phần2_engine.py pages/*.py`: OK.
- `python tools/run_phần2_self_check.py`: OK.
