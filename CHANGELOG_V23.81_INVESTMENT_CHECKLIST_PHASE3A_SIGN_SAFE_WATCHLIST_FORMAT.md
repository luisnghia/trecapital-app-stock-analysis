# V23.81 — Phase 3A, Sign-safe Ratios & Watchlist Format

- Sửa lỗi `ABS(Capex)/CFO`: chỉ đánh giá cường độ Capex khi CFO dương. CFO âm/bằng 0 trả N/A, 0 điểm và cảnh báo; không dùng trị tuyệt đối CFO để tạo tín hiệu tốt giả.
- Chuẩn hóa chính sách dấu dùng chung: CFO/LNST, FCF/LNST, OE/LNST chỉ tính khi LNST dương; các tỷ lệ trên LNTT chỉ tính khi LNTT dương; Debt/EBITDA chỉ tính khi EBITDA dương.
- Trường hợp LNST âm được phân loại riêng: lỗ nhưng CFO dương cần kiểm tra recovery/working capital; LNST và CFO cùng âm là cảnh báo, không dùng âm chia âm.
- Áp dụng chính sách trên Module 1 cash-flow/ratio scorecards, cảnh báo, Module 2 Porter/Moat và Accrual/Sloan, cùng Phase 2 quantitative tools.
- Growth trên nền EPS/lợi nhuận âm hoặc bằng 0 được đổi thành nhãn chuyển trạng thái lỗ–lãi, không hiển thị phần trăm tăng trưởng méo; EPS uplift từ buyback chỉ tính trên nền lợi nhuận/EPS dương.
- Watchlist materialize định dạng trước khi đưa vào selectable dataframe để tương thích Streamlit 1.40: tiền/giá 0 số lẻ; ratio 1 số lẻ + `x`; phần trăm 1 số lẻ + `%`; CCC theo ngày; thiếu dữ liệu `—`; âm đỏ, dương xanh; analyst correction vàng hoa mai.
- Thêm Phase 3A `Industry & Moat`: KPI overlay theo normal/cyclical/bank/insurance/securities, operating-driver coverage, Porter/Moat scorecard và Value Chain cho doanh nghiệp phi tài chính, cùng mapping Q15–Q20/Q22–Q26/Q29–Q32/Q55–Q57.
- Doanh nghiệp tài chính khóa score Porter công nghiệp và dùng KPI ngành chuyên biệt; field thiếu giữ `Research gap`, không tự điền 0.
- Phase 3A chỉ đọc Trecapital Data Layer, không gọi network/AI và không tự ghi analyst assessment.
- Regression Checklist: 126 passed, 9 skipped tại local checkpoint; có Streamlit smoke riêng cho Industry Overlay.

Checkpoint trước thay đổi: `df48ee152fe4f60f637030ce1877ea368aac5bd8` (`V23.80`).
