# V23.40 - Full static print report

## Mục tiêu
- Trang **Báo cáo tổng hợp toàn bộ nội dung** dùng để in/Save as PDF phải bung đầy đủ toàn bộ bảng, không còn khung cuộn `st.dataframe` bị cắt khi in.
- Bổ sung note/nhận xét/diễn giải/chấm điểm dưới các bảng đánh giá quan trọng để báo cáo PDF không thiếu nội dung đang chỉ hiện khi click/double click trong app.

## Thay đổi chính
1. Chỉ thay đổi cách render bảng ở trang báo cáo tổng hợp trong `report_exporter.py`.
2. Các bảng tương tác trong từng phần 1, Định giá chuyên sâu, So sánh doanh nghiệp không đổi.
3. Thay `st.dataframe` trong trang báo cáo tổng hợp bằng HTML table tĩnh:
   - In full toàn bộ dòng.
   - Giữ heatmap xanh/đỏ/vàng.
   - Không còn thanh cuộn nội bộ khi in PDF.
4. Thêm khối `Note / nhận xét / diễn giải đi kèm bảng` cho các bảng:
   - Đánh giá trọng yếu.
   - Dải giá trị nội tại.
   - Bảng định giá theo phương pháp.
   - Porter Moat Score.
   - Chuỗi giá trị Porter.
   - Kịch bản/rủi ro.
   - Các bảng chấm điểm/cảnh báo có cột nhận xét/tín hiệu.

## Ảnh hưởng
- Không thay đổi công thức, engine tính toán, nguồn dữ liệu, session state.
- Không ảnh hưởng bảng tương tác trong các phần.
- PDF có thể dài hơn nhưng đầy đủ hơn.
- Khuyến nghị in A4 ngang và bật Background graphics.
