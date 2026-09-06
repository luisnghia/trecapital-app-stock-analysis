# Deep Company Analysis — Merge Readiness V41

## Mục tiêu

V41 là nhánh kiểm định cuối trước khi tích hợp Deep Company Analysis Chapter 1–7 vào nhánh sản phẩm Trecapital. Không thay đổi logic đầu tư hoặc dữ liệu tài chính; mục tiêu là kiểm tra ancestry/branch drift, xung đột, regression giữa Deep Company Analysis và Investment Checklist, và khả năng khởi động Streamlit trên bề mặt production.

## Nhánh

- Merge-readiness branch: `feature/deep-company-analysis-merge-ready-v41`
- Parent acceptance branch: `feature/deep-company-analysis-dgc-acceptance-v40`
- V38 baseline: `feature/deep-company-analysis-sort-ttm-v38`
- Product integration baseline: `feature/investment-checklist-phase1c`
- Repository default integration target: `main`

## Preflight branch audit trước CI

GitHub compare cho thấy:

| Base | Head | Ahead | Behind | Kết luận preflight |
|---|---|---:|---:|---|
| V38 | V40 | 2 | 0 | V40 là hậu duệ trực tiếp của V38; phần tăng thêm chỉ là strict DGC acceptance workflow + audit document. |
| `feature/investment-checklist-phase1c` | V40 | 455 | 0 | Không có commit mới ở Phase1C nằm ngoài lịch sử V40; có thể kiểm tra theo hướng fast-forward ancestry. |
| `main` | V40 | 692 | 0 | V40 chứa toàn bộ lịch sử `main`; không có branch divergence theo compare, nhưng khoảng cách 692 commit bắt buộc phải chạy production regression trước khi merge. |

## Acceptance gates V41

1. Xác nhận `main`, Phase1C, V38 và V40 đều là ancestor của V41.
2. Không tồn tại unresolved Git merge-conflict marker trong Python/YAML.
3. Route và file lõi của Investment Checklist + Deep Company Analysis vẫn hiện diện.
4. Compile toàn bộ integration surface: `app.py`, Module 1, Module 2, Checklist, Deep Company Analysis và các Streamlit page liên quan.
5. Chạy toàn bộ `modules/deep_company_analysis/test_*.py` với failure semantics nghiêm ngặt.
6. Chạy toàn bộ `modules/investment_checklist/tests` với PostgreSQL 16 service để kiểm tra SQLite + PostgreSQL integration.
7. Streamlit health smoke ba bề mặt: main app, Deep Company Analysis page, Investment Checklist page.
8. Chỉ tạo `DEEP_ANALYSIS_MERGE_READINESS_V41.json` với `acceptance=PASS` khi tất cả gate phía trước đã PASS.

## Nguyên tắc merge

V41 chỉ là nhánh **merge-ready**, không tự động merge vào `main`. Nếu V41 PASS, bước tiếp theo là mở PR/merge có kiểm soát. Do `main` đang cách V40 hàng trăm commit nhưng vẫn là ancestor, việc tích hợp có thể là fast-forward về mặt lịch sử; tuy nhiên chỉ được coi là an toàn sau khi regression production và Streamlit smoke đều PASS.

## Kết quả CI

_Pending — sẽ cập nhật sau khi workflow `Deep Company Analysis V41 — Merge Readiness` hoàn tất._
