# Investment Checklist Phase 3B — Peer Snapshot & Ranking

## Mục tiêu

Phase 3B nối trang **So sánh doanh nghiệp** hiện có với một review cụ thể của Investment Checklist
mà không làm chậm Fast Entry và không tự ghi kết luận thay analyst.

Luồng vận hành:

1. Analyst mở trang So sánh doanh nghiệp và chạy tối đa 10 mã cùng ngành.
2. Kết quả tạm nằm trong Streamlit session state; việc đổi Q01–Q59 không tải peer lại.
3. Analyst quay về `Industry & Moat`, kiểm tra bảng, nhập lý do và bấm lưu.
4. App tạo một phiên bản append-only trong `peer_comparison_snapshots` gắn với đúng company/review.
5. Khi finalize review, phiên bản peer mới nhất và SHA-256 của payload được nhúng vào immutable snapshot.

## Guardrails

- Tối thiểu mã gốc + 1 peer; tối đa 10 doanh nghiệp.
- Mã gốc bắt buộc phải có trong kết quả.
- Xếp hạng xác định theo `Điểm tổng hợp → MOS → Moat score → ticker`.
- Không thay dữ liệu thiếu bằng 0 và không tính lại BCTC ở service lưu snapshot.
- Không network, AI hoặc `save_assessment()` trong engine/UI Phase 3B.
- Review `completed` là read-only; muốn cập nhật phải tạo review mới.
- Xóa review thủ công sẽ đếm và xóa peer snapshot thuộc review đó, đồng thời giữ audit tombstone.
- Peer Snapshot chỉ hỗ trợ evidence định lượng cho Q19, Q22, Q24, Q26 và Q32; analyst tự kết luận.

## PostgreSQL/Supabase

Migration production:

`20260822080738_investment_checklist_phase3b_peer_snapshots`

Table `public.peer_comparison_snapshots` bật RLS và thu hồi quyền `anon`/`authenticated`. App truy cập
bằng kết nối PostgreSQL server-side; Data API không được mở cho bảng nghiên cứu nội bộ này.

## Acceptance tests

- Version append-only + audit.
- Ranking/tie-break xác định.
- Reject sai mã gốc, thiếu điểm, <2 hoặc >10 doanh nghiệp.
- Lock sau finalize.
- Immutable snapshot giữ đúng payload/hash/version.
- Review deletion dọn peer snapshot đúng phạm vi.
- SQLite, PostgreSQL migration và Streamlit smoke.

