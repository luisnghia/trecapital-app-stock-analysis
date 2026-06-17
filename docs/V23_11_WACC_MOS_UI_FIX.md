# V23.14 – WACC doanh nghiệp, MOS đồng bộ, UI Tổng quan doanh nghiệp

## 1. WACC doanh nghiệp

App bỏ hoàn toàn ô `WACC tham chiếu (%)`. WACC trong biểu đồ ROIC & đầu tư được tự tính cho từng doanh nghiệp và từng kỳ.

Công thức:

```text
WACC = E / (D + E) × Ke + D / (D + E) × Kd × (1 - Tax Rate)
```

Trong đó:

```text
E = Giá trị vốn hóa thị trường = shares_outstanding_mil × year_end_price / 1000
D = Nợ vay chịu lãi = vay ngắn hạn + vay dài hạn + trái phiếu + nợ thuê tài chính
Kd = |chi phí lãi vay hoặc lãi vay đã trả| / nợ vay chịu lãi bình quân
Tax Rate = chi phí thuế TNDN / lợi nhuận trước thuế, giới hạn 0%-50%
Ke = lãi suất phi rủi ro + beta × phần bù rủi ro thị trường
```

Nếu nguồn dữ liệu chưa có beta thị trường, app dùng beta proxy nội bộ, tính từ biến động lợi nhuận, biến động doanh thu và đòn bẩy của chính doanh nghiệp. Khi có beta thật từ dữ liệu thị trường, app sẽ ưu tiên beta thật.

## 2. MOS

MOS hiện tại không phụ thuộc mức MOS người dùng chọn:

```text
MOS hiện tại = (Giá trị nội tại - Giá hiện tại) / Giá trị nội tại
```

Các chỉ tiêu phải thay đổi khi người dùng đổi MOS:

```text
Giá mua theo MOS chọn = Giá trị nội tại × (1 - MOS yêu cầu)
Tín hiệu đạt/chưa đạt MOS = so sánh giá hiện tại với giá mua theo MOS chọn
Chênh lệch so với MOS yêu cầu = MOS hiện tại - MOS yêu cầu
```

## 3. Đồng bộ phần

Tổng quan doanh nghiệp và Định giá chuyên sâu dùng chung `st.session_state['target_mos_pct']`, `shared_ticker`, cache BCTC và kết quả tính toán. Đổi MOS ở một phần thì phần còn lại nhận cùng mức MOS.

## 4. UI

Tab Tổng quan doanh nghiệp/2 được tăng kích thước, tăng viền, nền và trạng thái đang chọn. Các phần nhận xét/đánh giá/kết luận quan trọng dùng khung đỏ, chữ lớn hơn và đậm hơn.
