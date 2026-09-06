# Deep Company Analysis — DGC Chapter 1–7 Strict Acceptance V40

## Mục tiêu

V40 chuyển bài thử DGC Chapter 1–7 từ chế độ **trial/reporting** sang **strict acceptance gate**. Workflow V38 cũ cố ý dùng `set +e`, ghi exit code rồi `exit 0`, vì vậy workflow có thể xanh dù một Chapter thực tế đang GAP/FAIL. V40 không nuốt lỗi: bất kỳ bước acceptance bắt buộc nào thất bại sẽ làm GitHub Actions thất bại.

## Phạm vi khóa

- Chapter 1: core/final acceptance, canonical Trecapital bridge và TTM/T12M.
- Chapter 2: DGC business/industry evidence E2E.
- Chapter 3: DGC customer evidence E2E.
- Chapter 4: DGC supplier/competition evidence lock E2E.
- Chapter 5: DGC product economics/ROIC lock E2E.
- Chapter 6: quantitative/source/closure tests và live canonical quantitative gate.
- Chapter 7: management discovery/research/closure tests và live DGC management/evidence gate.
- Cuối cùng chạy toàn bộ `modules/deep_company_analysis/test_*.py` ở chế độ strict.

## Guardrail bắt buộc

### 1. Single Source of Truth

Dữ liệu tài chính Chapter 1 và Chapter 6 phải đi qua Trecapital canonical data. Workflow không tạo financial source riêng cho Deep Company Analysis.

### 2. Q32 PP&E semantics

Asset-age diagnostics chỉ được nhận field PP&E rõ nghĩa:

- `net_ppe_bil`
- `ppe_net_bil`
- `property_plant_equipment_net_bil`
- `gross_ppe_bil`
- `ppe_gross_bil`
- `property_plant_equipment_gross_bil`

Các field tổng quát như `fixed_assets_bil`, `non_current_assets_bil`, `long_term_assets_bil`, `total_long_term_assets_bil` không được dùng làm Net/Gross PP&E fallback. Nếu canonical data không có PP&E đúng nghĩa thì output phải giữ thiếu/N/A thay vì gán proxy sai nghĩa.

### 3. DGC official-source priority

DGC phải có nguồn doanh nghiệp chính thức `ducgiangchem.vn` trong `KNOWN_COMPANY_DOMAINS`. Nguồn chính thức là research target ưu tiên; nguồn tài chính thứ cấp chỉ dùng đối chiếu/tham khảo.

### 4. Analyst boundary

Chapter 7 management discovery chỉ phát hiện research targets/evidence. Nó không được tự ghi Analyst Management Profile, xác nhận chức vụ hiện tại khi bằng chứng chưa đủ, tự phân loại management quality/OO-LT-HH/Lion-Hyena, hoặc tự phát MOS/BUY-HOLD-SELL.

### 5. Missing-data discipline

Không tạo số liệu thay thế chỉ để lấp ô trống. Khi nguồn canonical/evidence không đủ, acceptance cho phép N/A/unknown nếu semantics yêu cầu như vậy; không cho phép proxy sai nghĩa hoặc kết luận vượt bằng chứng.

## Tiêu chí PASS

Workflow chỉ tạo marker `DGC_CH1_7_STRICT_ACCEPTANCE_V40.json` với `acceptance = PASS` khi tất cả bước trước đó đã hoàn tất thành công. Nếu một Chapter, live bridge, guardrail hoặc regression lỗi thì marker PASS không được tạo và workflow phải đỏ.

## File workflow

`.github/workflows/test-dgc-ch1-7-acceptance-v40.yml`

Branch triển khai: `feature/deep-company-analysis-dgc-acceptance-v40`.
