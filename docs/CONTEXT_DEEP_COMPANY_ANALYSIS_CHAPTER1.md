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
- Chapter 1 chạy local với SQLite; việc nhập/lưu/mở lại hồ sơ, Inventory và Review Queue không phụ thuộc API/Cloud DB.

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

## 4. Kiến trúc Chương 1 đã triển khai

### A. Idea Origin — Nguồn hình thành ý tưởng

Lưu nguồn hình thành ý tưởng, lý do doanh nghiệp xuất hiện trên radar, tại sao thị trường có thể đang định giá sai và initial thesis.

### B. Opportunity Signals

Theo dõi/tự động hóa:
- Drawdown từ đỉnh 52 tuần;
- historical valuation percentile;
- price/earnings hoặc price/cash-flow divergence;
- event / forced selling candidate.

Opportunity Signal **không phải Buy Signal**. Event từ WebEvidence chỉ là candidate cần analyst xác minh.

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

Bốn tiêu chí định lượng hiện có Data Suggested từ Trecapital canonical data: Strong Financials, High ROIC, Low Capital Expenditures, Strong Balance Sheet. Analyst Assessment đã lưu không bị auto-data ghi đè.

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

App tự tính MOS so với Target và Stock Price / Target. Trecapital dùng canonical bridge từ Module 1/Module 2, không tạo data engine riêng cho Chapter 1. Quote stale guard vô hiệu các field/trigger phụ thuộc giá khi quote quá cũ.

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

Structured Trigger Builder hỗ trợ:
- Giá;
- MOS;
- ROIC;
- Debt/EBITDA;
- EBIT/Interest;
- FCF Yield;
- Valuation Percentile;
- 52W Drawdown;
- BCTC mới;
- BCTC kỳ cụ thể, ví dụ Q3/2026;
- Event/CBTT candidate mới;
- trigger thủ công nâng cao để giữ backward compatibility.

Engine chỉ tạo Review Queue khi trigger chuyển từ chưa thỏa sang thỏa; không spam trùng. Resolve item không thay đổi Gate. BCTC/event dùng baseline. Trigger giá/MOS/FCF Yield/valuation percentile không chạy từ quote stale.

## 6. Persistence offline

Database local:

`data_cache/deep_company_analysis_chapter1.db`

Các bảng chính:
- `chapter1_current`
- `chapter1_quality_current`
- `chapter1_gate_history`
- `chapter1_snapshots`
- `chapter1_monitoring_triggers`
- `chapter1_trigger_state`
- `chapter1_review_queue`

## 7. Case thử nghiệm DGC

Fixture:

`sample_data/deep_company_analysis/DGC_chapter1_trial.json`

Đây là case point-in-time as-of **28/08/2026** dùng để kiểm thử workflow, không phải dữ liệu live. Kết quả thử nghiệm nền:
- Quality Filter: **5/10**;
- Unknown: **2/10**;
- Research Gate: **🟡 Watch**;
- Current Price fixture: 43.000 đ/cp.

Chi tiết mapping dữ liệu tự động nằm tại:

`docs/DGC_CHAPTER1_TRIAL_AUTODATA_AUDIT.md`

## 8. File triển khai

Branch:

`feature/deep-company-analysis-checklist`

Page:

`pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py`

Logic:

`modules/deep_company_analysis/chapter1.py`

Monitoring:

`modules/deep_company_analysis/monitoring.py`

Structured Trigger Builder:

`modules/deep_company_analysis/structured_triggers.py`

Final acceptance test:

`modules/deep_company_analysis/test_chapter1_final_acceptance.py`

## 9. Đóng gói local/offline Lite

Người dùng đã có sẵn Python 3.11. Package Lite **không đóng kèm Python và không đóng kèm offline_wheels** để giảm dung lượng.

- Nếu máy đã có Python 3.11 + requirements Trecapital: tải ZIP → giải nén → double-click `CHAY_TRECAPITAL_OFFLINE.bat`.
- Nếu chỉ có Python 3.11 nhưng thiếu thư viện: `CAI_THU_VIEN_MOT_LAN.bat` sẽ cài từ PyPI và cần Internet **một lần**; sau đó app chạy local.
- Việc nhập/lưu/đọc hồ sơ Chapter 1 không cần Internet. Nút cập nhật dữ liệu thị trường/BCTC mới đương nhiên cần kết nối nguồn dữ liệu.

## 10. Acceptance criteria Chương 1

- Page mở được local.
- Một ticker lưu được đầy đủ A→F.
- Table 1.1 lưu 10 tiêu chí + Confidence 3 mức + note.
- Confidence không tham gia Quality Score.
- Lưu Gate bắt buộc Reason for Gate.
- Opportunity Inventory tự phân nhóm theo Gate.
- Một ticker chỉ có một current record.
- Đổi Gate tạo append-only history; snapshot không mất.
- Reject không xóa dữ liệu.
- Structured trigger được lưu và round-trip.
- BCTC kỳ cụ thể hoạt động.
- Review Queue chống cảnh báo trùng.
- Resolve Review Queue không tự đổi Gate.
- Quote stale không kích hoạt trigger phụ thuộc market price.
- Legacy manual trigger được giữ nguyên, không mất dữ liệu.
- Không có logic tự động đổi Research Gate.
- Không có tín hiệu BUY/HOLD/SELL trong Chapter 1.

## 11. Final Acceptance Test — 02/09/2026

Final acceptance được chạy trực tiếp trên branch hiện tại bằng Python 3.11 và case DGC:

- Compile Chapter 1: PASS.
- Full regression suite: **27/27 PASS**.
- DGC end-to-end acceptance riêng: **3/3 PASS**.
- Streamlit headless startup/health check cho page `07_Phan_tich_chuyen_sau_doanh_nghiep.py`: PASS.
- Lightweight package integrity check: PASS; bắt buộc có page, Chapter 1 engine, Monitoring Engine, Structured Trigger Builder và launcher; xác nhận không kèm `offline_wheels`.

DGC end-to-end đã xác minh flow:

`DGC fixture → SQLite save/load → Quality 5/10 → Unknown 2 → Watch → Opportunity Inventory → structured triggers → MOS trigger → BCTC Q3/2026 trigger → event-new trigger → Review Queue → resolve → Gate vẫn Watch → analyst đổi Gate → Continue → history/snapshots append-only → current inventory vẫn chỉ 1 DGC`.

Hai lỗi cấu hình được phát hiện và sửa trong vòng final test:

1. **CI cũ vẫn re-apply migration patch V4/V5/V6 lên source đã ở V6**, có thể làm hỏng pipeline. Đã bỏ hoàn toàn legacy patch-reapply khỏi CI; CI giờ test chính source hiện hành.
2. **Launcher/Hướng dẫn Lite còn ghi sai rằng package có `offline_wheels`**, trong khi V2+ đã cố ý loại wheelhouse. Đã sửa launcher, installer và hướng dẫn để phản ánh đúng: package Lite không kèm Python/wheels; nếu thiếu dependency thì cần Internet một lần để cài requirements.

Kết luận: **Chapter 1 đạt acceptance để khóa tính năng và chuyển sang thiết kế Chapter 2.**
