# Hướng dẫn sử dụng KHDN Ops V2.23

> Hướng dẫn tích hợp trong app. Bản Word V2.22 chi tiết 16 trang được đính kèm trong gói cài đặt local.

## 1. Workflow tổng thể

**QLKH tạo/giao hồ sơ → CBHT tiếp nhận → CBHT xử lý → CBHT báo hoàn thành → QLKH đánh giá → kết thúc.**

- CBHT có thể **trả lại QLKH** trước khi hoàn thành. QLKH có thể giao lại, đổi CBHT hoặc hủy; các mốc gốc vẫn được giữ để không reset thời gian.
- Lãnh đạo có thể **yêu cầu làm lại** trên chính hồ sơ cũ; hệ thống mở vòng xử lý mới và giữ lịch sử vòng trước.
- Các thao tác hủy/xóa là soft-cancel, không xóa vật lý dấu vết tác nghiệp.

## 2. Vai trò

### Cán bộ hỗ trợ (CBHT)
- Tiếp nhận hồ sơ QLKH giao.
- Tự tạo tác nghiệp khi cần.
- Xử lý, báo hoàn thành, trả lại QLKH.
- Xem lịch sử và Dashboard cá nhân; so sánh benchmark CBHT toàn phòng.

### Cán bộ QLKH
- Tạo/giao hồ sơ cho CBHT.
- Đổi CBHT/hủy theo điều kiện; xử lý hồ sơ CBHT trả lại.
- Đánh giá Chất lượng và Tiến độ theo thang 0–10, bước 0,5; nếu dưới 9 phải nhập góp ý.
- Xem lịch sử và Dashboard phạm vi hồ sơ mình phụ trách.

### Lãnh đạo phòng
- Theo dõi toàn phòng, hồ sơ đang/chờ xử lý, heatmap trễ.
- Lọc lịch sử theo ngày/cán bộ/công việc.
- Yêu cầu thực hiện lại; không chấm điểm thay QLKH.

### Admin
- Quản lý user, username, reset mật khẩu, khóa/xóa mềm user.
- Nạp danh mục CIF/Tên khách hàng/QLKH.
- Quản lý loại công việc, audit, backup/archive.

## 3. Các mốc thời gian

- `assigned_at`: QLKH giao hồ sơ.
- `first_accepted_at`: CBHT tiếp nhận lần đầu, không reset khi giao lại.
- `accepted_at`: lần tiếp nhận gần nhất.
- `start_time`: bắt đầu xử lý.
- `end_time`: CBHT báo hoàn thành.
- `evaluated_at`: QLKH đánh giá.
- `closed_time`: hồ sơ kết thúc.
- `returned_to_qlkh_at`: CBHT trả hồ sơ.
- `last_rework_at`: Lãnh đạo yêu cầu làm lại.

Thời gian xử lý được tính theo phút. Thời gian hiển thị theo `hh:mm dd/mm/yyyy`.

## 4. Hướng dẫn CBHT

### Hồ sơ chờ tiếp nhận
1. Mở **Tác nghiệp → Hồ sơ chờ tiếp nhận**.
2. Danh sách ưu tiên hồ sơ cũ trước, có mức độ trễ/heatmap.
3. Chọn trực tiếp một dòng.
4. Bấm **Tiếp nhận hồ sơ** để bắt đầu xử lý hoặc **Trả lại QLKH** nếu không phù hợp.

### Tự tạo tác nghiệp
1. Gõ CIF hoặc một phần tên khách hàng; chọn kết quả đúng.
2. QLKH được lấy mặc định từ danh mục nhưng có thể điều chỉnh riêng cho lần tác nghiệp.
3. Chọn công việc, đơn vị VND/USD/EUR, nhập giá trị; Ghi chú không bắt buộc.
4. Tạo tác nghiệp. Hồ sơ do CBHT tự tạo được xem là đã tiếp nhận ngay.

### Hồ sơ đang xử lý
- Chọn trực tiếp dòng hồ sơ.
- Khi xong, bấm **Hoàn thành xử lý – chuyển QLKH đánh giá**; app tự ghi thời điểm kết thúc và thời gian xử lý.
- Ghi chú có thể sửa khi hồ sơ còn chờ đánh giá; sau đánh giá bị khóa.
- Có thể trả lại QLKH nếu chưa hoàn thành.

## 5. Hướng dẫn QLKH

### Tạo/giao hồ sơ
1. Tìm CIF/Tên khách hàng.
2. Chọn CBHT, công việc, giá trị, đơn vị, ghi chú.
3. Bấm **Giao hồ sơ**; app giữ nguyên trang để nhập món tiếp theo.
4. Hồ sơ xuất hiện bên CBHT qua auto-refresh.

### Hồ sơ chưa tiếp nhận / CBHT trả lại
- Chưa tiếp nhận: có thể đổi CBHT hoặc hủy/xóa.
- CBHT trả lại: có thể giao lại CBHT cũ, đổi CBHT khác hoặc hủy/xóa.
- Đổi người/hủy không reset `assigned_at`; `first_accepted_at` đã phát sinh cũng được giữ.

### Đánh giá
1. Mở **Chờ tôi đánh giá**.
2. Chọn trực tiếp dòng hồ sơ đã hoàn thành.
3. Chấm Chất lượng và Tiến độ, mặc định 5,0.
4. Nếu một tiêu chí dưới 9, bắt buộc nhập góp ý.
5. Lưu đánh giá để kết thúc hồ sơ.

## 6. Lãnh đạo và Admin

