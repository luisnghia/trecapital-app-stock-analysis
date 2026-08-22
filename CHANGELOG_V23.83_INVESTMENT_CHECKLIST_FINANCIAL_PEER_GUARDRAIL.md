# V23.83 — Financial Peer Guardrail & Production QA

- Sửa nhận diện ngân hàng/bảo hiểm/chứng khoán khi nguồn ngành chỉ trả mã số: classifier đọc thêm tên doanh nghiệp.
- Peer tài chính không còn chấm CFO/LNST, FCF/LNST, ROIC, biên gộp, nợ ròng/VCSH hoặc Porter công nghiệp.
- Xếp hạng tài chính tạm thời dùng 60% ROE/tăng trưởng LNST và 40% P/B/P/E/MOS.
- Kết luận bắt buộc nêu research gap NIM, CASA, NPL, LLR, CAR, CIR và credit cost.
- Không gọi Porter scorecard công nghiệp cho doanh nghiệp tài chính.
- Summary không còn gắn moat leader giả khi toàn bộ moat score là N/A.
- Thêm regression cho trường hợp VCB có industry/sub-industry chỉ là mã `1357`.

## QA checkpoint

- Targeted Phase 3B financial guardrail: 8 passed.
- Full Investment Checklist regression: 134 passed, 9 skipped trước CI PostgreSQL.
- Live V23.82 đã tái hiện lỗi VCB/BID/CTG bị phân loại Normal/Cyclical; không lưu snapshot sai vào Supabase.
