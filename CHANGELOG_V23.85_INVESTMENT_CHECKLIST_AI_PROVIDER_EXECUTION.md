# V23.85 — Governed AI Provider Execution (Phase 4B)

## Kết quả

- Kết nối server-side tới OpenAI Responses API với `store=false` và strict Structured Outputs.
- Chỉ cho phép model trong allowlist; mặc định `gpt-5.6-terra`.
- Thêm quy trình tải PDF/DOCX/TXT/MD/CSV/JSON hoặc dán văn bản, trích xuất text có marker trang/đoạn/dòng và lưu phiên bản append-only.
- Không lưu binary nguồn; mỗi content version có SHA-256, số ký tự, phạm vi trích xuất và audit trail.
- Provider chỉ tạo suggestion. Không tự ghi assessment, evidence hay quyết định đầu tư.
- Analyst phải chấp nhận từng suggestion trước khi chuyển thành evidence/link.
- Xác minh lại source/content/hash/excerpt/locator khi ghi run và khi analyst chấp nhận; khóa citation hallucination và stale content.
- Run thành công/thất bại đều lưu model version, prompt version/hash, request IDs, token usage, latency, số lần thử và lỗi an toàn.
- HTTP provider chạy ngoài transaction database; retry có giới hạn cho timeout/rate-limit/lỗi tạm thời.
- API key chỉ đọc từ Streamlit server secrets và không được ghi vào request body, database hay audit log.
- Giữ lại bộ nhập JSON Phase 4A làm đường dự phòng có kiểm soát.

## Database

- Thêm bảng `research_source_contents` và index theo source/company.
- Mở rộng `ai_research_runs` với provider audit/usage metadata.
- Mở rộng `ai_research_suggestions` với content ID/hash chính xác tại thời điểm chạy.
- Hỗ trợ nâng cấp idempotent cho SQLite cũ và PostgreSQL/Supabase.
- Các bảng nội bộ bật RLS nhưng không cấp policy cho client; thu hồi quyền `anon`/`authenticated`.

## Kiểm thử trước migration production

- Toàn bộ Investment Checklist: **149 passed, 10 skipped** ở local.
- Bao phủ provider success/failure/refusal, strict response contract, request-id audit, citation hallucination, sai trang PDF, stale content, review lock và nâng cấp SQLite V23.84.
- PostgreSQL tests được giữ cho GitHub Actions/PostgreSQL 16 và Supabase live validation.

## Vận hành

- Cần cấu hình `OPENAI_API_KEY` trong Streamlit server secrets để bật nút chạy provider.
- Mọi lần gửi tài liệu sang OpenAI đều cần checkbox xác nhận chủ động của analyst tại thời điểm chạy.
