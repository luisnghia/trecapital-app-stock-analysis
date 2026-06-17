# V23.23 - Fix danh sách cùng ngành và nút phần

## Lỗi đã sửa

1. So sánh doanh nghiệp chỉ lấy được 1 mã (mã gốc như DGC) từ trang Vietstock cùng ngành.
   - Nguyên nhân: bảng doanh nghiệp cùng ngành trên Vietstock được render động bằng JavaScript; HTML public thường chỉ chứa mã gốc, breadcrumb ngành và biến GICS.

2. Nút chuyển trang Tổng quan doanh nghiệp / Định giá chuyên sâu / So sánh doanh nghiệp trong sidebar chưa nổi bật theo nhận diện thương hiệu quỹ.

## Cách xử lý

- Tách GICS ngành từ HTML Vietstock: `_gicsLevel1..4`, `_gicsNameLevel1..4`.
- Thử các endpoint Vietstock legacy và lưu toàn bộ raw audit.
- Bổ sung fallback FireAnt ICB theo dạng `api.fireant.vn/icb/{industryCode}/symbols` khi Vietstock không trả peer-list JSON.
- Nếu các nguồn động vẫn không trả danh sách hợp lệ, dùng seed fallback minh bạch theo ngành nhận diện, ví dụ ngành Hóa chất/Phân bón gồm DGC, DPM, DCM, BFC, LAS, DDV, CSV, HVT, SFG, VAF, NET.
- Không còn xem trường hợp chỉ có đúng mã gốc là crawl thành công.
- Nâng cấp CSS sidebar navigation theo màu nhận diện Trecapital: xanh ngọc lục bảo / teal + vàng gold.

## Audit trail

Raw crawl vẫn lưu tại `raw_data/vietstock_peers/`; CSV cùng tên được tạo cạnh file JSON để kiểm tra nhanh.
