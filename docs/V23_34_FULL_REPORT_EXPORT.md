# V23.34 - Xuất báo cáo phân tích đầy đủ Excel / PDF / Word

## Nội dung cập nhật

- Thêm phần `report_exporter.py` để gom báo cáo phân tích của toàn bộ app vào một file xuất.
- Thêm khung **📤 Xuất báo cáo phân tích đầy đủ ra Excel / PDF / Word** tại Tổng quan doanh nghiệp, Định giá chuyên sâu và So sánh doanh nghiệp.
- Người dùng chọn định dạng file muốn xuất:
  - Excel `.xlsx`
  - Word `.docx`
  - PDF `.pdf`
- File xuất bao gồm:
  - Thông tin doanh nghiệp, nguồn dữ liệu/cache, KPI tổng hợp.
  - Tổng quan doanh nghiệp: tóm tắt nhanh, nhận xét theo triết lý đầu tư giá trị, định giá MOS, cảnh báo, FCF & dòng tiền, chỉ số tài chính, dữ liệu năm + TTM và quý.
  - Định giá chuyên sâu: định giá chuyên sâu, Porter Moat Score, chuỗi giá trị Porter, kịch bản & rủi ro, internet evidence nếu đã cập nhật.
  - So sánh doanh nghiệp: kết quả so sánh doanh nghiệp cùng ngành nếu đã chạy peer comparison.
  - Đồ thị chính: doanh thu/LNST, CFO/FCF/OE, ROIC/WACC, EPS/OEPS, FCF generation/usage/conversion, DuPont, ROIC & đầu tư, radar Porter Moat, radar chuỗi giá trị, peer score.

## Lưu ý kỹ thuật

- File cũng được lưu vào thư mục `reports/` để kiểm tra lại sau.
- Để xuất ảnh biểu đồ Plotly vào Excel/Word/PDF, app cần package `kaleido` trong `requirements.txt`.
- PDF dùng font Unicode nếu môi trường có sẵn Noto Sans/DejaVu Sans để hạn chế lỗi tiếng Việt.
- Nếu chưa chạy So sánh doanh nghiệp, phần peer comparison sẽ để trống và không làm app lỗi.

## Files thay đổi

- `report_exporter.py`
- `phần1_dashboard.py`
- `phần2_dashboard.py`
- `requirements.txt`
- `VERSION.txt`
