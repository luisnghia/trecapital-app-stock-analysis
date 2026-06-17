# V23.8 - Tự đồng bộ Tổng quan doanh nghiệp ⇄ Định giá chuyên sâu và note giải thích khi nhấp đôi

## 1. Tự đồng bộ dữ liệu

Từ V23.8, app dùng chung một bộ dữ liệu hoạt động cho cả Tổng quan doanh nghiệp và Định giá chuyên sâu thông qua các khóa session:

- `active_ticker`
- `active_overview_csv`
- `active_year_csv`
- `active_quarter_csv`
- `active_source_label`

Khi nhập mã ở Tổng quan doanh nghiệp, app tự chạy pipeline Tổng quan doanh nghiệp, lưu dữ liệu chuẩn hóa vào `data_cache`, lưu raw response vào `raw_data`, rồi kích hoạt bộ dữ liệu này cho cả Tổng quan doanh nghiệp và Định giá chuyên sâu.

Khi nhập mã ở Định giá chuyên sâu với nguồn **Tự động từ dữ liệu tổng quan**, thứ tự xử lý là:

1. Ưu tiên bộ dữ liệu đang hoạt động của Tổng quan doanh nghiệp nếu cùng mã.
2. Nếu chưa có, tìm cache Tổng quan doanh nghiệp/Định giá chuyên sâu đã tạo trước đó.
3. Nếu vẫn chưa có, tự gọi pipeline crawler Tổng quan doanh nghiệp: FireAnt + Vietstock.
4. Nếu crawler không trả dữ liệu chuẩn, fallback về Financial tích hợp nếu mã có đủ block BCTC.

## 2. Note giải thích khi nhấp đôi vào chỉ tiêu

Các bảng đánh giá/định giá quan trọng của Định giá chuyên sâu được render thành bảng HTML có sự kiện double-click. Khi nhấp đôi vào một dòng, app hiển thị note gồm:

- Chỉ tiêu/phương pháp đang xem.
- Số liệu cụ thể của dòng đó.
- Cơ sở tính/cảnh báo.
- Nguyên tắc đánh giá theo triết lý đầu tư giá trị và Porter.

Các bảng áp dụng:

- Dải giá trị nội tại.
- Bảng định giá theo từng phương pháp.
- Porter Moat Scorecard.
- Chuỗi giá trị Porter.
- Kịch bản & rủi ro.
- Tín hiệu kỳ gần nhất.

## 3. Nguyên tắc định dạng

Tiếp tục giữ nguyên yêu cầu nguồn dự án:

- Số liệu tiền tệ: tỷ đồng hoặc đồng/cp tùy bảng.
- Phần trăm: 1 số thập phân.
- Hệ số: 1 số thập phân.
- Số âm màu đỏ, số dương/tăng trưởng dương màu xanh ngọc lục bảo.
- Công thức và logic phải có tài liệu giải thích trong thư mục `docs`.
