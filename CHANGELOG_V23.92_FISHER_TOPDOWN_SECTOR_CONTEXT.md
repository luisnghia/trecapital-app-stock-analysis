# V23.92 — Fisher Top-down & Sector Context

## Phạm vi

- Tích hợp module `V1.1_TOPDOWN_SECTOR` thành page độc lập thứ sáu của Trecapital.
- Thêm workspace `🧭 Fisher Top-down & Sector` trong Investment Checklist.
- Lưu toàn bộ 11 ngành, 26 Portfolio Drivers, pha chu kỳ, benchmark, ranking và tỷ trọng dưới dạng snapshot append-only theo review.

## Governance

- Sector context không tự ghi Q01–Q59, không thay assessment Industry & Moat và không phát lệnh mua/bán.
- Analyst phải chọn ngành của doanh nghiệp, xác nhận time horizon và ghi lý do lưu/version.
- Benchmark khởi tạo được giữ ở trạng thái `unverified` cùng Research gap bắt buộc.
- `analyst_verified` chỉ hợp lệ khi gắn exact evidence mới nhất, thuộc doanh nghiệp, nguồn còn active và evidence đã `verified`.
- Payload và source mapping đều có SHA-256; immutable review snapshot chứa latest version và lịch sử hash.
- Review completed khóa ghi; manual review deletion xóa snapshot thuộc review nhưng giữ audit tombstone.

## Database

- Thêm `topdown_sector_snapshots` với 27 cột, 4 foreign keys và 6 indexes tính cả PK/unique.
- RLS bật; `anon` và `authenticated` không có quyền table/sequence.
- Migration: `investment_checklist_phase8_governed_fisher_topdown_sector`.

## Kiểm thử

- Top-down engine self-check: 60 kịch bản ngẫu nhiên + kịch bản biên, đạt toàn bộ.
- Top-down UI smoke: 25 kịch bản, đạt toàn bộ.
- Full repository: 180 passed, 14 skipped.
