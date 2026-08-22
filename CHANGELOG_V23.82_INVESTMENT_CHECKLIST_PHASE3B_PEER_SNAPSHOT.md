# V23.82 — Investment Checklist Phase 3B Peer Snapshot & Ranking

- Gắn kết quả từ trang So sánh doanh nghiệp vào đúng review của Investment Checklist.
- Chỉ lưu khi analyst xác nhận và nhập lý do; không tự ghi assessment Q01–Q59.
- Append-only version, SHA-256 payload, audit trail và lịch sử phiên bản.
- Khóa ghi khi review đã finalize; peer payload được nhúng vào immutable snapshot.
- Review deletion đếm/xóa peer snapshot cùng phạm vi và giữ tombstone.
- Không gọi network/AI khi đổi Question; giới hạn 2–10 doanh nghiệp.
- Mapping evidence định lượng: Q19, Q22, Q24, Q26, Q32.
- Thêm schema SQLite/PostgreSQL và migration Supabase production.

## QA checkpoint

- Local Checklist regression: 132 passed, 9 skipped trước khi chạy CI PostgreSQL.
- Production Supabase: PostgreSQL 17.6 ACTIVE_HEALTHY; migration Phase 3B applied.
- Two-connection database probe: PASS.
- Public Streamlit URL vẫn chạy `main` cũ, chưa phải V23.81/V23.82; không dùng làm bằng chứng nghiệm thu branch.

