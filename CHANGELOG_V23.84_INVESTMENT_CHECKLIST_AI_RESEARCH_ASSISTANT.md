# V23.84 — Governed AI Research Assistant (Phase 4A)

- Thêm top-level `🤖 AI Research Assistant` với AI run audit và analyst approval queue.
- AI output được lưu append-only cùng provider/model/prompt version, source manifest và SHA-256 của prompt/input/output.
- Evidence/contradiction suggestion bắt buộc có source, source hash, locator, excerpt và mapping Q01–Q59.
- Research gap không được gắn nguồn giả hoặc tự tạo assessment.
- Analyst phải accept/reject và ghi lý do; không được sửa quyết định đã lưu.
- Accept evidence tạo Evidence Workspace record ở trạng thái `unverified` và evidence link trong cùng transaction.
- Citation drift, source archived, completed review và quyết định lặp đều bị khóa.
- Immutable review snapshot nhúng toàn bộ AI runs, suggestions và analyst decisions.
- Review deletion dọn AI workflow theo đúng FK order nhưng giữ promoted evidence như evidence thủ công.
- PostgreSQL/Supabase bật RLS và thu hồi quyền `anon`/`authenticated` trên ba bảng AI nội bộ.
- Security Advisor follow-up bật cùng guardrail cho ba bảng Evidence Workspace cũ và bổ sung index bao phủ các FK Phase 4A.
- Phase 4A chưa tự gọi model/network; JSON model output được ingest có kiểm soát. Provider execution là Phase 4B.

## Validation

- Full Investment Checklist regression: 140 passed, 10 skipped ở local.
- Phase 4A + Evidence + Peer regression: 14 passed, 2 skipped ở local.
- Skips dành cho PostgreSQL CI có `TEST_DATABASE_URL`.
