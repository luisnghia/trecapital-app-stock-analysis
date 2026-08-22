# V23.89 — Monitoring & Delta Review (Phase 6)

## Phạm vi

- Thêm khu vực top-level `📡 Monitoring & Delta Review` vào Fast Entry V3.
- Monitoring rule có version theo Q01–Q59, cadence, trigger, metric/threshold, materiality và exact evidence.
- Observation append-only phân biệt `triggered`, `clear`, `unknown` và `research_gap`; kết luận triggered/clear bắt buộc có evidence.
- Delta queue chỉ hoạt động trong review loại `delta` có `prior_review_id` đã completed.
- Mỗi delta item giữ baseline assessment, observation/evidence, change type, proposed action, confidence và materiality.
- Analyst phải cập nhật Q01–Q59 trong Analyst Workspace trước; Phase 6 chỉ liên kết assessment kết quả rồi ghi quyết định bất biến.

## Guardrail

- Phase 6 không gọi provider/network và không tự ghi `analyst_assessments`.
- Carry-forward bắt buộc assessment có `analyst_confirmed`; revise/research-gap bắt buộc status tương ứng.
- Completed review khóa mọi ghi mới.
- Immutable snapshot nâng lên `phase1b-review-v6-evidence-peer-ai-management-monitoring-delta`.
- Review deletion xóa đúng dữ liệu Phase 6 thuộc review, giữ evidence/audit tombstone và xử lý an toàn lineage delta.

## Database

- Thêm `monitoring_rules`, `monitoring_observations`, `delta_review_items`, `delta_review_decisions`.
- Covering index cho review/company/question/rule/evidence/baseline/supersedes.
- PostgreSQL/Supabase bật RLS và thu hồi quyền `anon`/`authenticated`; app tiếp tục dùng trusted direct connection.

## Hotfix đi kèm

- Loại bỏ leading indentation trong HTML bảng Industry & Moat; nội dung không còn bị render thành Markdown code block.
- Regression khóa HTML thật phải bắt đầu bằng `<style>` và có wrapper responsive.
