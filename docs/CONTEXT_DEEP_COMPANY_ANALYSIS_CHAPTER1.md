# Trecapital — Context triển khai trang "Phân tích chuyên sâu doanh nghiệp"

## 1. Mục tiêu

Xây dựng một page mới trong Trecapital có tên **Phân tích chuyên sâu doanh nghiệp**, phát triển từng chương theo khung của Michael Shearn trong *The Investment Checklist: The Art of In-Depth Research*.

Trang này không thay thế page **Investment Checklist** hiện tại. Page mới được thiết kế như một **living investment research report**: mỗi chương vừa tổng hợp kết luận, vừa liên kết tới bằng chứng, lịch sử thay đổi và các chương phân tích sâu hơn.

## 2. Nguyên tắc lõi

- **AI/Data = Research Assistant.**
- **Người dùng = Investment Analyst.**
- AI có thể thu thập, tính toán, tìm evidence/counter-evidence, phát hiện trigger và đề xuất.
- AI không được tự ghi đè đánh giá analyst, không tự đổi Research Gate và không tự đưa ra quyết định mua/bán.
- Trecapital Data Layer sẽ là **Single Source of Truth** khi kết nối dữ liệu tự động ở các phase sau.
- Bản Chapter 1 đầu tiên phải chạy **offline hoàn toàn**, dùng SQLite local; không phụ thuộc API hay Internet.

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

Lưu:

- nguồn hình thành ý tưởng;
- tại sao doanh nghiệp xuất hiện trên radar;
- tại sao thị trường có thể đang định giá sai;
- initial thesis.

Các nguồn gợi ý trong app:

- thị trường giảm mạnh;
- ngành bị bán mạnh;
- cổ phiếu giảm mạnh/gần đáy 52 tuần;
- forced selling / bị loại khỏi chỉ số;
- spin-off / tái cấu trúc;
- sự kiện đặc biệt;
- kết quả kinh doanh tạm thời xấu;
- bất định pháp lý/quản trị/ngành;
- định giá thấp bất thường;
- screen định lượng;
- ý tưởng từ nhà đầu tư khác;
- doanh nghiệp chất lượng muốn theo dõi dài hạn;
- khác.

### B. Opportunity Signals

Phase đầu cho phép analyst nhập offline:

- Drawdown từ đỉnh 52 tuần;
- historical valuation percentile;
- price/earnings or price/cash-flow divergence;
- event / forced selling.

Phase sau bridge tự động từ Trecapital Data Layer. Opportunity Signal **không phải Buy Signal**.

### C. Quality Filter — Table 1.1

Mỗi tiêu chí có:

- Analyst Assessment: `✓ Có | X Không | — Chưa biết | N/A`;
- Confidence: 1–5;
- Evidence / Note.

App tổng hợp:

- Quality Filter = số tiêu chí `✓` / 10;
- Unknown = số tiêu chí `—` / 10.

**Quality score chỉ là research filter, không phải tín hiệu mua/bán.**

### D. Research Gaps

Lưu các nội dung chưa biết / Critical Unknowns, mỗi dòng một mục.

Mục tiêu: tạo queue nghiên cứu để các chương tiếp theo lần lượt đóng các khoảng trống thông tin.

### E. Valuation Snapshot — bridge sang Table 1.2

Phase đầu hỗ trợ nhập offline:

- Current Price;
- Target Price;
- FCF Yield;
- Dividend Yield;
- TEV/EBIT;
- TEV/EBITDA;
- Debt/EBITDA;
- EBIT/Interest.

App tự tính:

- MOS so với Target;
- Stock Price / Target.

Phase sau số liệu sẽ lấy từ Module 1/Module 2 canonical data, không tạo engine dữ liệu song song.

### F. Research Gate

Bốn trạng thái:

