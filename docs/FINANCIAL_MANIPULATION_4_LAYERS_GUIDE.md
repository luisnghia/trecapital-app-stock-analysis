# V23.55 - Hướng dẫn 4 lớp cảnh báo thao túng tài chính

Mục tiêu của tab **Thao túng tài chính** là tạo cờ đỏ định lượng để kiểm tra sâu chất lượng báo cáo tài chính. Kết quả không phải kết luận pháp lý về gian lận.

## Lớp 1 - Beneish M-Score

Công thức:

```text
M = -4.84
  + 0.920 × DSRI
  + 0.528 × GMI
  + 0.404 × AQI
  + 0.892 × SGI
  + 0.115 × DEPI
  - 0.172 × SGAI
  + 4.679 × TATA
  - 0.327 × LVGI
```

Ngưỡng cảnh báo: `M-Score > -2.22`.

8 biến:

- `DSRI = (AR_t / Sales_t) / (AR_{t-1} / Sales_{t-1})`.
- `GMI = Gross Margin_{t-1} / Gross Margin_t`.
- `AQI = [1 - (Current Assets_t + PP&E_t) / Total Assets_t] / [1 - (Current Assets_{t-1} + PP&E_{t-1}) / Total Assets_{t-1}]`.
- `SGI = Sales_t / Sales_{t-1}`.
- `DEPI = DepRate_{t-1} / DepRate_t`, trong đó `DepRate = Depreciation / (Depreciation + PP&E)`.
- `SGAI = (SG&A_t / Sales_t) / (SG&A_{t-1} / Sales_{t-1})`.
- `TATA`: ưu tiên `Balance-sheet accruals / Total Assets_t`, trong đó `Balance-sheet accruals = ΔCurrent Assets - ΔCash - ΔCurrent Liabilities + ΔShort-term Debt - Depreciation`; nếu thiếu dữ liệu thì dùng proxy `(Net Profit_t - CFO_t) / Total Assets_t` và ghi rõ proxy.
- `LVGI = (Liabilities_t / Total Assets_t) / (Liabilities_{t-1} / Total Assets_{t-1})`.

Lưu ý: nếu nguồn dữ liệu không tách được PP&E/TSCĐ thuần và chỉ có tài sản dài hạn, app ghi rõ `AQI proxy`.

## Lớp 2 - Accrual Quality / Sloan

Công thức chính:

```text
Sloan accrual ratio = (LNST - CFO) / Tổng tài sản bình quân
```

Chỉ báo phụ:

```text
CFO/LNST = CFO / LNST
FCF/LNST = FCF / LNST
Balance-sheet accruals = ΔCA - ΔCash - ΔCL + ΔSTD - Depreciation
Balance-sheet accrual ratio = Balance-sheet accruals / Tổng tài sản bình quân
```

Diễn giải:

- Sloan accrual ratio dương cao: lợi nhuận phụ thuộc nhiều vào accruals hơn dòng tiền thật.
- CFO/LNST thấp kéo dài: lợi nhuận chưa chuyển hóa tốt thành tiền.
- FCF/LNST âm: cần phân biệt capex mở rộng hợp lý hay mô hình kinh doanh hút tiền.

Ngưỡng nội bộ:

- Sloan > 7% tài sản bình quân: theo dõi.
- Sloan > 12% tài sản bình quân: rủi ro cao.
- CFO/LNST < 0.8: cần kiểm tra.
- CFO/LNST < 0.5 hoặc CFO âm: rủi ro cao hơn.

## Lớp 3 - Modified Jones / Kothari

Mô hình Modified Jones:

```text
TA_t / A_{t-1} = α0 + α1 × (1 / A_{t-1})
                + α2 × ((ΔREV_t - ΔREC_t) / A_{t-1})
                + α3 × (PPE_t / A_{t-1}) + ε_t

DA Modified Jones = ε_t
```

Trong đó:

```text
TA = Total accruals
A_{t-1} = Tổng tài sản đầu kỳ
ΔREV = Doanh thu_t - Doanh thu_{t-1}
ΔREC = Phải thu_t - Phải thu_{t-1}
PPE = TSCĐ/PP&E
DA = Discretionary Accruals
```

Mô hình Kothari:

```text
TA_t / A_{t-1} = α0 + α1 × (1 / A_{t-1})
                + α2 × ((ΔREV_t - ΔREC_t) / A_{t-1})
                + α3 × (PPE_t / A_{t-1})
                + α4 × ROA_t + ε_t

DA Kothari = ε_t
```

Diễn giải:

- DA dương cao: accruals làm tăng lợi nhuận, cần kiểm tra doanh thu, phải thu, vốn hóa chi phí, dự phòng/hoàn nhập.
- DA âm sâu: có thể là big-bath hoặc ghi nhận chi phí trước.

Ngưỡng nội bộ:

- `|DA| > 7%` tổng tài sản đầu kỳ: theo dõi.
- `|DA| > 12%` tổng tài sản đầu kỳ: rủi ro cao.

Lưu ý triển khai: nếu chuỗi dữ liệu ngắn, app dùng proxy median và ghi rõ trong cột `Phương pháp ước lượng` thay vì giả vờ có hồi quy OLS ổn định.

## Lớp 4 - Real Earnings Management (REM)

Mô hình CFO bất thường:

```text
CFO_t / A_{t-1} = α0 + α1 × (1 / A_{t-1})
                 + β1 × (Sales_t / A_{t-1})
                 + β2 × (ΔSales_t / A_{t-1}) + ε_t

Abnormal CFO = ε_t
```

Mô hình sản xuất bất thường:

```text
PROD_t = COGS_t + ΔInventory_t

PROD_t / A_{t-1} = α0 + α1 × (1 / A_{t-1})
                  + β1 × (Sales_t / A_{t-1})
                  + β2 × (ΔSales_t / A_{t-1})
                  + β3 × (ΔSales_{t-1} / A_{t-1}) + ε_t

Abnormal PROD = ε_t
```

Mô hình chi phí tùy ý bất thường:

```text
DISEXP_t / A_{t-1} = α0 + α1 × (1 / A_{t-1})
                    + β1 × (Sales_{t-1} / A_{t-1}) + ε_t

Abnormal DISEXP = ε_t
```

Trong app, nếu không có R&D/quảng cáo riêng, `DISEXP` dùng chi phí bán hàng + quản lý hoặc proxy SG&A.

Diễn giải:

- Abnormal CFO âm: có thể kéo doanh thu bằng giảm giá hoặc nới tín dụng, làm CFO yếu.
- Abnormal PROD dương: có thể sản xuất dư/tồn kho cao để giảm giá vốn đơn vị.
- Abnormal DISEXP âm: có thể cắt chi phí tùy ý để nâng lợi nhuận ngắn hạn.

## Cách dùng kết quả trong định giá

Nếu một hoặc nhiều lớp cảnh báo cao:

1. Giảm độ tin cậy của EPS/LNST hiện tại.
2. Ưu tiên CFO, FCF, Owner Earnings và lợi nhuận bình thường hóa.
3. Tăng yêu cầu margin of safety.
4. Đọc kỹ thuyết minh doanh thu, phải thu, tồn kho, dự phòng, chi phí vốn hóa, khấu hao, giao dịch bên liên quan và ý kiến kiểm toán.
5. Không kết luận gian lận nếu chưa có bằng chứng kiểm toán/cơ quan quản lý.
