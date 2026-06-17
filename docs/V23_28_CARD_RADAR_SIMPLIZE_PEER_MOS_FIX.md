# V23.28 - Card, radar scorecards, Simplize peer selector, MOS fix

## Nội dung sửa

1. Tăng kích thước các card KPI/metric thêm khoảng 20%.
2. Thêm biểu đồ mạng nhện cho:
   - Bảng đánh giá FCF & dòng tiền theo năm/quý.
   - Bảng đánh giá phân tích chỉ số tài chính.
3. Sửa crawler/parser Simplize peer:
   - Loại bỏ các dòng header/chỉ tiêu như ROE, ROA, EPS, FCF, CFO, MOS, WACC... không được đưa vào danh sách cổ phiếu.
   - Bổ sung kiểm tra tên dòng sau mã để tránh bắt nhầm header của bảng.
4. So sánh doanh nghiệp:
   - Bảng danh sách cổ phiếu cùng ngành có cột tick `Chọn`.
   - Mặc định không tự chọn mã; người dùng chọn xong bấm So sánh.
   - Thêm ô nhập mã thủ công, cách nhau bằng dấu phẩy.
   - Mã đang phân tích vẫn tự tham gia xếp hạng và được tô màu riêng trong bảng kết quả, nhưng không hiển thị cột `Mã đang phân tích`.
   - Bảng kết quả bỏ cột nguồn dữ liệu, giữ cột `Vốn hóa (tỷ đồng)`.
5. Sửa MOS trong từng phần 2 engine:
   - Nếu giá trị nội tại/cp <= 0 thì không tính giá MOS và MOS hiện tại.
   - Nếu kịch bản định giá âm/không dương thì MOS kịch bản để trống để tránh lỗi MOS dương giả tạo.

## Kiểm tra

- `python -m py_compile phần1_dashboard.py phần2_dashboard.py phần2_engine.py adapters/vn_public_crawler.py`
- `python tools/run_phần2_self_check.py`
