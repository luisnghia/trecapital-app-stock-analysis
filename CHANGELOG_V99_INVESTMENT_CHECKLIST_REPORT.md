# V99 — Investment Checklist Word Research Report

## Phạm vi

V99 hoàn thiện luồng xuất Word của **Investment Research & Checklist** trên nền V98, không mở thêm pipeline dữ liệu tài chính và không thay đổi quyền quyết định của analyst.

## Thay đổi chính

- Thêm báo cáo Word `.docx` cho review đang chọn, tạo theo cơ chế **explicit / lazy**: chỉ dựng báo cáo khi analyst bấm `Tạo / làm mới báo cáo Word`.
- Báo cáo chứa Q01–Q59, trạng thái, Analyst Assessment, Confidence, Materiality, analyst answer và Reason for Change.
- Đưa Research Evidence đã liên kết vào đúng từng Question.
- Đưa financial evidence 10 năm + TTM vào các nhóm trọng yếu Q25–Q32, Q46–Q47 và Q53–Q57 khi có field canonical trực tiếp.
- Mỗi financial evidence row có lineage: `source_field`, `source_module`, `source_period`, `data_origin`.
- Khi field canonical không có, báo cáo ghi đúng `chưa có dữ liệu chuẩn hóa`; không thay bằng 0 và không suy diễn.
- Financial evidence adapter chỉ đọc `annual_df` canonical của Trecapital Data Layer; không gọi API, không import engine định giá, không append TTM và không tái tính ROIC/FCF/valuation.
- Giữ nguyên renderer V98 byte-for-byte trong `integration_preview_v3_legacy.py`; V99 chỉ bọc thêm surface xuất Word để giảm rủi ro regression đối với navigation/performance contract hiện hữu.

## Guardrails

1. **Single Source of Truth**: Trecapital Data Layer là nguồn duy nhất cho dữ liệu tài chính tự động.
2. **Analyst remains decision maker**: exporter là read-only projection, không ghi/override assessment.
3. **No silent inference**: thiếu field canonical được thể hiện rõ là thiếu dữ liệu.
4. **Point-in-time export**: file Word phản ánh trạng thái ở thời điểm analyst bấm tạo/làm mới; nếu vừa sửa assessment/evidence phải bấm tạo lại.

## Regression tests bổ sung

- Full source traceability cho financial evidence.
- Explicit missing-data behavior, không zero-fill.
- Analyst judgment preservation.
- Không có network fetch hoặc parallel financial/formula engine trong V99 report layer.
- DOCX chứa analyst answer, source trace, TTM và marker thiếu dữ liệu.
