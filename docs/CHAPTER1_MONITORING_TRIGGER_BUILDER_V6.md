# Chapter 1 — Monitoring Trigger Builder V6

## Mục đích

V6 chuẩn hóa cách analyst tạo Monitoring Trigger cho Opportunity Inventory. Đây là lớp triển khai của Trecapital, không phải bảng/tiêu chí gốc trong *The Investment Checklist*.

Nguyên tắc bất biến:

- Trigger chỉ tạo **Review Queue**.
- Trigger không tự đổi Research Gate.
- Trigger không tạo BUY/HOLD/SELL.
- Các field phụ thuộc giá thị trường chỉ được đánh giá khi quote đủ mới theo guardrail hiện tại.
- Event/CBTT chỉ là candidate cần analyst xác minh.

## Structured Trigger Builder

Các nhóm trigger có thể chọn trực tiếp trên UI:

1. Chỉ tiêu định lượng.
2. Có BCTC mới.
3. BCTC kỳ cụ thể.
4. Có Event / CBTT mới.
5. Thủ công nâng cao để tương thích trigger legacy.

### Chỉ tiêu định lượng hỗ trợ

- Giá hiện tại.
- MOS.
- ROIC.
- Debt/EBITDA.
- EBIT/Interest.
- FCF Yield.
- Valuation Percentile.
- 52W Drawdown.

Operator hỗ trợ: `<`, `<=`, `>`, `>=`, `=`.

Ví dụ canonical string do builder sinh:

- `Review khi Giá < 80.000`
- `Review khi MOS > 25%`
- `Review khi ROIC < 15%`
- `Review khi Debt/EBITDA > 2x`

## BCTC mới

`Review khi có BCTC mới` dùng baseline. Lần kiểm tra đầu tiên lưu kỳ canonical hiện tại. Review Queue chỉ được tạo khi `as_of` thay đổi sang kỳ mới.

## BCTC kỳ cụ thể

Builder sinh chuỗi dạng:

`Review khi có BCTC Q3/2026`

Parser chuyển về canonical target period:

`2026-Q3`

Quy tắc đánh giá:

- Current canonical period < target period → `armed`.
- Current canonical period >= target period → `triggered`.
- Review item chỉ được tạo tại transition `false → true`, vì vậy không lặp cảnh báo ở mỗi lần refresh.

Period rank dùng để so sánh:

`rank = year * 4 + quarter`

Ví dụ:

- Q2/2026 = `2026*4 + 2`
- Q3/2026 = `2026*4 + 3`

Do đó Q2/2026 chưa đạt Q3/2026, còn Q3/2026 hoặc Q4/2026 đều đạt mốc.

## Event / CBTT mới

Lần đầu engine lưu signature của các event candidate hiện có. Chỉ candidate mới xuất hiện sau baseline mới tạo Review Queue.

Signature được tạo từ:

`category | title | url`

và băm SHA-1 rút gọn để so sánh ổn định.

## Persistence

V6 tiếp tục dùng SQLite local:

`data_cache/deep_company_analysis_chapter1.db`

Các bảng monitoring:

- `chapter1_trigger_state`
- `chapter1_review_queue`

Trigger cấu hình vẫn được lưu bằng text human-readable trong `chapter1_monitoring_triggers` để giữ tương thích ngược với V5.

## Acceptance tests V6

- Structured numeric trigger round-trip qua parser.
- Trigger Giá/MOS/ROIC/Debt-EBITDA/Valuation Percentile giữ đúng metric/operator/threshold.
- `Review khi có BCTC Q3/2026` parse thành `statement_period`, target `2026-Q3`.
- Q2/2026 không trigger.
- Q3/2026 trigger.
- Q4/2026 vẫn coi là đã đạt mốc nhưng dedup transition ngăn cảnh báo lặp.
- Generic `Review khi có BCTC mới` vẫn tương thích V5.
