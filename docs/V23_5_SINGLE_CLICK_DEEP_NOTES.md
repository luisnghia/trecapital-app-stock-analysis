# V23.5 - Single-click Deep Notes

## Mục tiêu cập nhật

1. Nhấp một lần vào từng chỉ tiêu/phương pháp để xem note giải thích.
2. Note không còn dùng nguyên tắc chung cho mọi mã. Nội dung note lấy từ chính BCTC đã chuẩn hóa của mã đang phân tích: ROIC, ROE, CFO/LNST, FCF/LNST, biên gộp, CCC, vòng quay tồn kho, nợ/EBITDA, tăng trưởng doanh thu/OE, giá hiện tại, số cổ phiếu và các giả định định giá.
3. Tích hợp nguyên tắc từ tài liệu nguồn theo từng trường hợp doanh nghiệp:
   - Graham/Dodd: earning power, asset value, margin of safety.
   - Buffett: Owner Earnings và chất lượng dòng tiền.
   - Li Lu: hiểu bear case, ROIC/deployed capital, downside protection.
   - Howard Marks: dải kết quả, rủi ro, không phụ thuộc một dự báo duy nhất.
   - Michael Porter: lợi thế cạnh tranh phải truy về hoạt động trong chuỗi giá trị, không kết luận chung chung.

## Cách hoạt động

- Khi bảng được render, app sinh note cho từng dòng dựa trên `phần2_note_context` gồm: company, annual_df, quarterly_df, valuation_df, value_range, moat_df, classification và assumptions.
- Người dùng chỉ cần click một lần vào dòng/chỉ tiêu; note hiện ngay dưới bảng.
- Mỗi phương pháp định giá có công thức riêng:
  - Earnings Power: EPS chuẩn hóa x P/E mục tiêu theo loại doanh nghiệp.
  - Owner Earnings: OEPS x (1+g)/(r-g), trong đó g lấy từ OE CAGR hoặc doanh thu CAGR và bị chặn trần.
  - FCF Capitalization: FCF/cp / suất vốn hóa bảo thủ.
  - P/B: BVPS x P/B mục tiêu, ưu tiên với tài chính/asset play.
  - NLA/NCAV: tiền + ĐT ngắn hạn + phải thu sau haircut + tồn kho sau haircut - nợ phải trả.
- Moat/Porter note dùng dữ liệu cụ thể: ROIC/ROE, biên gộp, biên EBIT, CCC, SG&A/DT, CFO/LNST, FCF/LNST, CAGR doanh thu/OE.

## Lưu ý kiểm toán

Note giải thích là lớp phân tích tự động, không thay thế việc đọc BCTC/BCTN gốc. Khi dữ liệu thiếu, app ghi rõ thiếu dữ liệu thay vì kết luận moat/định giá chắc chắn.
