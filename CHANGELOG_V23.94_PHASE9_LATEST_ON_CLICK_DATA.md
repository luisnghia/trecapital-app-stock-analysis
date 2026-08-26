# V23.94 — Phase 9 Latest-on-click data

- Thêm Source Registry có kiểm soát cho đủ 26 Fisher Portfolio Drivers.
- Chỉ gọi nguồn khi analyst bấm `Cập nhật dữ liệu mới nhất`; không polling, cron, realtime hoặc tải nền khi đổi trang.
- Tích hợp IMF DataMapper và World Bank WDI không cần API key; FRED/EIA là nguồn tùy chọn khi server có key.
- Nguồn chưa có API ổn định được giữ là Research gap, không suy đoán hoặc tự chấm điểm.
- Lưu append-only Update Run, observation, suggestion và analyst decision; URL audit không chứa API key/query secret.
- Analyst phải accept/reject kèm lý do và xác nhận trước khi điểm driver được áp dụng vào phiên Fisher Top-down.
- Phase 9 không ghi `analyst_assessments`, không sửa Q01–Q59 và không tạo lệnh mua/bán.
- Immutable review snapshot và review deletion workflow đã bao phủ toàn bộ dữ liệu Phase 9.
- Bốn bảng PostgreSQL mới bật RLS, thu hồi quyền `anon/authenticated`, có khóa ngoại và index phục vụ review/run lookup.
