# Formula audit - Tổng quan doanh nghiệp V14

## 1. Sửa cách hiểu ROIC Buffett/Li Lu

V13 dùng trực tiếp:

```text
ROIC = Operating profit / Deployed Capital
Deployed Capital = Working capital + Fixed assets - Cash - Short-term financial investments
```

Cách này cho DGC rất cao vì hai nguyên nhân:

1. `Operating profit` theo dòng KQKD Việt Nam `Lợi nhuận thuần từ hoạt động kinh doanh` có thể bao gồm doanh thu tài chính từ lượng tiền gửi/đầu tư tài chính ngắn hạn lớn.
2. Mẫu số lại loại tiền và đầu tư tài chính ngắn hạn ra khỏi vốn triển khai. Như vậy numerator giữ lợi nhuận tài chính, denominator loại tài sản tạo ra lợi nhuận tài chính → không đồng bộ.

V14 tách thành 2 chỉ tiêu:

### 1.1. ROIC chuẩn - chỉ tiêu chính trên dashboard

```text
Core Operating Profit = Gross Profit - Selling Expenses - G&A Expenses
Tax Rate = Tax Expense / Profit Before Tax
NOPAT = Core Operating Profit × (1 - Tax Rate)
Capital Employed = Total Assets - Current Liabilities
Average Capital Employed = (Capital Employed đầu kỳ + cuối kỳ) / 2
ROIC chuẩn = NOPAT / Average Capital Employed
```

Đây là chỉ tiêu chính để tránh ROIC bị thổi phồng ở doanh nghiệp nhiều tiền/đầu tư tài chính ngắn hạn như DGC.

### 1.2. ROIC Li Lu / Deployed - chỉ tiêu bổ sung

```text
Operating Working Capital = Current Assets - Cash - Short-term Financial Investments - Current Liabilities
Deployed Capital = Operating Working Capital + Net Fixed Assets
Average Deployed Capital = (Deployed Capital đầu kỳ + cuối kỳ) / 2
ROIC Li Lu / Deployed = Core Operating Profit / Average Deployed Capital
```

Chỉ tiêu này gần với cách đọc Timberland của Li Lu: loại phần tiền mặt dư thừa để xem vốn thực sự triển khai trong vận hành tạo được bao nhiêu operating profit. Tuy nhiên chỉ tiêu này không nên dùng thay thế ROIC chuẩn nếu doanh nghiệp đang có lượng tiền gửi/đầu tư tài chính rất lớn và lợi nhuận tài chính đáng kể.

## 2. ROE tự tính / ROE thực tế

V13 dùng gần đúng:

```text
ROE thực tế = Net profit / Ending equity
```

V14 sửa lại đúng hơn:

```text
Average Equity = (Equity đầu kỳ + Equity cuối kỳ) / 2
ROE tự tính = Net profit / Average Equity
```

Với dữ liệu quý, FireAnt `ROE_TTM` được ưu tiên khi có. Khi phải tự tính, app dùng cơ sở TTM và vốn chủ sở hữu bình quân để tránh ROE bị thấp/cao do chỉ lấy vốn chủ sở hữu cuối kỳ.

## 3. Owner Earnings

Theo Buffett 1986, Owner Earnings là:

```text
Reported earnings
+ Depreciation, depletion, amortization and certain other non-cash charges
- Average annual capitalized expenditures required to fully maintain long-term competitive position and unit volume
```

V14 vẫn dùng proxy thực dụng với dữ liệu FireAnt công khai:

```text
Owner Earnings ≈ CFO - Maintenance Capex
```

Trong dữ liệu app, capex là dòng tiền ra nên thường âm. Vì vậy:

```text
Owner Earnings = CFO + average(-abs(capex_bil))
```

`average(-abs(capex_bil))` là maintenance capex ước tính bằng trung bình trượt 5 năm đối với dữ liệu năm hoặc 8 quý đối với dữ liệu quý. Cách này tránh sai dấu khi nguồn dữ liệu lưu Capex là số dương. Nếu sau này có dữ liệu tách maintenance capex và growth capex, app nên dùng maintenance capex thực tế thay proxy này.

DuPont V23.62: asset turnover dùng doanh thu / tổng tài sản bình quân; equity multiplier dùng tổng tài sản bình quân / vốn chủ sở hữu bình quân để nhất quán với ROA/ROE tự tính.

## 4. DuPont

V14 giữ 3 biểu đồ:

1. `DUPONT: ROE - ROA - BIÊN LỢI NHUẬN RÒNG`.
2. `DUPONT: NHÂN TỐ ĐÓNG GÓP VÀO ROE`.
3. `ĐẦU TƯ VÀ HIỆU QUẢ ĐẦU TƯ ROIC`.

Công thức DuPont:

```text
ROE = Net Profit Margin × Asset Turnover × Equity Multiplier
```

Trong biểu đồ 1, các đường tiêu chuẩn đã dùng đúng màu với cột tương ứng:

- Tiêu chuẩn ROE cùng màu với cột ROE.
- Tiêu chuẩn Net Profit Margin cùng màu với cột Net Profit Margin.
- Tiêu chuẩn Gross Margin cùng màu với cột Gross Margin.
