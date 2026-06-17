# V23.69 - Audit lại công thức lý thuyết và sửa TTM ratio

## Nội dung sửa
- Không còn carry các tỷ số quý như ROE, ROA, ROIC, P/E, P/B, P/S vào dòng TTM.
- Dòng TTM chỉ giữ giá thị trường dạng point-in-time; các tỷ số sinh lời được tính lại từ dòng tiền/lợi nhuận TTM và mẫu số bình quân trailing quarters.
- Bổ sung regression test để bắt lỗi stale quarterly ratios bị copy sang TTM.

## Lý do
Dòng TTM phải dùng mẫu số bình quân của kỳ trailing và tử số 4 quý cộng lại. Copy tỷ số của quý gần nhất sang TTM là sai về lý thuyết phân tích tài chính.
