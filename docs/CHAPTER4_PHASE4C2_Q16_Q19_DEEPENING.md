# Chapter 4 Phase 4C.2 — Q16 Pricing Power + Q19 Competitor Intelligence

## Mục tiêu

Phase 4C.1 đã nâng chất lượng evidence nhưng DGC vẫn còn hai research gaps quan trọng:

- **Q16 Pricing Power**: thiếu evidence đủ mạnh về thay đổi giá đi cùng phản ứng volume/customer/retention/thị phần.
- **Q19 Competitive Landscape**: evidence còn mỏng so với 8 nhóm logic mà Michael Shearn yêu cầu xem xét.

Phase 4C.2 đào sâu đúng hai khoảng trống này, nhưng vẫn giữ nguyên nguyên tắc của Trecapital:

> AI/Data = Research Assistant; User = Investment Analyst.

Không có auto moat, auto Pricing Power, auto Competition Intensity, auto Ideal Company, auto Research Gate hay BUY/HOLD/SELL.

## Q16 — Pricing Power Evidence Engine

Engine tìm evidence theo thứ tự:

1. HTML/IR chính thức đã đăng ký trong Trecapital.
2. BCTN/PDF chính thức đã đăng ký.
3. Targeted web search cho giá bán, ASP, sản lượng, khách hàng, retention, demand và market share.

### Quy tắc evidence

- **Price + customer/volume response** → explicit candidate, vẫn cần analyst xác minh.
- **Price only** → insufficient for Pricing Power.
- **Price + commodity/input-cost context** → commodity/cost-pass-through candidate, không được gọi Pricing Power.
- Margin tăng một mình không phải pricing evidence.
- Query text không được dùng để tự tạo match; classifier chỉ đọc title/snippet/evidence text thật.

### Event Type Candidate

- Price + customer/volume response candidate — analyst verify.
- Commodity / Cost-pass-through candidate — not Pricing Power conclusion.
- Price + reaction with commodity/cost context — analyst separate pass-through from Pricing Power.
- Price-only candidate — insufficient.

## Q19 — Competitor Intelligence Engine

### Same-industry candidate universe

Engine tái sử dụng danh sách cùng ngành từ Simplize/Trecapital. Đây chỉ là **candidate context**:

- peer cùng ngành không tự động là direct competitor;
- analyst phải xác nhận segment/geography/customer overlap;
- app không tự chọn Industry Standard hay Ideal Company.

### Deep search theo 8 nhóm logic Q19

Classifier gom evidence vào các nhóm:

1. Limited / Direct Competition
2. Industry Change / Capacity Competition
3. How Competitors Compete
4. Fierceness / Price Competition
5. Substitute Products
6. Low-cost Country Competition
7. Industry Standard / Market Position
8. Why Competitors Failed

Các query bổ sung tập trung vào:

- target + top same-industry peers;
- market share/capacity/price competition;
- substitutes/import/China/foreign low-cost threat;
- failures/exits/loss-making competitors.

Query text không được dùng để phân loại evidence. Nếu title/snippet không chứa competition evidence thật thì kết quả bị loại.

## Persistence

Phase 4C.2 chỉ append candidate rows vào `evidence_matrix` với:

- `Status = Candidate — Analyst verify`
- `Data Origin = Chapter 4 Research Assistant Evidence Bridge Phase 4C.2`

Các trường analyst như Assessment, Trend, Confidence, Conclusion và các bảng structured Q16/Q19 không bị ghi đè.

## UI

Khối mới trong tab Chương 4:

**Phase 4C.2 — Q16 Pricing Power + Q19 Competitor Intelligence**

Nút:

**🎯 Đào sâu Q16 + Q19**

UI hiển thị:

- Phase 4C.2 Gap Audit;
- Q16 pricing evidence;
- same-industry competitor candidate universe;
- Q19 competitor-intelligence evidence;
- cảnh báo nếu Q16 chưa có explicit price+reaction;
- coverage số nhóm Q19 có evidence.

## Guardrails bắt buộc

- Price-only ≠ Pricing Power.
- Margin-only ≠ Pricing Power.
- Commodity/shortage price ≠ sustainable Pricing Power.
- Same-industry peer ≠ direct competitor.
- Search query terms ≠ evidence.
- Competitor failure mention ≠ verified root cause.
- Không auto Competition Intensity.
- Không auto Ideal Company.
- Không đổi Research Gate.

## Acceptance

Phase 4C.2 phải PASS:

- unit tests cho price-only, price+volume, commodity context;
- query-only false-positive tests;
- Q19 subtopic classifier tests;
- peer universe exclusion/sorting test;
- persistence no-overwrite test;
- full Deep Analysis regression;
- live DGC diagnostic;
- unified Streamlit smoke test;
- Windows offline package build.
