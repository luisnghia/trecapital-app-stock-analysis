# Định giá chuyên sâu V23.56

Đây là bản tích hợp: **Tổng quan doanh nghiệp nằm trong từng phần 2**, chạy chung một app Streamlit multipage.

## Cách chạy nhanh

1. Giải nén thư mục.
2. Chạy `install_and_run_phần2.bat` lần đầu.
3. Các lần sau chạy `run_phần2.bat`.
4. App sẽ tự mở tại trang gốc `http://localhost:8501/`, mặc định là **Tổng quan doanh nghiệp – Tổng quan doanh nghiệp**.
5. Sidebar vẫn có trang **Định giá chuyên sâu – Định giá chuyên sâu** để chuyển qua khi cần xem định giá chuyên sâu.

## Cách dùng đúng với mã như DGC

1. Nhập mã `DGC` ở **Tổng quan doanh nghiệp** hoặc **Định giá chuyên sâu**.
2. Giữ nguồn **Tự động từ dữ liệu tổng quan** hoặc **FireAnt + Vietstock**.
3. App tự chạy pipeline Tổng quan doanh nghiệp, lưu cache/raw data và đồng bộ ngay sang Định giá chuyên sâu.
4. Trong các bảng định giá/đánh giá, nhấp một lần vào từng dòng để xem note giải thích số liệu và nguyên tắc đánh giá.

## Version

- Package: Định giá chuyên sâu
- Version: V23.56
- Tổng quan doanh nghiệp tích hợp: V22

## File chạy

- `install_and_run_phần2.bat`: cài môi trường và chạy app tích hợp.
- `run_phần2.bat`: chạy nhanh app tích hợp.
- `run_phần1.bat`: vẫn giữ để chạy riêng Tổng quan doanh nghiệp nếu cần.

## Ghi chú

Định giá chuyên sâu không tự bịa số liệu. Nếu chưa có dữ liệu BCTC nhiều kỳ, app sẽ báo rõ để chạy Tổng quan doanh nghiệp/crawler trước.



## V23.22
- Chuyển card **Giá hiện tại** xuống ngay dưới dòng mã cổ phiếu/tên doanh nghiệp ở Tổng quan doanh nghiệp và Định giá chuyên sâu.
- Tăng kích thước các card KPI/metric khoảng 20% để dễ đọc trên dashboard.
- V23.22: chuyển **Dữ liệu DN cùng ngành** thành **So sánh doanh nghiệp - So sánh doanh nghiệp**; lưu danh sách peer vào `data_cache/peer_universe_phần2.csv`, hỗ trợ crawl Vietstock, nhập tay, upload CSV và chỉnh trực tiếp.
- Thêm lệnh **So sánh 10 doanh nghiệp cùng ngành**: app tải dữ liệu từng mã, tính định giá/MOS, Porter Moat, chất lượng vốn, chất lượng dòng tiền và xếp hạng so sánh.
- Kết quả peer có note giải thích khi nhấp vào từng dòng và có file CSV tải về để kiểm tra/audit.

## V23.20
- Khi mở app bằng file `.bat`, trình duyệt được mở chủ động tại `http://localhost:8501/` để vào thẳng **Tổng quan doanh nghiệp – Tổng quan doanh nghiệp**.
- Định giá chuyên sâu thêm bảng **Đánh giá trọng yếu theo dữ liệu doanh nghiệp** nằm trên mục **Dải giá trị nội tại**.
- Bảng đánh giá trả lời 5 câu hỏi: loại doanh nghiệp, độ bền lợi nhuận, nguồn moat, ROIC/ROCE là moat thật hay chu kỳ, và biên an toàn.
- Dòng cảnh báo/khuyến nghị được phóng to để dễ quan sát.
- Nhấp 1 lần vào chỉ tiêu để xem note.
- Note giải thích chi tiết theo dữ liệu từng doanh nghiệp, không dùng chung một nguyên tắc.
- Tích hợp nguyên tắc nguồn Graham/Buffett/Li Lu/Howard Marks/Porter vào note tự động.

## V23.20 – Cập nhật giao diện Trecapital và note Tổng quan doanh nghiệp

- Thêm logo Trecapital vào sidebar và hero của Tổng quan doanh nghiệp/Định giá chuyên sâu.
- Nền, button, khung cảnh báo và bảng note chuyển sang bộ màu xanh teal + vàng của logo.
- Định giá chuyên sâu đưa khung cảnh báo/khuyến nghị lên **trên Dải giá trị nội tại**, khung lớn và chữ to hơn.
- Tổng quan doanh nghiệp thêm note nhấp một lần cho bảng MOS, cảnh báo, bộ tiêu chí và bảng phân tích chỉ số tài chính.


