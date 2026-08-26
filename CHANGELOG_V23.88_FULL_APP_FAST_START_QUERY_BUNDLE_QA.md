# V23.88 — Full-app fast start, query bundling & QA

## Mục tiêu

- Giảm tối thiểu 50% thời gian chờ khi mở/chuyển trang hoặc đổi khu vực Checklist.
- Không đánh đổi tính mới của dữ liệu: quote cache quá hạn bị khóa, crawler live chỉ chạy khi analyst chủ động cập nhật.
- Rà toàn bộ 5 trang chính và 10 khu vực Checklist sau V23.87.

## Thay đổi hiệu năng

1. **Network-free first paint**
   - Tổng quan không còn tự gọi FireAnt/Vietstock ở lần render đầu sau reboot.
   - Định giá/So sánh/Báo cáo ưu tiên bundle đang hoạt động → cache chuẩn hóa → sample/Financial fast start.
   - Investment Checklist ưu tiên session bundle → process cache → normalized sample khởi động nhanh → BCTC tích hợp; crawler chỉ chạy sau nút cập nhật.
   - Cache provider quá 6 giờ vẫn dùng được cho BCTC nhưng quote bị coi là stale và bị loại khỏi assessment.

2. **Supabase query bundling**
   - Research Home: từ nhiều lượt đọc riêng lẻ còn 2 SELECT trên một pooled connection.
   - Research Evidence Coverage: từ 5 lượt đọc/xuất còn 1 query link; coverage, summary và JSON được dựng từ cùng immutable bundle.
   - Phase 5 Management: 4 bảng đọc qua một pooled connection và tái sử dụng trong sub-view; session hot-cache 30 giây.
   - Preview xóa review chỉ tải khi analyst bấm yêu cầu, không còn chạy hàng loạt COUNT trên mọi fragment rerun.

3. **Cold-process optimization**
   - Dùng normalized sample cho shell khởi động nhanh, có nhãn rõ và nút cập nhật live.
   - Cố định `MPLCONFIGDIR` writable để không rebuild font cache sau mỗi process restart.

## Benchmark & QA

- V23.87 live baseline Investment Checklist: **23.384 giây**.
- V23.87 live baseline chuyển sang Management: **7.172 giây**.
- V23.88 multipage smoke trong cùng session (local):
  - Tổng quan cold-start: **7.588 giây**.
  - Định giá chuyên sâu: **2.399 giây**.
  - So sánh doanh nghiệp: **0.103 giây**.
  - Báo cáo tổng hợp: **2.247 giây**.
  - Investment Checklist: **0.154 giây**.
- 5/5 trang: 0 exception, 0 Streamlit error trong multipage smoke.
- Query-budget regression: Phase 5 giảm 5 → 1 connection checkout; Evidence default giảm 5 → 1 read (80%).
- Full automated suite trước CI: 162 passed, 11 skipped; PostgreSQL cases do CI PostgreSQL 16 xác nhận.
- Parser gate FireAnt cũ được chuyển sang fixture đúng contract endpoint V14; full-repository collection không còn dừng ở top-level assertion legacy.

## Guardrails

- Không dùng cache stale để giả làm giá hiện tại.
- Không tự ghi assessment, evidence hoặc review.
- Cập nhật live vẫn dùng pipeline Trecapital canonical và cùng global ticker.
- Completed review, snapshot và audit trail giữ nguyên tính bất biến.
