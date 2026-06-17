# V23.26 - So sánh doanh nghiệp chuyển peer crawler sang Simplize

## Thay đổi chính

1. So sánh doanh nghiệp không còn dùng Vietstock/Selenium để lấy danh sách doanh nghiệp cùng ngành.
2. App dùng Simplize theo 2 cách:
   - nếu người dùng nhập URL ngành Simplize, app lấy trực tiếp URL đó;
   - nếu để trống, app mở trang `https://simplize.vn/co-phieu/{MÃ}` để tự tìm link ngành rồi lấy danh sách cổ phiếu trong trang ngành.
3. Raw audit được lưu tại `raw_data/simplize_peers/`.
4. Nếu Simplize đổi bố cục hoặc không trả danh sách, app báo lỗi rõ và không tự sinh peer suy đoán.
5. Đã bỏ dependency Selenium và file worker Vietstock khỏi gói app.

## Ví dụ URL ngành

`https://simplize.vn/co-phieu/nganh/cong-nghiep/co-so-ha-tang-giao-thong-van-tai`

Trang này có danh sách cổ phiếu ngành và các cột như giá hiện tại, biến động giá, P/E, P/B, ROE, tăng trưởng LNST dự phóng, tỷ suất cổ tức, sàn và vốn hóa. So sánh doanh nghiệp dùng danh sách mã từ trang này làm peer universe, sau đó tự tải dữ liệu/định giá theo pipeline đã chọn trong app.
