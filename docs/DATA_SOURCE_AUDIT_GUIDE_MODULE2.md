# DATA_SOURCE_AUDIT_GUIDE_MODULE2

## 1. Thứ tự ưu tiên nguồn dữ liệu

1. Báo cáo tài chính, báo cáo thường niên, công bố thông tin chính thức.
2. Dữ liệu chuẩn hóa từ Tổng quan doanh nghiệp/Financial tích hợp/FireAnt/Vietstock khi có.
3. Báo cáo phân tích CTCK, báo cáo ngành, hiệp hội ngành.
4. Tin tức tài chính, báo chí.
5. Blog/diễn đàn: chỉ dùng tham khảo, không dùng làm dữ liệu tính toán.

## 2. Cơ chế lưu vết

- Dữ liệu tài chính đã chuẩn hóa nằm trong `data_cache/` hoặc `sample_data/`.
- Raw response/tin tìm kiếm nằm trong `raw_data/phần2_web/{ticker}/`.
- Báo cáo xuất ra nằm trong `reports/`.
- Công thức nằm trong `docs/FORMULA_EXPLANATION_MODULE2.md`.
- Giả định định giá nằm trong `configs/valuation_assumptions_phần2.json`.

## 3. Cảnh báo bắt buộc

Định giá chuyên sâu phải cảnh báo khi:

- thiếu số cổ phiếu lưu hành;
- không có Owner Earnings hoặc FCF;
- FCF âm nhiều năm;
- lợi nhuận biến động mạnh;
- nợ vay/EBITDA cao;
- định giá asset play nhưng chưa kiểm tra chất lượng phải thu/tồn kho;
- dùng nguồn internet phụ trợ thay cho báo cáo gốc.

## 4. Nguyên tắc kiểm toán kết luận

Mỗi kết luận quan trọng phải truy được về:

- công thức;
- dữ liệu đầu vào;
- nguồn dữ liệu;
- giả định;
- cảnh báo hạn chế.


## Ghi chú V23.1

- Sửa lỗi nhận diện nhầm các dòng chỉ tiêu tài chính như ROE, ROIC, BasicEPS thành mã cổ phiếu.
- Danh sách mã có dữ liệu BCTC trong `Financial-v1.3.0.xlsm` hiện được đọc từ sheet `BÁO CÁO TÀI CHÍNH`, cột `Mã`.
- Với mã không có block BCTC nhiều kỳ, Định giá chuyên sâu dừng định giá và yêu cầu import/crawl dữ liệu trước, tránh hiển thị N/A hoặc moat score ảo.
- V23.66: đã bỏ nguồn online thử nghiệm `vnstock/KBS` và `vnstock/VCI` khỏi Module 2 để tránh phụ thuộc schema không ổn định; app ưu tiên FireAnt/Vietstock/Financial tích hợp/CSV mẫu.
