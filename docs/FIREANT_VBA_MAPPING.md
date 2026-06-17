# Mapping FireAnt từ file Financial-v1.3.0.xlsm

Trong phần VBA `TCReport_FireAnt.cls`, URL được tạo theo logic:

```vb
Case CSTC, CSTCq: .ReportType = 5
  .url = SIE_FireAnt & "api/Data/Finance/" & _
       IIf(.toQuarter = 0, "Yearly", "Quarterly") & "FinancialInfo?symbol=" & .MaSIC & _
          "&fromYear=" & .fromYear & _
          IIf(.toQuarter = 0, n_, "&fromQuarter=" & .fromQuarter) & _
          "&toYear=" & .toYear & _
          IIf(.toQuarter = 0, n_, "&toQuarter=" & .toQuarter)

Case CDKT:       .ReportType = 1
Case CDKTq:      .ReportType = 1
Case KQKD:       .ReportType = 2
Case KQKDq:      .ReportType = 2
Case LCTTTT:     .ReportType = 3
Case LCTTTTq:    .ReportType = 3
Case LCTTGT:     .ReportType = 4
Case LCTTGTq:    .ReportType = 4

.url = SIE_FireAnt & "api/Data/Finance/LastestFinancialReports?symbol=" & .MaSIC & _
        "&type=" & .ReportType & _
        "&year=" & .toYear & _
        "&quarter=" & .toQuarter & _
        "&count=" & CStr(.DataColumns)
```

V13 chuyển đúng logic này sang Python tại `adapters/vn_public_crawler.py`, class `PublicFireAntCrawler`.

Điểm sửa quan trọng so với các bản trước: parser mới không làm mất nhãn chỉ tiêu `Name` khi dữ liệu kỳ nằm trong list con `Values`.

## Bổ sung V13

- `cash_dividend_bil` vẫn lưu giá trị dòng tiền cổ tức đã trả theo LCTT để kiểm tra nguồn.
- Dashboard không vẽ `cash_dividend_bil` nữa mà vẽ `cash_dividend_yield_pct` theo năm: `abs(cash_dividend_bil) * 1.000 / shares_outstanding_mil / year_end_price * 100`.
- `year_end_price` được lấy từ payload lịch sử giá FireAnt nếu endpoint public trả được dữ liệu. Nếu không có dữ liệu giá cuối năm, app để trống tỷ suất cổ tức thay vì dùng sai giá hiện tại.
- Dữ liệu quý không hiển thị chỉ tiêu cổ tức.
- Với các quý/năm FireAnt chưa trả đủ ratio TTM, app tự điền `EPS`, `OEPS`, `ROE thực tế`, `ROE DuPont`, và ước tính ROE/ROIC để tránh dashboard chính bị N/A.
