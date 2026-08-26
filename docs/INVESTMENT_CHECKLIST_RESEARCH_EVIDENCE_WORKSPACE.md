# Research Evidence Workspace — Technical specification

## Mục tiêu

Research Evidence Workspace tạo chuỗi truy xuất đầy đủ:

`Nguồn → Evidence version → Review → Q01–Q59 → Analyst assessment → Immutable snapshot`.

Workspace không dùng AI và không thay analyst đưa ra kết luận. Nó giải quyết bốn yêu cầu vận hành:

1. Mọi nhận định có thể truy ngược về nguồn và vị trí cụ thể.
2. Bằng chứng ủng hộ, phản bác và bối cảnh được lưu tách biệt.
3. Nội dung sửa đổi không ghi đè lịch sử; mỗi thay đổi tạo version mới kèm lý do.
4. Finalized review giữ exact evidence versions, không bị hồi tố bởi nghiên cứu sau này.

## Data model

### `research_sources`

Danh mục nguồn theo doanh nghiệp:

- loại nguồn;
- tiêu đề, nhà phát hành, URL;
- ngày tài liệu và ngày analyst truy cập;
- reliability 1–5;
- trạng thái active/archived;
- source hash chống nhập trùng;
- audit actor/time.

Nguồn đã archived không nhận evidence version mới nhưng evidence lịch sử vẫn được giữ.

### `research_evidence`

Mỗi evidence có stable `evidence_key` và nhiều version append-only:

- loại: fact, quote, metric, observation, contradiction, risk;
- locator: trang/mục/đoạn;
- excerpt/sự kiện ngắn có thể kiểm chứng;
- ghi chú analyst;
- verification: unverified, verified, disputed, stale;
- direction: supports, contradicts, context;
- confidence 1–5;
- `supersedes_evidence_id`, `version_no`, `change_reason`, content hash.

Link cũ không tự chuyển sang evidence version mới. Analyst phải chủ động chọn version dùng cho review.

### `evidence_question_links`

Liên kết exact evidence version với một review và một câu Q01–Q59:

- relationship: primary, supporting, context, contradicts;
- materiality 1–5;
- link note;
- active/deactivated state và lý do bỏ link;
- audit actor/time.

Review completed là read-only. Nguồn và evidence cấp doanh nghiệp vẫn có thể tiếp tục được bổ sung để dùng cho review tương lai.

## UI workflow

### Coverage

- 59 dòng Q01–Q59.
- Số evidence, số verified, số mâu thuẫn và materiality cao nhất.
- Lọc câu chưa có evidence hoặc có evidence phản bác.
- Xuất evidence package JSON của review.

### Nguồn

- Thêm nguồn có metadata và reliability.
- Phát hiện nguồn trùng theo hash.
- Archive có lý do; không hard-delete lịch sử.

### Bằng chứng

- Ghi evidence version 1.
- Tạo version sửa đổi có lý do; version cũ giữ nguyên.
- Hiển thị evidence mới nhất theo evidence key.

### Liên kết Q01–Q59

- Một evidence có thể gắn nhiều câu hỏi.
- Một câu hỏi có thể có nhiều evidence từ nhiều nguồn/version.
- Unlink cần lý do và chỉ deactive, không xóa audit.
- Completed review chỉ đọc.

### Analyst Workspace

- Khi chọn một câu hỏi, app hiển thị exact linked evidence versions ngay trên form assessment.
- Evidence được cache theo review; đổi câu hỏi chỉ lọc trong bộ nhớ, không thêm database round-trip.
- Nếu có contradiction, app hiển thị cảnh báo để analyst xử lý trong kết luận.

## Snapshot và deletion

- `finalize_review()` dùng snapshot schema `phase1b-review-v2-evidence`.
- Snapshot chứa evidence summary và toàn bộ active links kèm source/evidence metadata tại thời điểm finalize.
- Xóa review thủ công xóa evidence links của review để giải phóng FK, nhưng giữ `research_sources` và `research_evidence` cho review khác.
- Audit tombstone ghi số evidence links bị xóa.

## Acceptance tests

- Tạo nguồn trùng bị từ chối.
- Evidence sửa đổi thiếu change reason bị từ chối.
- Latest evidence trả đúng version mới nhất; version cũ vẫn truy xuất được qua review link.
- Coverage đếm đúng covered/verified/contradictory questions.
- Completed review chặn link/unlink.
- Snapshot không đổi sau finalize.
- Review deletion giữ nguồn/evidence và xóa link thuộc review.
- SQLite/PostgreSQL cùng semantics.
- Migration legacy không lỗi khi database nguồn chưa có evidence tables.
- Streamlit smoke render sạch Coverage, Nguồn, Bằng chứng và Liên kết Q01–Q59.
