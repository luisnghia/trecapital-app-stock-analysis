# V23.91 — Phase 7 Investment Memo & Decision Journal

## Phạm vi

- Investment memo append-only có version, lý do thay đổi và evidence tổng hợp.
- Thesis pillars bắt buộc falsification test; trạng thái supported/mixed/contradicted phải có
  supporting hoặc contradicting evidence tương ứng.
- Risk register có xác suất, tác động, khả năng chống chịu, chỉ báo cảnh báo sớm và liên kết
  tùy chọn tới Monitoring Rule Phase 6.
- Analyst Decision Signature lưu snapshot JSON cùng SHA-256; quyết định là bất biến và niêm
  phong memo/pillar/risk của review.
- Post-decision review tách kết quả đầu tư khỏi chất lượng quy trình để giảm outcome bias.

## Guardrail

- App không tự phát BUY/SELL, không gọi AI/network và không ghi assessment Q01–Q59.
- BUY/ADD/HOLD/TRIM/SELL cần giá thị trường dương và đủ kịch bản `low ≤ base ≤ high`.
- Analyst phải xác nhận research gap và trực tiếp ký trước khi quyết định được ghi.
- Completed review khóa toàn bộ Phase 7; immutable snapshot và manual review deletion đã bao
  phủ năm bảng mới.
- PostgreSQL/Supabase dùng backend-only access: RLS bật và thu hồi toàn bộ quyền
  `anon/authenticated`.

## Kiểm thử

- Versioning, evidence ownership, falsification, valuation/MOS, analyst signature, snapshot hash,
  post-decision review, review lock, manual deletion, Streamlit routing và no-AI/no-assessment
  contract.
