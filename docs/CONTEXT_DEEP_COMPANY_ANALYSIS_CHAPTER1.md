# Trecapital — Context triển khai trang "Phân tích chuyên sâu doanh nghiệp"

## 1. Mục tiêu

Xây dựng một page mới trong Trecapital có tên **Phân tích chuyên sâu doanh nghiệp**, phát triển từng chương theo khung của Michael Shearn trong *The Investment Checklist: The Art of In-Depth Research*.

Trang này không thay thế page **Investment Checklist** hiện tại. Page mới được thiết kế như một **living investment research report**: mỗi chương vừa tổng hợp kết luận, vừa liên kết tới bằng chứng, lịch sử thay đổi và các chương phân tích sâu hơn.

## 2. Nguyên tắc lõi

- **AI/Data = Research Assistant.**
- **Người dùng = Investment Analyst.**
- AI có thể thu thập, tính toán, tìm evidence/counter-evidence, phát hiện trigger và đề xuất.
- AI không được tự ghi đè đánh giá analyst, không tự đổi Research Gate và không tự đưa ra quyết định mua/bán.
- Trecapital Data Layer là **Single Source of Truth** cho dữ liệu tài chính/định giá khi bridge tự động.
- Bản Chapter 1 phải chạy **offline hoàn toàn** với SQLite local; không phụ thuộc API hay Internet để nhập, lưu và đọc lại hồ sơ.

## 3. Căn cứ Chương 1 của sách

Chapter 1 của sách có 3 phần chính:

1. **How Investment Opportunities Are Created**
2. **How to Filter Your Investment Ideas**
3. **Using a Spreadsheet to Track Potential and Existing Holdings**

Table 1.1 dùng 10 tiêu chí lọc chất lượng:

1. Recurring Revenue
2. Long Runway
3. Proven Management
4. Franchise / Moat
5. Strong Financials
6. High ROIC
7. Limited Competition
8. Low Capital Expenditures
9. Diversified Customer Base
10. Strong Balance Sheet

Table 1.2 là **Inventory of Ideas**, dùng để theo dõi các cơ hội hiện tại và tiềm năng; các trường gốc gồm TEV/EBIT, TEV/EBITDA, TEV/Normalized Earnings, Pre-Tax Earnings Yield, Debt/EBITDA, EBIT/Interest Expense, FCF Yield, Dividend Yield, Market Price, Free Cash-Flow Estimate, Target Price và Stock Price vs. Target.

## 4. Kiến trúc Chương 1 đã thống nhất

### A. Idea Origin — Nguồn hình thành ý tưởng

Lưu nguồn hình thành ý tưởng, lý do doanh nghiệp xuất hiện trên radar, tại sao thị trường có thể đang định giá sai và initial thesis.

### B. Opportunity Signals

Theo dõi:
- Drawdown từ đỉnh 52 tuần;
- historical valuation percentile;
- price/earnings hoặc price/cash-flow divergence;
- event / forced selling.

Opportunity Signal **không phải Buy Signal**.

### C. Quality Filter — Table 1.1

Mỗi tiêu chí có:

- Analyst Assessment: `✓ Có | X Không | — Chưa biết | N/A`;
- Confidence: **Thấp | Trung bình | Cao**;
- Evidence / Note.

Confidence là lớp quản trị chất lượng nhận định do app bổ sung, **không phải tiêu chí gốc của Shearn và không cộng vào Quality Score**. Dữ liệu legacy 4–5 được quy về mức **Cao**.

App tổng hợp:
- Quality Filter = số tiêu chí `✓` / 10;
- Unknown = số tiêu chí `—` / 10.

**Quality score chỉ là research filter, không phải tín hiệu mua/bán.**

### D. Research Gaps

Lưu các nội dung chưa biết / Critical Unknowns, mỗi dòng một mục. Các chương tiếp theo sẽ lần lượt đóng các khoảng trống thông tin này.

### E. Valuation Snapshot — bridge sang Table 1.2

