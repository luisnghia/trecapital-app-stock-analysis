# V23.42 - Clean consolidated print report

## Nội dung cập nhật

1. Báo cáo tổng hợp toàn bộ nội dung không còn in các bảng dữ liệu thô/chuẩn hóa:
   - Dữ liệu năm + TTM dùng cho biểu đồ
   - Dữ liệu quý dùng cho biểu đồ
   - Dữ liệu năm + TTM
   - Dữ liệu quý

2. Báo cáo tổng hợp không còn các section audit/data nguồn theo yêu cầu:
   - 1.7 Tổng quan doanh nghiệp / Tab Dữ liệu
   - 1.8 Tổng quan doanh nghiệp / Tab Nhật ký nguồn
   - 2.5 Định giá chuyên sâu / Tab Internet evidence
   - 2.6 Định giá chuyên sâu / Tab Dữ liệu
   - 2.7 Định giá chuyên sâu / Tab Công thức & audit

3. Bảng ROIC & đầu tư trong báo cáo in được tối ưu để fit dòng:
   - loại cột công thức WACC chi tiết khỏi báo cáo in;
   - giảm font/padding riêng cho bảng ROIC;
   - giữ các cột số liệu chính để phục vụ phân tích.

4. Bảng Kết quả peer comparison được nới rộng cột Mã/ticker, không bị xuống dòng.

5. Phạm vi sửa chỉ ở trang Báo cáo tổng hợp toàn bộ nội dung trong `report_exporter.py`, không thay đổi engine tính toán hay giao diện tương tác của các phần chính.
