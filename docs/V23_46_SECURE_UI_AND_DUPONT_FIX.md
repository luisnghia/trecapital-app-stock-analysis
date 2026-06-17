# V23.46 - Secure UI, DuPont comment, peer button and FCF table header fix

## Nội dung cập nhật

1. Chỉnh tương phản nút lệnh theo theme Oaktree-inspired:
   - Ép màu chữ và icon trong button luôn tương phản với nền.
   - Hover/disabled state có màu chữ riêng để tránh trùng màu với nền.

2. Đổi tên nút:
   - Từ: `Lấy lại danh sách cùng ngành từ Simplize`
   - Thành: `Lấy danh sách cùng ngành`

3. Bảng `Bảng phân tích sử dụng dòng tiền theo năm/quý`:
   - Các dòng tiêu đề nhóm `(I)`, `(II)`, `(III)` được in đậm và tô nền nhẹ.

4. Tab `DuPont`:
   - Thêm card `Nhận xét quan trọng DuPont`.
   - Card phân tích ROE theo biên lợi nhuận, vòng quay tài sản, hệ số nhân vốn chủ và ROA.

5. Bảo mật giao diện:
   - Đổi tên các selectbox nguồn dữ liệu thành `Chế độ dữ liệu` với nhãn trung tính.
   - Ẩn tên nhà cung cấp dữ liệu, đường dẫn cache/raw, URL và các cột nguồn khỏi các bảng hiển thị.
   - Đổi `Internet evidence` thành `Bằng chứng định tính`.
   - Đổi `Công thức & audit` thành `Công thức & giả định`, không hiển thị đường dẫn kỹ thuật.

6. Bỏ tab `Nhật ký nguồn` khỏi Tổng quan doanh nghiệp.

## Kiểm tra

- `python -m py_compile`: OK
- `python tools/run_self_check.py data_sources/Financial-v1.3.0.xlsm --ticker DCM`: OK
- `python tools/run_module2_self_check.py`: OK
