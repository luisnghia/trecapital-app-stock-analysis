# Beneish M-Score – hướng dẫn công thức và cách đánh giá

## Mục tiêu
Tab **Thao túng tài chính** trên page **Định giá chuyên sâu** dùng mô hình Beneish M-Score để cảnh báo rủi ro thao túng lợi nhuận/chất lượng BCTC kém. Kết quả là tín hiệu cảnh báo định lượng, không phải kết luận pháp lý về gian lận.

## Nguồn công thức
Mô hình 8 biến Beneish M-Score:

```text
M = -4.84 + 0.920×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI
    + 0.115×DEPI - 0.172×SGAI + 4.679×TATA - 0.327×LVGI
```

Ngưỡng cảnh báo dùng trong app: **M-Score > -2.22**.

## Biến đầu vào
| Biến | Công thức/logic triển khai | Ý nghĩa cảnh báo |
|---|---|---|
| DSRI | `(Phải thu/Doanh thu)t / (Phải thu/Doanh thu)t-1` | Phải thu tăng nhanh hơn doanh thu, có thể báo hiệu doanh thu ghi nhận lỏng hoặc thu tiền chậm. |
| GMI | `Biên gộp t-1 / Biên gộp t` | GMI > 1 nghĩa là biên gộp suy giảm, tăng áp lực làm đẹp lợi nhuận. |
| AQI | `[1 - (TS ngắn hạn + TSCĐ)/Tổng TS]t / [1 - (TS ngắn hạn + TSCĐ)/Tổng TS]t-1` | AQI > 1 cho thấy tài sản chất lượng thấp/chi phí hoãn lại có thể tăng. |
| SGI | `Doanh thu t / Doanh thu t-1` | Tăng trưởng cao tạo áp lực duy trì kỳ vọng lợi nhuận. |
| DEPI | `Tỷ lệ khấu hao t-1 / Tỷ lệ khấu hao t`, trong đó tỷ lệ khấu hao = khấu hao / (khấu hao + TSCĐ) | DEPI > 1 cho thấy tỷ lệ khấu hao giảm, cần kiểm tra thời gian hữu dụng/phương pháp khấu hao. |
| SGAI | `(SG&A/Doanh thu)t / (SG&A/Doanh thu)t-1` | SG&A/DT tăng phản ánh chi phí vận hành tăng nhanh hơn doanh thu. Nếu thiếu chi tiết bán hàng/quản lý, app dùng proxy và ghi rõ trong bảng. |
| TATA | Ưu tiên `Balance-sheet accruals / Tổng tài sản` với `Balance-sheet accruals = ΔCA - ΔCash - ΔCL + ΔNợ vay ngắn hạn - Khấu hao`; nếu thiếu dữ liệu thì fallback `(LNST - CFO) / Tổng tài sản` | TATA dương cao cho thấy lợi nhuận phụ thuộc accruals nhiều hơn dòng tiền. |
| LVGI | `(Nợ/Tổng TS)t / (Nợ/Tổng TS)t-1` | Đòn bẩy tăng có thể tạo động cơ đáp ứng covenant/nợ. |

## Cách đọc kết quả
| Mức | Quy tắc trong app | Hành động phân tích |
|---|---|---|
| Thấp | M-Score <= -2.70 | Không thấy tín hiệu cảnh báo lớn theo Beneish, nhưng vẫn phải kiểm tra dòng tiền và thuyết minh. |
| Theo dõi | -2.70 < M-Score <= -2.22 | Gần vùng cảnh báo, cần soi các biến nổi bật. |
| Rủi ro cao | -2.22 < M-Score <= -1.78 | Mô hình gắn cờ rủi ro thao túng lợi nhuận. Giảm độ tin cậy của lợi nhuận khi định giá. |
| Rủi ro rất cao | M-Score > -1.78 | Cần kiểm tra sâu doanh thu, phải thu, tồn kho, khấu hao, SG&A, accruals và nợ vay. |
| Thiếu dữ liệu | Không đủ 8 biến | App vẫn hiển thị biến đã tính được và danh sách biến thiếu/cần kiểm tra. |

## Lưu ý triển khai
- App chỉ dùng dữ liệu năm, không dùng TTM/T12M để tính Beneish vì mô hình cần so sánh năm t với năm t-1.
- Các số liệu tiền tệ giữ đơn vị tỷ đồng theo quy chuẩn app.
- Nếu nguồn dữ liệu thiếu chi tiết chi phí bán hàng/quản lý, app có thể ước tính SG&A bằng `Lợi nhuận gộp - Lợi nhuận hoạt động`, hoặc nếu không có lợi nhuận hoạt động thì dùng `Lợi nhuận gộp - Lợi nhuận trước thuế`. Khi dùng proxy, bảng hiển thị rõ để người dùng kiểm chứng lại BCTC.
- Với ngân hàng, bảo hiểm, chứng khoán và doanh nghiệp tài chính, Beneish 8 biến không phải công cụ lõi; chỉ dùng tham khảo nếu dữ liệu đủ.
- Từ V23.66, app ghi rõ cách tính TATA: balance-sheet accruals chuẩn nếu đủ thành phần; nếu không đủ thì đánh dấu proxy dòng tiền.
- Kết quả không khẳng định doanh nghiệp gian lận. Kết quả chỉ yêu cầu đọc sâu BCTC kiểm toán, thuyết minh, giao dịch bên liên quan và đối chiếu CFO/LNST.