- Danh sách đang/chờ xử lý chỉ hiển thị hồ sơ chưa kết thúc, món cũ trước.
- Hồ sơ CBHT trả lại QLKH được tách riêng.
- **Lịch sử & yêu cầu làm lại** có bộ lọc Ngày/Khoảng ngày, Cán bộ, Công việc; chọn trực tiếp dòng hồ sơ.
- Yêu cầu làm lại mở vòng xử lý mới trên hồ sơ cũ và giữ đầy đủ lịch sử/điểm vòng trước.

## 7. Dashboard và mục tiêu hiệu suất

Dashboard nhận xét riêng từng tiêu chí, **không dùng điểm tổng hợp 60/25/15**:
- Thời gian xử lý: giảm là cải thiện.
- Chất lượng: tăng là cải thiện.
- Điểm trung bình: tăng là cải thiện.
- Mỗi nhận xét nêu số hiện tại, số kỳ chuẩn, chênh lệch và % tăng/giảm; cải thiện màu xanh, giảm sút màu đỏ.

### Mục tiêu tuần/tháng
- Tuần calendar: Thứ Hai → Chủ Nhật; chỉ tính các ngày thực tế có hồ sơ hoàn thành.
- Mục tiêu là kỳ gần nhất trước đó có dữ liệu của cùng loại công việc.
- Tháng áp dụng tương tự. Chưa có kỳ lịch sử thì hiển thị **Chưa đủ dữ liệu**.

### Chuẩn dài hạn tối đa 5 năm
Không bắt buộc đủ 5 năm. Mỗi chỉ tiêu chọn chuẩn riêng trong tối đa 5 năm đã có:
- Thời gian: năm có thời gian thấp nhất.
- Chất lượng: năm có điểm chất lượng cao nhất.
- Điểm trung bình: năm có điểm trung bình cao nhất.

## 8. Giá trị và tỷ giá BIDV

- Đơn vị: VND, USD, EUR.
- USD/EUR dùng tỷ giá **mua chuyển khoản BIDV** lấy bằng direct HTTP từ backend công khai của trang BIDV, không dùng Selenium/ChromeDriver.
- App tự cập nhật khi đăng nhập; có nút cập nhật lại ở sidebar.
- Mỗi tác nghiệp ngoại tệ giữ tỷ giá tại thời điểm tạo.
- KPI giá trị Dashboard chỉ tính Giải ngân, Bảo lãnh, L/C; nghiệp vụ khác mặc định giá trị 0 trong thống kê giá trị.

## 9. Lịch sử, audit và truy vết

- Lịch sử xử lý: thời điểm, người thực hiện, hành động, chi tiết.
- Lịch sử đánh giá: vòng, người đánh giá, Chất lượng, Tiến độ, Góp ý, thời gian.
- Chọn trực tiếp dòng bảng lịch sử để xem hồ sơ.
- Audit lưu các thao tác giao, tiếp nhận, trả lại, đổi CBHT, hủy, hoàn thành, đánh giá, làm lại.

## 10. Tài khoản, avatar và mật khẩu

- Cán bộ có thể upload avatar PNG/JPG/WEBP tối đa 2 MB; ảnh hiển thị cạnh tên ở sidebar.
- Đổi mật khẩu trong **Tài khoản**; tối thiểu 8 ký tự gồm chữ và số.
- User quên mật khẩu: liên hệ Admin reset.
- Admin quên mật khẩu: dùng chức năng khôi phục Admin; bản local có `RESET_ADMIN_PASSWORD.bat` làm phương án cứu hộ.

## 11. Backup, archive và báo cáo

- Cuối năm app tự archive năm đã kết thúc: file thống kê, file chi tiết mỗi năm và snapshot DB.
- Admin có thể tải backup/archive trong Quản trị.
- Báo cáo Excel theo phạm vi/bộ lọc, gồm chi tiết và các lớp tổng hợp theo cán bộ, công việc, tuần, tháng tùy quyền.

## 12. Auto-refresh và cảnh báo

- Mặc định mỗi 6 giây kiểm tra fingerprint dữ liệu liên quan user; chỉ rerun khi có thay đổi.
- Ô trạng thái có hồ sơ cần xử lý đổi màu/nhấp nháy và có thể bấm để chuyển nhanh đến đúng nghiệp vụ.

## 13. Checklist hằng ngày

**CBHT:** kiểm tra hồ sơ chờ tiếp nhận/đang xử lý → xử lý món cũ trước → báo hoàn thành ngay khi xong → theo dõi Dashboard cá nhân.

**QLKH:** theo dõi hồ sơ giao chưa tiếp nhận và hồ sơ trả lại → đánh giá sớm → dùng đúng chức năng đổi/hủy để giữ audit.

**Lãnh đạo/Admin:** kiểm tra heatmap trễ, hồ sơ trả lại/đổi/hủy → yêu cầu làm lại trên hồ sơ cũ → kiểm tra Dashboard, backup, archive và audit.

## 14. Xử lý sự cố nhanh

- Không lấy tỷ giá: bấm **Cập nhật tỷ giá BIDV**, kiểm tra mạng/proxy.
- Không tìm khách hàng: kiểm tra CIF/Tên KH đã được Admin nạp và đang Active.
- Không đánh giá được: hồ sơ phải ở Chờ QLKH đánh giá; điểm <9 phải có Góp ý.
- Không sửa được ghi chú: sau đánh giá hồ sơ đã khóa, chỉ mở lại khi Lãnh đạo yêu cầu làm lại.
- Cần kiểm tra lỗi: gửi `logs/khdn_ops.log` và ảnh màn hình cho người phụ trách kỹ thuật.
