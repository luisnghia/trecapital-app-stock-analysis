# V23.25 - So sánh doanh nghiệp: lấy bảng động Vietstock bằng browser automation, bỏ fallback suy đoán

## Vấn đề bản trước
- Trang `https://finance.vietstock.vn/{MÃ}/so-sanh-gia-co-phieu-cung-nganh.htm` trả HTML tĩnh nhưng bảng **Cùng ngành** được render bằng JavaScript.
- Cách crawl HTML/API đoán endpoint có thể chỉ thấy mã gốc hoặc nhầm chuỗi kỹ thuật thành ticker.
- Fallback theo ngành/ticker có rủi ro đưa danh sách peer không đúng bản chất ngành.

## Sửa đổi
1. `PublicVietstockCrawler.fetch_industry_peers()` ưu tiên mở trang Vietstock bằng Selenium/Chrome headless.
2. App chỉ đọc vùng DOM của widget cùng ngành: `#stock-relation-container`, `.stock-relation__container`, `.relation-content`.
3. App thu thêm body từ browser network log để bắt JSON/HTML động nếu Vietstock tải bảng bằng request ngầm.
4. Chỉ sau đó mới thử một số endpoint Vietstock cũ bằng anti-forgery token.
5. **Không còn tự sinh danh sách fallback/suy đoán.** Nếu không lấy được bảng động thật, app trả bảng rỗng và cảnh báo rõ:
   - chưa lấy được bảng động Vietstock;
   - raw HTML/browser/API đã lưu tại `raw_data/vietstock_peers`;
   - người dùng có thể crawl lại hoặc import CSV peer thủ công.

## Yêu cầu cài đặt
- `selenium==4.27.1` đã được thêm vào `requirements.txt`.
- Máy cần có Google Chrome hoặc trình duyệt Chromium tương thích. Selenium Manager sẽ tự xử lý driver khi môi trường cho phép.

## Điều hướng app
- Ẩn navigation mặc định của Streamlit để không hiện page kỹ thuật `app`.
- Thêm navigation thủ công theo nhận diện thương hiệu quỹ: Tổng quan doanh nghiệp, Định giá chuyên sâu, So sánh doanh nghiệp.
- `app.py` vẫn là entrypoint kỹ thuật nhưng mặc định render Tổng quan doanh nghiệp.