Các trường:
- Current Price;
- Target Price;
- FCF Yield;
- Dividend Yield;
- TEV/EBIT;
- TEV/EBITDA;
- Debt/EBITDA;
- EBIT/Interest.

App tự tính MOS so với Target và Stock Price / Target.

Trecapital hiện đã có bridge canonical để lấy/tính phần lớn các trường này từ Module 1/Module 2. Chapter 1 sẽ nối vào bridge đó thay vì tạo data engine riêng.

### F. Research Gate

Bốn trạng thái:
- 🟢 **Continue** — tiếp tục nghiên cứu chuyên sâu;
- 🟡 **Watch** — theo dõi, chờ thêm dữ liệu hoặc điều kiện;
- 🟠 **Pause** — tạm dừng nghiên cứu;
- 🔴 **Reject** — loại khỏi pipeline nghiên cứu hiện tại.

Quy tắc:
- `Reason for Gate` bắt buộc;
- Gate do analyst quyết định;
- app không tự đổi Gate;
- khi Gate thay đổi phải lưu lịch sử append-only;
- Reject không xóa hồ sơ và có thể reopen.

### G. Opportunity Inventory / Table 1.2

Khi analyst bấm **Lưu đánh giá Chương 1**, doanh nghiệp tự động được đưa vào Inventory và phân nhóm theo Gate: Continue / Watch / Pause / Reject.

Một ticker chỉ có **một current opportunity record**, nhưng có nhiều snapshot/history.

## 5. Monitoring / Review Queue

Mỗi doanh nghiệp có thể lưu trigger như MOS, giá, BCTC mới, Debt/EBITDA hoặc sự kiện định tính. App về sau có thể tự phát hiện trigger nhưng **không tự đổi Research Gate**.

## 6. Persistence offline

Database local:

`data_cache/deep_company_analysis_chapter1.db`

Các bảng:
- `chapter1_current`
- `chapter1_quality_current`
- `chapter1_gate_history`
- `chapter1_snapshots`
- `chapter1_monitoring_triggers`

## 7. Case thử nghiệm DGC

Fixture:

`sample_data/deep_company_analysis/DGC_chapter1_trial.json`

Đây là case point-in-time as-of **28/08/2026** dùng để kiểm thử workflow, không phải dữ liệu live. Khi nhập mã `DGC`, page có nút nạp case vào SQLite local.

Kết quả thử nghiệm hiện tại:
- Quality Filter: **5/10**;
- Unknown: **2/10**;
- Research Gate: **🟡 Watch**;
- Current Price: 43.000 đ/cp trong fixture;
- Target/MOS để trống cho đến khi nối Module 2 canonical valuation.

Chi tiết mapping dữ liệu tự động nằm tại:

`docs/DGC_CHAPTER1_TRIAL_AUTODATA_AUDIT.md`

## 8. File triển khai

Branch:

`feature/deep-company-analysis-checklist`

Page:

`pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py`

Logic:

`modules/deep_company_analysis/chapter1.py`

Tests:

`modules/deep_company_analysis/test_chapter1.py`

## 9. Đóng gói offline

Người dùng đã có sẵn Python 3.11. Từ V2 package **không đóng kèm Python/wheelhouse** để giảm dung lượng. Gói chỉ chứa source, cấu hình, dữ liệu mẫu và file `.bat` chạy app.

## 10. Acceptance criteria Chương 1

- Page mở được offline.
- Một ticker lưu được đầy đủ A→F.
- Table 1.1 lưu 10 tiêu chí + Confidence 3 mức + note.
- Confidence không tham gia Quality Score.
- Lưu Gate bắt buộc Reason for Gate.
- Opportunity Inventory tự phân nhóm theo Gate.
- Đổi Gate tạo history, không mất record cũ.
- Snapshot được tạo mỗi lần lưu.
- Reject không xóa dữ liệu.
- Monitoring trigger được lưu và đọc lại.
- Không có logic tự động đổi Research Gate.
- Không có tín hiệu BUY/HOLD/SELL trong Chapter 1.