## V23.20
- Thu nhỏ khung cảnh báo/khuyến nghị nổi bật khoảng 50%.
- Bổ sung giải thích trong tab Internet evidence cho moat/rủi ro/BCTC.


## V23.20
- Trả lại các thuật ngữ tài chính/phân tích quan trọng về dạng tiếng Anh như bản V23.15.
- Thêm heatmap cho cột Độ tin cậy trong bảng định giá theo phương pháp.


## V23.20
- Bỏ câu "Góc nhìn chủ sở hữu doanh nghiệp..." trong nhận xét tự động.
- Sửa lỗi đếm nhầm "Chưa đạt MOS" thành đạt MOS.
- Thêm glossary thuật ngữ/từ viết tắt trong tab Công thức & audit với comment tương tác.
- Nâng cấp Internet evidence: tìm theo mã cổ phiếu + tên doanh nghiệp, ưu tiên nguồn chính thức/tài chính, lọc kết quả rác từ trang tìm kiếm.
- Làm nổi bật dòng mã cổ phiếu và tên doanh nghiệp theo màu thương hiệu.


## V23.22
- Tách tab Dữ liệu DN cùng ngành thành So sánh doanh nghiệp - So sánh doanh nghiệp.
- So sánh doanh nghiệp tự lấy mã từ Tổng quan doanh nghiệp và crawl danh sách cổ phiếu cùng ngành từ Vietstock.
- Thêm biểu đồ màng nhện điểm nhiệt trong tab Chuỗi giá trị của Định giá chuyên sâu.


## V23.33 - So sánh doanh nghiệp Vietstock dynamic peer crawler

- So sánh doanh nghiệp ưu tiên dùng Selenium/Chrome headless để đọc bảng động **Cùng ngành** thật từ Vietstock.
- Bỏ fallback suy đoán danh sách peer theo ngành/ticker; nếu không lấy được bảng động/API thật, app báo lỗi và lưu raw audit thay vì tạo danh sách sai.
- Sidebar đã ẩn page kỹ thuật `app`; mặc định mở app là Tổng quan doanh nghiệp và điều hướng phần dùng nút thủ công theo nhận diện thương hiệu quỹ.
- Cần cài `selenium` từ `requirements.txt` và máy cần có Chrome/Chromium để crawl bảng động.


## V23.33 - So sánh doanh nghiệp Simplize peer crawler

- Bỏ luồng lấy danh sách peer từ Vietstock/Selenium trong từng phần 3 vì chậm và không ổn định.
- Thêm crawler Simplize: tự lấy URL ngành từ trang cổ phiếu Simplize hoặc dùng URL ngành người dùng nhập.
- Raw audit lưu tại `raw_data/simplize_peers/`; không tự tạo danh sách peer suy đoán khi không lấy được dữ liệu thật.


## V23.33
- Tóm tắt tự động Định giá chuyên sâu bổ sung Đặc điểm cần kiểm tra theo loại doanh nghiệp.
- Bảng Đánh giá trọng yếu theo dữ liệu doanh nghiệp hiển thị full, không cuộn trong bảng.
- Sửa cơ chế chọn dòng hiện note bằng UTF-8 base64 + event delegation cho các bảng explainable Tổng quan doanh nghiệp/2.

## V23.40 - Full static print report
- Báo cáo tổng hợp toàn bộ nội dung chuyển toàn bộ bảng in PDF sang HTML table tĩnh để bung đủ dòng, không còn bị cắt bởi khung cuộn Streamlit.
- Bổ sung note/nhận xét/diễn giải dưới các bảng đánh giá/chấm điểm quan trọng.
- Không thay đổi công thức và không ảnh hưởng các bảng tương tác ở Tổng quan doanh nghiệp/2/3.


## V23.42 - Clean consolidated print report

- Báo cáo tổng hợp đã bỏ các bảng dữ liệu thô và các tab dữ liệu/audit theo yêu cầu.
- Bảng ROIC & đầu tư được tối ưu để fit dòng khi in PDF.
- Cột Mã trong bảng peer comparison được nới rộng để không xuống dòng.


## V23.49
- Khôi phục nút **Tải dữ liệu quý** trong tab **Dữ liệu** của trang **Định giá chuyên sâu**.
