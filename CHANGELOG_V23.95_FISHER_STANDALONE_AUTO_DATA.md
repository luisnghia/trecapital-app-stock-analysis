# V23.95 — Fisher Top-Down độc lập và dữ liệu tự động

## Phạm vi

- Bước 5 nhận danh sách mã và chỉ gọi nguồn sau khi analyst bấm `Lấy dữ liệu & sàng lọc`.
- Tái sử dụng public crawler và cache chuẩn hóa của Trecapital; không tạo nguồn dữ liệu doanh nghiệp thứ hai.
- Tự lấy/tính vốn hóa, P/E, P/B, P/S, P/CF từ CFO TTM, nợ vay/vốn chủ và GTGD bình quân 20 phiên.
- Thiếu bất kỳ chỉ tiêu bắt buộc nào sẽ trả `Thiếu dữ liệu`, không được tính là `Đạt`.
- `Portfolio Drivers` có nút cập nhật vĩ mô mới nhất; không polling/cron và không tự sửa điểm driver.
- IMF DataMapper lỗi có fallback sang series World Bank WDI chính thức cho GDP, CPI, thất nghiệp và chi tiêu chính phủ.
- Tab `Snapshot vĩ mô` lưu lịch sử append-only độc lập, so sánh driver và xếp hạng ngành với phiên bản liền trước.
- Gỡ route `Latest Data Update` khỏi Investment Checklist và gỡ bridge session từ Fisher sang phân tích doanh nghiệp.
- Gỡ tab phân tích cổ phiếu 5 bước khỏi Fisher Top-Down.

## An toàn dữ liệu

- Snapshot không có khóa doanh nghiệp, review hay Q01–Q59.
- PostgreSQL/Supabase bật RLS và thu hồi quyền `anon`/`authenticated`; app dùng kết nối backend trực tiếp.
- SQLite local có trigger chặn UPDATE/DELETE; repository không cung cấp API sửa/xóa snapshot.
- Kết quả cập nhật vĩ mô chỉ là quan sát và suggestion; analyst tự thay đổi slider nếu đồng ý.

## Kiểm thử

- Full regression: `192 passed, 15 skipped`.
- UI smoke Fisher: đạt toàn bộ, không còn session bridge sang module khác.
- Có test riêng cho dữ liệu sàng lọc tự động, missing-data guardrail, IMF→World Bank fallback và snapshot append-only.
