# V23.22 - So sánh doanh nghiệp so sánh doanh nghiệp và radar Chuỗi giá trị

## 1. Biểu đồ màng nhện trong tab Chuỗi giá trị

Tab **Chuỗi giá trị** của Định giá chuyên sâu đã bổ sung biểu đồ radar/màng nhện lấy trực tiếp từ cột **Điểm nhiệt** của bảng **Bản đồ chuỗi giá trị theo Porter**.

Quy đổi điểm nhiệt:

| Đánh giá sơ bộ | Điểm nhiệt |
|---|---:|
| Tốt | 100 |
| Trung bình | 55 |
| Yếu | 15 |
| Chưa đủ dữ liệu / Cần bổ sung bằng chứng | 35 |

Biểu đồ giúp nhìn nhanh hoạt động nào là lợi thế nổi bật, hoạt động nào là điểm yếu/cần kiểm tra thêm trong chuỗi giá trị.

## 2. Chuyển peer comparison thành So sánh doanh nghiệp

Tab **Dữ liệu DN cùng ngành** đã được tách khỏi Định giá chuyên sâu và chuyển thành trang riêng:

`pages/03_So_sanh_doanh_nghiep.py`

Tên phần hiển thị: **So sánh doanh nghiệp - So sánh doanh nghiệp**.

## 3. Crawl danh sách cùng ngành từ Vietstock

So sánh doanh nghiệp tự lấy mã đang hoạt động từ Tổng quan doanh nghiệp thông qua session state:

- `phần1_ticker`
- `active_ticker`
- `shared_ticker`
- `phần2_ticker`
- `last_query_ticker`

Sau đó app crawl trang Vietstock dạng:

`https://finance.vietstock.vn/{MÃ}/so-sanh-gia-co-phieu-cung-nganh.htm`

Kết quả được chuẩn hóa và lưu tại:

- `data_cache/peer_universe_phần2.csv`
- raw audit: `raw_data/vietstock_peers/`

Crawler được thiết kế có nhiều fallback: HTML page, HTML table, link tài chính, và các endpoint JSON/AJAX ứng viên của Vietstock. Nếu Vietstock đổi endpoint/chặn dữ liệu động, app không treo mà hiện cảnh báo và giữ raw file để kiểm tra.

## 4. So sánh tối đa 10 doanh nghiệp

Người dùng chọn tối đa 10 mã từ peer universe. App tự tải dữ liệu, định giá và tính:

- Giá hiện tại;
- Giá trị weighted;
- MOS hiện tại;
- P/E, P/B;
- ROE, ROIC;
- Biên gộp, biên ròng;
- CAGR doanh thu/LNST 5 năm;
- CFO/LNST, FCF/LNST;
- Nợ ròng/VCSH;
- Porter Moat score;
- điểm chất lượng, điểm dòng tiền, điểm định giá, điểm tổng hợp;
- xếp hạng và kết luận so sánh.

## 5. Note giải thích khi nhấp từng dòng

Bảng kết quả peer dùng `_render_explainable_table`. Khi nhấp một dòng, app hiện note gồm:

- xếp hạng và điểm tổng hợp;
- ROE, ROIC, biên gộp;
- CFO/LNST, FCF/LNST;
- giá hiện tại, giá trị weighted, MOS, P/E, P/B;
- Porter Moat score;
- nguyên tắc chấm điểm: 30% chất lượng sinh lời/vốn + 25% dòng tiền + 25% Porter Moat + 20% định giá/MOS, có phạt rủi ro nếu đòn bẩy cao.