- 🟢 **Continue** — tiếp tục nghiên cứu chuyên sâu;
- 🟡 **Watch** — theo dõi, chờ dữ liệu/điều kiện;
- 🟠 **Pause** — tạm dừng nghiên cứu;
- 🔴 **Reject** — loại khỏi pipeline nghiên cứu hiện tại.

Quy tắc:

- `Reason for Gate` là bắt buộc;
- Gate do analyst quyết định;
- app không tự đổi Gate;
- khi Gate thay đổi phải lưu lịch sử append-only;
- Reject không xóa hồ sơ, có thể reopen sau này.

### G. Opportunity Inventory / Table 1.2

Khi analyst bấm **Lưu đánh giá Chương 1**, doanh nghiệp tự động được đưa vào Inventory và phân nhóm theo Gate:

1. Continue
2. Watch
3. Pause
4. Reject

Một ticker chỉ có **một current opportunity record**, nhưng có nhiều snapshot/history.

Inventory hiện các trường chính:

- Gate;
- ticker;
- tên doanh nghiệp;
- Quality Filter;
- Unknown;
- current price;
- target price;
- MOS;
- FCF Yield;
- Gate reason;
- Next Review;
- Last Updated.

## 5. Monitoring / Review Queue

Mỗi doanh nghiệp có thể lưu các trigger, ví dụ:

- Review khi MOS > 25%;
- Review khi giá < 80.000;
- Review sau BCTC Q3/2026;
- Review khi Debt/EBITDA < 2x.

Phase hiện tại chỉ lưu trigger offline.

Phase sau app có thể tự phát hiện trigger dựa trên dữ liệu mới và đưa doanh nghiệp vào Review Queue, nhưng **không tự đổi Research Gate**.

## 6. Persistence offline

Database local:

`data_cache/deep_company_analysis_chapter1.db`

Các bảng:

- `chapter1_current` — current record của mỗi ticker;
- `chapter1_quality_current` — Table 1.1 current assessment;
- `chapter1_gate_history` — lịch sử Gate append-only;
- `chapter1_snapshots` — snapshot mỗi lần lưu;
- `chapter1_monitoring_triggers` — trigger theo dõi.

Không cần PostgreSQL/Supabase/API để chạy Chapter 1 offline.

## 7. File triển khai hiện tại

Branch:

`feature/deep-company-analysis-checklist`

Page:

`pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py`

Logic Chương 1:

`modules/deep_company_analysis/chapter1.py`

Context:

`docs/CONTEXT_DEEP_COMPANY_ANALYSIS_CHAPTER1.md`

## 8. Cách chạy offline

Tại thư mục repo:

```powershell
git checkout feature/deep-company-analysis-checklist
pip install -r requirements.txt
streamlit run app.py
```

Sau đó mở menu **Phân tích chuyên sâu doanh nghiệp**.

Chapter 1 có thể nhập/lưu/mở lại hoàn toàn offline. File SQLite được tạo tự động khi mở page lần đầu.

## 9. Phase tiếp theo dự kiến

Sau khi Chapter 1 offline ổn định:

1. Bridge Opportunity Signals từ Trecapital canonical data.
2. Bridge valuation fields từ Module 1 / Module 2.
3. Thêm monitoring engine phát hiện trigger.
4. Thêm AI Research Assistant cho evidence nhưng vẫn giữ analyst approval.
5. Bắt đầu Chapter 2: Understanding the Business — The Basics.

## 10. Acceptance criteria Chương 1

- Page mở được offline, không cần API.
- Một ticker lưu được đầy đủ A→F.
- Table 1.1 lưu được 10 tiêu chí + confidence + note.
- Lưu Gate bắt buộc Reason for Gate.
- Opportunity Inventory tự phân nhóm theo Gate.
- Đổi Gate tạo history, không mất record cũ.
- Snapshot được tạo mỗi lần lưu.
- Reject không xóa dữ liệu.
- Monitoring trigger được lưu và đọc lại.
- Không có logic tự động đổi Research Gate.
- Không có tín hiệu BUY/HOLD/SELL trong Chapter 1.
