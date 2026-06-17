# V23.10 – Đồng bộ MOS, kiểm tra công thức và nâng giao diện tab

## Thay đổi chính

1. Bổ sung mức MOS 0% và 10% vào danh sách chọn MOS yêu cầu.
2. Chuẩn hóa MOS thành một khóa dữ liệu dùng chung `st.session_state["target_mos_pct"]` cho toàn app. Chọn MOS ở Tổng quan doanh nghiệp hoặc Định giá chuyên sâu sẽ tự đồng bộ qua phần còn lại.
3. Sửa lỗi công thức khi MOS = 0%: các hàm không còn dùng biểu thức `or 30/50` khiến 0% bị hiểu thành mặc định.
4. Các nhận xét nhanh, đánh giá, kết luận và nhận xét quan trọng được đưa vào khung chữ đỏ, lớn hơn để dễ quan sát.
5. Thanh tab được thiết kế to hơn, bo tròn, có màu nền và trạng thái active nổi bật theo màu Trecapital.

## Công thức MOS kiểm tra

- Giá mua theo MOS chọn = Giá trị nội tại × (1 - MOS chọn / 100).
- MOS hiện tại = (Giá trị nội tại - Giá hiện tại) / Giá trị nội tại × 100.
- Khi MOS chọn thay đổi, các cột `Giá MOS chọn`, `Giá mua theo MOS chọn`, kết luận đủ/chưa đủ MOS và note giải thích đều lấy theo cùng `target_mos_pct`.

## Nguyên tắc đồng bộ dữ liệu

Tất cả phần dùng chung mã cổ phiếu, nguồn dữ liệu, cache tài chính và MOS yêu cầu để bảo đảm thống nhất dữ liệu tuyệt đối giữa Tổng quan doanh nghiệp và Định giá chuyên sâu.


## Bổ sung kiểm soát ROIC & WACC

- Tab `ROIC & đầu tư` chỉ giữ đường `ROIC Operating Profit` và `WACC`.
- Các đường ROIC Owner Earnings, ROIC NOPAT/Capital Employed, ROIC FireAnt không còn nằm trong biểu đồ để tránh rối và để tập trung vào hiệu quả vốn hoạt động cốt lõi.
- Từ V23.14, app không dùng WACC tham chiếu sidebar; WACC được tự tính theo từng doanh nghiệp.

## Kiểm tra đồng bộ toàn app

- Khóa MOS dùng chung: `st.session_state["target_mos_pct"]`.
- Khóa mã cổ phiếu/cache dùng chung: `last_query_ticker`, `active_ticker`, `phần2_ticker`, `active_*_csv`.
- Không còn khóa WACC nhập tay; WACC là cột dữ liệu/tính toán `wacc_pct`.
