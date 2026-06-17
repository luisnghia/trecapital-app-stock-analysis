# V23.8 - Mặc định Tổng quan doanh nghiệp và một nút cập nhật Định giá chuyên sâu

## Nội dung cập nhật

1. Mở app mặc định vào Dashboard Tổng quan doanh nghiệp - Tổng quan doanh nghiệp.
2. Khi tìm mã cổ phiếu ở Tổng quan doanh nghiệp, app tự cập nhật dữ liệu dùng chung cho Định giá chuyên sâu và tự tìm evidence internet cho moat/rủi ro/BCTC.
3. Ở Định giá chuyên sâu chỉ còn một nút: **Tìm kiếm/cập nhật tất cả**. Nút này đồng thời:
   - đồng bộ BCTC/cache từ pipeline Tổng quan doanh nghiệp sang Định giá chuyên sâu;
   - làm mới dữ liệu crawler nếu cần;
   - tìm evidence internet và lưu audit trail vào `raw_data/phần2_web/<ticker>/`.

## Nguyên tắc vận hành

- Tổng quan doanh nghiệp là pipeline dữ liệu gốc.
- Định giá chuyên sâu không yêu cầu người dùng chạy riêng nhiều nút.
- Evidence internet là bằng chứng định tính/phụ trợ; số liệu định giá ưu tiên dữ liệu BCTC đã chuẩn hóa từ Tổng quan doanh nghiệp.
- Các bảng phân tích vẫn dùng cơ chế nhấp một lần vào dòng/chỉ tiêu để xem note giải thích.
