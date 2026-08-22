# V23.86 — Management & Human Intelligence (Phase 5)

## Phạm vi

- Thêm khu vực top-level `👥 Management & Human Intel` cho Q33–Q52 và Q58–Q59.
- Table 7.1 Lion/Hyena trở thành Management Character Matrix có subject, trạng thái, signal -2..+2, confidence, materiality, rationale và exact evidence.
- Table 8.1 trở thành Management Tenure Timeline cho tối đa 5 lãnh đạo chủ chốt, khuyến nghị lịch sử tối thiểu 5–10 năm.
- Hồ sơ manager theo version: founder/internal/external, chức danh, nhiệm kỳ, sở hữu, lương thưởng, xác minh và evidence.
- Track record có cấu trúc cho compensation/ownership, insider transaction, guidance, capital allocation, buyback, M&A, integrity và communication.
- Human Intelligence phân loại nguồn: customer, competitor, supplier, employee, industry insider, academic, headhunter, regulator; lưu credibility, corroboration và cờ confidential.
- Guidance và M&A có hậu kiểm `current/1y/3y/5y`, expected outcome, actual outcome và trạng thái tạo/hủy giá trị.

## Guardrail

- Structured management signal chỉ là evidence cho analyst; không gọi `save_assessment` và không tự ghi final Q01–Q59 assessment.
- Research gap/not reviewed không được gán signal score; Unknown khác Neutral.
- Lion/Hyena không phải nhãn tự động và không được kết luận từ một sự kiện đơn lẻ.
- Completed review khóa toàn bộ ghi mới; dữ liệu Phase 5 được nhúng vào immutable snapshot `phase1b-review-v5-evidence-peer-ai-management`.
- Dữ liệu append-only/versioned; thay đổi score hoặc hồ sơ manager bắt buộc có lý do.
- Review deletion xóa đúng dữ liệu Phase 5 thuộc review nhưng giữ research evidence và audit tombstone.

## Database

- Thêm `management_people_versions`.
- Thêm `management_timeline_events`.
- Thêm `management_track_records`.
- Thêm `management_question_signals`.
- Bổ sung covering index cho toàn bộ FK review/company/evidence/supersedes/question; PostgreSQL/Supabase bật RLS và thu hồi toàn bộ quyền `anon`/`authenticated` vì app dùng trusted direct connection.
- Migration SQLite → PostgreSQL giữ đủ bốn bảng Phase 5 và reset đúng sequence.

## Kiểm thử local

- Phase 5 targeted: **5 passed, 1 skipped** (PostgreSQL secret không có ở local).
- Toàn bộ Investment Checklist: **155 passed, 11 skipped**.
- Bao phủ versioning, evidence scope, signal guardrail, mapping câu hỏi, immutable snapshot, completed-review lock, review deletion, Streamlit UI smoke và no-network/no-auto-assessment contract.
