# V23.41 - Consolidated report: full evaluation tables and source-rule formatting

## Mục tiêu
- Sửa trang **Báo cáo tổng hợp toàn bộ nội dung** sau phản hồi V23.40.
- Đảm bảo các bảng đánh giá/chấm điểm quan trọng xuất hiện ngay trong báo cáo tổng hợp.
- Bỏ khối note tự sinh bên dưới bảng để báo cáo gọn, không rối.
- Chuẩn hóa format số liệu theo nguyên tắc nguồn của app.

## Thay đổi chính
1. Mục **0.1 Tổng hợp các bảng đánh giá và chấm điểm trong báo cáo** nay hiển thị trực tiếp toàn bộ bảng kiểm tra quan trọng, gồm:
   - Cảnh báo / điểm cần kiểm tra.
   - Kết quả định giá MOS.
   - Bộ tiêu chí FCF & dòng tiền năm/quý.
   - Cảnh báo dòng tiền năm/quý.
   - Bộ tiêu chí đánh giá chỉ số tài chính 100 điểm.
   - Cảnh báo/tình huống chỉ số tài chính.
   - Đánh giá trọng yếu theo dữ liệu doanh nghiệp.
   - Dải giá trị nội tại.
   - Bảng định giá theo từng phương pháp.
   - Porter Moat Score.
   - Chuỗi giá trị Porter.
   - Kịch bản & rủi ro.
   - Peer comparison nếu đã chạy.

2. Bỏ khối **Note / nhận xét / diễn giải đi kèm bảng** trong trang báo cáo tổng hợp.

3. Format số liệu HTML print table:
   - Chỉ tiêu tỷ đồng / VND / số lượng: không có số thập phân.
   - Chỉ tiêu phần trăm: 1 số thập phân.
   - Hệ số / P/E / P/B / P/S / vòng quay / điểm: 1 số thập phân.
   - Cột text, tín hiệu, diễn giải, công thức, đường dẫn: giữ nguyên nội dung.

## Phạm vi ảnh hưởng
- Chỉ sửa `report_exporter.py` và trang Báo cáo tổng hợp.
- Không thay đổi engine tính toán, công thức, dữ liệu nguồn, hay bảng tương tác trong từng phần 1/2/3.
